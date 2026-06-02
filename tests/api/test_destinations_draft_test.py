from fastapi.testclient import TestClient
from app.main import app
from app.deps import set_repos
from app.osclients.discovery import DiscoveryService


class FakeDraftConn:
    def __init__(self, creds, fail):
        self.creds = creds
        self.fail = fail

    def authorize(self):
        if self.fail:
            raise RuntimeError("bad creds")
        return "tok"


def _client(fail):
    disc = DiscoveryService(conn_factory=lambda did: None,
                            draft_conn_factory=lambda creds: FakeDraftConn(creds, fail))
    set_repos(discovery=disc)
    return TestClient(app)


def body():
    return {"authUrl": "http://e/v3", "username": "svc", "password": "pw",
            "projectName": "svc", "userDomain": "Default", "projectDomain": "Default"}


def test_draft_test_ok():
    resp = _client(fail=False).post("/api/v1/destinations/test", json=body())
    assert resp.status_code == 200 and resp.json() == {"reachable": True}


def test_draft_test_bad_creds_returns_502():
    resp = _client(fail=True).post("/api/v1/destinations/test", json=body())
    assert resp.status_code == 502
