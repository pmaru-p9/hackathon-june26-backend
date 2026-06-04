from app.store.migrations import MigrationRepo
from app.store.destinations import DestinationRepo
from tests.fakes.k8s import FakeCustomObjects, FakeSecrets


def test_destination_repo_persists_spec_and_secret():
    co, sec = FakeCustomObjects(), FakeSecrets()
    repo = DestinationRepo(co, sec, namespace="ns")
    d = repo.create(name="east", auth_url="http://e/v3", region="r1",
                    project_name="svc", user_domain="Default", project_domain="Default",
                    username="svc", password="pw")
    assert sec.read("ns", f"dest-pcd-{d['id']}")["password"] == "pw"
    assert "password" not in co.get("ns", "DestinationPCD", d["id"])["spec"]


def test_migration_checkpoint_append():
    co = FakeCustomObjects(); sec = FakeSecrets()
    repo = MigrationRepo(co, sec, namespace="ns")
    m = repo.create(vm_id="s1", vm_name="db", destination_ref="d1", target_project="t",
                    az="az1", network_map=[], flavor={"auto": True},
                    preserve={}, source_cleanup="keepStopped")
    repo.checkpoint(m["id"], step="C3", state="done", data={"unmanaged": ["volume-v1"]})
    got = repo.get(m["id"])
    last = got["status"]["steps"][-1]
    assert last["checkpoint"]["unmanaged"] == ["volume-v1"]
    assert last["name"] == "C3"                              # canonical id unchanged (logic keys off this)
    assert last["summary"] == "unmanage volume on source"    # self-explanatory summary added


def test_destination_create_cleans_secret_if_cr_fails():
    from tests.fakes.k8s import FakeCustomObjects, FakeSecrets

    class FailingCO(FakeCustomObjects):
        def create(self, ns, kind, body):
            raise RuntimeError("k8s rejected the CR")

    co, sec = FailingCO(), FakeSecrets()
    repo = DestinationRepo(co, sec, namespace="ns")
    import pytest
    with pytest.raises(RuntimeError):
        repo.create(name="x", auth_url="u", region="r", project_name="p",
                    user_domain="Default", project_domain="Default",
                    username="svc", password="pw")
    # secret must not be left orphaned
    assert sec.data == {}
