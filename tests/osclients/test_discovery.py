from app.osclients.discovery import DiscoveryService


class FakeConn:
    def __init__(self, fail=False):
        self.fail = fail

    def authorize(self):
        if self.fail:
            raise RuntimeError("bad creds")
        return "tok"

    def projects(self):
        return [{"id": "p1", "name": "target"}]

    def azs(self):
        return [{"name": "az1"}]

    def networks(self):
        return [{"id": "n1", "name": "app", "subnets": [{"cidr": "10.20.0.0/24"}]}]

    def flavors(self):
        return [{"id": "f1", "name": "m1.small", "vcpus": 1, "ram": 2048, "disk": 20}]


def test_test_connection_ok_and_fail():
    svc = DiscoveryService(conn_factory=lambda did: FakeConn())
    assert svc.test("d1") == (True, "ok")
    bad = DiscoveryService(conn_factory=lambda did: FakeConn(fail=True))
    ok, msg = bad.test("d1")
    assert ok is False and "bad creds" in msg


def test_discovery_lists():
    svc = DiscoveryService(conn_factory=lambda did: FakeConn())
    assert svc.projects("d1")[0]["name"] == "target"
    assert svc.azs("d1")[0]["name"] == "az1"
    assert svc.flavors("d1")[0]["vcpus"] == 1
