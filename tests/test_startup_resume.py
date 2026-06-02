from app.engine.runner import MigrationRunner
from app.store.migrations import MigrationRepo
from tests.fakes.k8s import FakeCustomObjects, FakeSecrets


def test_resume_inflight_only_picks_non_terminal():
    co, sec = FakeCustomObjects(), FakeSecrets()
    repo = MigrationRepo(co, sec, namespace="ns")
    a = repo.create("s1", "a", "d", "t", "az", [], {}, {}, "keepStopped")
    b = repo.create("s2", "b", "d", "t", "az", [], {}, {}, "keepStopped")
    repo.set_phase(a["id"], "Completed")
    repo.set_phase(b["id"], "Cutover")
    runner = MigrationRunner(repo, engine=None)
    resumed = runner.resume_inflight(repo.list())
    assert b["id"] in resumed and a["id"] not in resumed
