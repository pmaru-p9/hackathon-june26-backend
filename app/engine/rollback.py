"""Rollback compensations. NEVER delete backend volume data — only re-toggle management
and rebuild instances. Regime A (source still exists) restores in place; Regime B (source
already deleted) best-effort reverse-migrates, else raises ReverseMigrateError so the
runner marks NeedsAttention."""


class ReverseMigrateError(Exception):
    """A reverse-migration step failed; the message carries the remaining manual steps."""


def rollback_in_place(nova, neutron, *, checkpoints, plan):
    """Regime A: failure before C2c (source VM still exists). Restore it in place."""
    actions = []
    # C2b: restore delete_on_termination to its original value if we flipped it
    c2b = checkpoints.get("C2b", {})
    if c2b.get("flipped"):
        nova.set_dot(plan.server_id, plan.root_volume_id, c2b.get("dotOriginal", True))
        actions.append("restore_dot")
    # C2: reattach data volumes that were detached
    for vid in checkpoints.get("C2", {}).get("detachedData", []):
        nova.attach_volume(plan.server_id, vid)
        actions.append(f"reattach:{vid}")
    # C1: power the source VM back on
    if "C1" in checkpoints:
        nova.start(plan.server_id)
        actions.append(f"power_on:{plan.server_id}")
    # S1: delete staged dest ports
    for pid in checkpoints.get("S1", {}).get("destPortIds", []):
        neutron.delete_port(pid)
        actions.append(f"delete_port:{pid}")
    return actions


def reverse_migrate(src_nova, src_cinder, dst_nova, dst_cinder, src_neutron, dst_neutron,
                    *, checkpoints, plan):
    """Regime B: failure after C2c (source deleted). Best-effort rebuild of the source.
    Raises ReverseMigrateError if any step fails (runner -> NeedsAttention)."""
    actions = []
    try:
        # undo destination, in reverse
        if "C5" in checkpoints:
            dst_nova.delete(checkpoints["C5"]["destServerId"])
            actions.append(f"delete_dest_vm:{checkpoints['C5']['destServerId']}")
        for dvid in checkpoints.get("C4", {}).get("destVolIds", []):
            dst_cinder.unmanage_by_id(dvid)
            actions.append(f"unmanage_dest:{dvid}")
        # re-manage volumes back on the source
        for backend_name in checkpoints.get("C3", {}).get("unmanaged", []):
            src_cinder.manage(host=plan.source_host, ref={"source-name": backend_name},
                              name=backend_name, volume_type=None, bootable=True, az=None)
            actions.append(f"remanage_source:{backend_name}")
        # recreate the source port(s) with original IP/MAC
        port_ids = []
        for nic in plan.network_map:
            port_ids.append(src_neutron.create_port(nic["destNetworkId"], nic["ip"],
                                                    nic["mac"]))
            actions.append(f"recreate_source_port:{nic['ip']}")
        # recreate the source VM from the re-managed root volume
        src_nova.create_server(name=f"{plan.server_id}-recreated", flavor=plan.flavor_id,
                               ports=port_ids, block_device_mapping=plan.volume_ids,
                               root_volume_id=plan.root_volume_id,
                               root_delete_on_termination=plan.dot_original,
                               availability_zone=plan.az, security_groups=plan.sgs,
                               key_name=plan.keypair, metadata=plan.metadata)
        actions.append(f"create_source_vm:{plan.server_id}-recreated")
        for pid in checkpoints.get("S1", {}).get("destPortIds", []):
            dst_neutron.delete_port(pid)
            actions.append(f"delete_dest_port:{pid}")
        return actions
    except Exception as exc:  # noqa: BLE001
        raise ReverseMigrateError(
            f"reverse migration failed after {actions}; volume(s) safe on shared backend; "
            f"manual recovery: re-manage on source + recreate VM. cause: {exc}") from exc
