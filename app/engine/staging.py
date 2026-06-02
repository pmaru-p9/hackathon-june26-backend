from app.engine.base import StepResult


def stage_ports(neutron, network_map) -> StepResult:
    """Pre-create destination ports with the source IP+MAC. If creating a later port
    fails, delete the ones already created so no orphaned ports (holding the original
    MACs) are left behind, then re-raise."""
    port_ids = []
    try:
        for nic in network_map:
            port_ids.append(neutron.create_port(nic["destNetworkId"], nic["ip"], nic["mac"]))
    except Exception:
        for pid in port_ids:
            neutron.delete_port(pid)
        raise
    return StepResult("S1", ok=True, checkpoint={"destPortIds": port_ids})
