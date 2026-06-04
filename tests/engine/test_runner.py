from app.engine.runner import MigrationRunner, ReauthRequired
from app.store.migrations import MigrationRepo
from tests.fakes.k8s import FakeCustomObjects, FakeSecrets


class StubEngine:
    def __init__(self, fail_at=None):
        self.fail_at = fail_at
        self.calls = []

    def preflight(self, m):
        self.calls.append("preflight")
        return True, []

    def stage(self, m):
        self.calls.append("stage")
        return [("S1", {"destPortIds": []})]

    def cutover(self, m):
        self.calls.append("cutover")
        if self.fail_at == "C4":
            raise RuntimeError("manage failed")
        return [("C1", {}), ("C2", {}), ("C3", {}), ("C4", {}), ("C5", {"destServerId": "d"})]

    def verify(self, m):
        self.calls.append("verify")
        return [("V1", {}), ("V2", {})]

    def rollback(self, m, failed_at, checkpoints):
        self.calls.append(f"rollback:{failed_at}")


def make_repo():
    return MigrationRepo(FakeCustomObjects(), FakeSecrets(), namespace="ns")


def test_happy_path_reaches_completed():
    repo = make_repo()
    m = repo.create("s1", "db", "d1", "t", "az1", [], {"auto": True}, {}, "keepStopped")
    MigrationRunner(repo, StubEngine()).run(m["id"])
    assert repo.get(m["id"])["status"]["phase"] == "Completed"


def test_failure_in_cutover_triggers_rollback_and_RolledBack():
    repo = make_repo()
    m = repo.create("s1", "db", "d1", "t", "az1", [], {"auto": True}, {}, "keepStopped")
    eng = StubEngine(fail_at="C4")
    MigrationRunner(repo, eng).run(m["id"])
    assert repo.get(m["id"])["status"]["phase"] == "RolledBack"
    assert any(c.startswith("rollback") for c in eng.calls)


def test_failed_preflight_clears_source_token():
    repo = make_repo()
    m = repo.create("s1", "db", "d1", "t", "az1", [], {"auto": True}, {}, "keepStopped")
    repo.store_source_token(m["id"], "T", "http://s/v3", "p")

    class FailPreflight(StubEngine):
        def preflight(self, m):
            return False, []

    MigrationRunner(repo, FailPreflight()).run(m["id"])
    assert repo.get(m["id"])["status"]["phase"] == "Failed"
    import pytest
    with pytest.raises(KeyError):       # token secret removed on terminal Failed
        repo.read_source_token(m["id"])


def test_needs_reauth_preserves_source_token():
    repo = make_repo()
    m = repo.create("s1", "db", "d1", "t", "az1", [], {"auto": True}, {}, "keepStopped")
    repo.store_source_token(m["id"], "T", "http://s/v3", "p")

    class ReauthEngine(StubEngine):
        def stage(self, m):
            raise ReauthRequired("token expired")

    MigrationRunner(repo, ReauthEngine()).run(m["id"])
    assert repo.get(m["id"])["status"]["phase"] == "NeedsReauth"
    assert repo.read_source_token(m["id"])["token"] == "T"   # preserved for /reauth
