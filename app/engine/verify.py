from app.engine.base import StepResult


class DestVmNotActive(Exception):
    ...


def verify_and_cleanup(dst_nova, server_id_dest):
    """V1 confirms the destination VM is ACTIVE before declaring success; if it is not,
    raises DestVmNotActive so the runner marks NeedsAttention. V2 is a record only — the
    source instance was already deleted during cutover (C2c) to free the root volume."""
    status = dst_nova.server_status(server_id_dest)
    if status != "ACTIVE":
        raise DestVmNotActive(f"destination VM {server_id_dest} is {status}, not ACTIVE")
    return [StepResult("V1", ok=True, checkpoint={"destServerId": server_id_dest}),
            StepResult("V2", ok=True, checkpoint={"sourceAlreadyDeleted": True})]
