from app.engine.base import StepResult


class DestVmNotActive(Exception):
    ...


def verify_and_cleanup(dst_nova, src_nova, server_id_dest, source_server_id, source_cleanup):
    """V1 confirms the destination VM is ACTIVE before declaring success; if it is not,
    raises DestVmNotActive so the runner marks NeedsAttention (no auto-rollback once the
    dest VM exists). V2 applies the source-cleanup policy on the SOURCE cloud."""
    status = dst_nova.server_status(server_id_dest)
    if status != "ACTIVE":
        raise DestVmNotActive(f"destination VM {server_id_dest} is {status}, not ACTIVE")
    results = [StepResult("V1", ok=True, checkpoint={"destServerId": server_id_dest})]
    if source_cleanup == "delete":
        src_nova.delete(source_server_id)
        results.append(StepResult("V2", ok=True, checkpoint={"sourceDeleted": True}))
    else:
        results.append(StepResult("V2", ok=True, checkpoint={"sourceKeptStopped": True}))
    return results
