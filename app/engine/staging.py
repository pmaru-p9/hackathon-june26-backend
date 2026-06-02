from app.engine.base import StepResult


def stage_ports(neutron, network_map) -> StepResult:
    port_ids = []
    for nic in network_map:
        port_ids.append(neutron.create_port(nic["destNetworkId"], nic["ip"], nic["mac"]))
    return StepResult("S1", ok=True, checkpoint={"destPortIds": port_ids})
