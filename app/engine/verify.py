import time

from app.config import settings
from app.engine.base import StepResult


class DestVmNotActive(Exception):
    ...


def verify_and_cleanup(dst_nova, server_id_dest, attempts: int = None, delay: int = None):
    """V1 waits for the destination VM to reach ACTIVE before declaring success (a freshly
    created VM is briefly BUILD); ERROR short-circuits. If it never becomes ACTIVE, raises
    DestVmNotActive so the runner marks NeedsAttention. V2 is a record only — the source
    instance was already deleted during cutover (C2c) to free the root volume."""
    attempts = attempts if attempts is not None else settings.verify_active_attempts
    delay = delay if delay is not None else settings.verify_active_seconds
    status = None
    for _ in range(attempts):
        status = dst_nova.server_status(server_id_dest)
        if status == "ACTIVE":
            return [StepResult("V1", ok=True, checkpoint={"destServerId": server_id_dest}),
                    StepResult("V2", ok=True, checkpoint={"sourceAlreadyDeleted": True})]
        if status == "ERROR":
            break
        if delay:
            time.sleep(delay)
    raise DestVmNotActive(f"destination VM {server_id_dest} is {status}, not ACTIVE")
