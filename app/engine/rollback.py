"""Compensation matrix. Returns an ordered list of action tags (for auditing/tests)
and performs them. NEVER deletes backend volume data — only re-toggles management."""
ORDER = ["Preflight", "S1", "S2", "C1", "C2", "C3", "C4", "C5", "V1"]


def rollback(nova, cinder, neutron, failed_at, checkpoints, source_server_id,
             source_host, attach_order) -> list[str]:
    actions: list[str] = []
    reached = set(ORDER[: ORDER.index(failed_at) + 1])

    # C5: a partially/over-created dest server would be removed by the runner before this;
    # C4: undo destination manage (unmanage on dest) so the LUN is free again
    if "C4" in reached:
        for dvid in checkpoints.get("C4", {}).get("destVolIds", []):
            cinder.unmanage_by_id(dvid)
            actions.append(f"unmanage_dest:{dvid}")
    # C3: re-manage the unmanaged volumes back on the SOURCE
    if "C3" in reached:
        pool = source_host
        for backend_name in checkpoints.get("C3", {}).get("unmanaged", []):
            ref = {"source-name": backend_name}
            cinder.manage(host=pool, ref=ref, name=backend_name, volume_type=None,
                          bootable=True, az=None)
            actions.append(f"remanage_source:{backend_name}")
    # C2: reattach volumes to the source VM in original order
    if "C2" in reached:
        for vid in attach_order:
            nova.attach_volume(source_server_id, vid)
            actions.append(f"reattach:{vid}")
    # C1: power the source VM back on
    if "C1" in reached:
        nova.start(source_server_id)
        actions.append(f"power_on:{source_server_id}")
    # S1: delete the pre-created destination ports
    if "S1" in reached:
        for pid in checkpoints.get("S1", {}).get("destPortIds", []):
            neutron.delete_port(pid)
            actions.append(f"delete_port:{pid}")
    return actions
