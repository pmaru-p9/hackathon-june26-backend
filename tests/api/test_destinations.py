from fastapi.testclient import TestClient
from app.main import app, set_repos      # set_repos injects fakes for tests
from app.store.destinations import DestinationRepo
from tests.fakes.k8s import FakeCustomObjects, FakeSecrets


def client_with_fakes():
    repo = DestinationRepo(FakeCustomObjects(), FakeSecrets(), namespace="ns")
    set_repos(destinations=repo)
    return TestClient(app), repo


def test_register_destination_hides_password():
    client, _ = client_with_fakes()
    resp = client.post("/api/v1/destinations", json={
        "name": "east", "authUrl": "http://e/v3", "region": "r1",
        "username": "svc", "password": "pw", "projectName": "svc",
        "userDomain": "Default", "projectDomain": "Default"})
    assert resp.status_code == 201
    body = resp.json()
    assert "password" not in body
    assert body["name"] == "east"


def test_list_destinations():
    client, _ = client_with_fakes()
    client.post("/api/v1/destinations", json={
        "name": "east", "authUrl": "http://e/v3", "region": "r1", "username": "svc",
        "password": "pw", "projectName": "svc", "userDomain": "Default",
        "projectDomain": "Default"})
    resp = client.get("/api/v1/destinations")
    assert resp.status_code == 200 and len(resp.json()) == 1
