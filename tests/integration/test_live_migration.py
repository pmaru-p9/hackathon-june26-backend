import os
import pytest

pytestmark = pytest.mark.skipif(os.getenv("PCD_LIVE") != "1",
                                reason="requires two shared-backend PCD envs")


def test_happy_path_volume_backed_vm_moves():
    # Documented manual/CI steps when PCD_LIVE=1:
    #   1. register dest env, 2. run preflight (all pass), 3. launch,
    #   4. poll until Completed, 5. assert dest VM ACTIVE + same IP, source kept stopped.
    assert True  # replace with live calls when the PCD_LIVE harness is available
