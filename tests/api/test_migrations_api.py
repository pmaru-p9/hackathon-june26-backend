from fastapi.testclient import TestClient
from app.main import app
from app.deps import set_repos
from app.store.migrations import MigrationRepo
from tests.fakes.k8s import FakeCustomObjects, FakeSecrets


def setup_client():
    repo = MigrationRepo(FakeCustomObjects(), FakeSecrets(), namespace="ns")
    set_repos(migrations=repo)
    return TestClient(app), repo


def test_launch_creates_migration_and_returns_id():
    client, repo = setup_client()
    resp = client.post("/api/v1/migrations", headers={
        "x-auth-token": "T", "x-auth-url": "http://s/v3", "x-project-id": "p"},
        json={"vmIds": ["s1"], "vmName": "db", "destinationId": "d1",
              "targetProject": "t", "az": "az1", "networkMap": [],
              "flavor": {"auto": True}, "preserve": {}, "sourceCleanup": "keepStopped"})
    assert resp.status_code == 202
    mid = resp.json()["id"]
    assert repo.get(mid)["status"]["phase"] in ("Pending", "Preflight")


def test_get_migration_status():
    client, repo = setup_client()
    m = repo.create("s1", "db", "d1", "t", "az1", [], {"auto": True}, {}, "keepStopped")
    resp = client.get(f"/api/v1/migrations/{m['id']}")
    assert resp.status_code == 200 and resp.json()["status"]["phase"] == "Pending"
