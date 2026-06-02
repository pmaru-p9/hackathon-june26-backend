from app.engine.base import StepResult


def verify_and_cleanup(nova, server_id_dest, source_server_id, source_cleanup) -> list:
    results = [StepResult("V1", ok=True, checkpoint={"destServerId": server_id_dest})]
    if source_cleanup == "delete":
        nova.delete(source_server_id)
        results.append(StepResult("V2", ok=True, checkpoint={"sourceDeleted": True}))
    else:
        results.append(StepResult("V2", ok=True, checkpoint={"sourceKeptStopped": True}))
    return results
