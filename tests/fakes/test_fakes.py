from tests.fakes.openstack import FakeCinder
from tests.fakes.k8s import FakeCustomObjects

def test_fake_cinder_unmanage_then_manageable():
    c = FakeCinder()
    c.add_volume("vol-1", size=10, host="h@be#pool", bootable=True, backend_name="volume-vol-1")
    c.unmanage("vol-1")
    assert "vol-1" not in c.volumes
    refs = c.list_manageable("h@be#pool")
    assert refs[0]["reference"] == {"source-name": "volume-vol-1"}
    assert refs[0]["safe_to_manage"] is True

def test_fake_k8s_custom_objects_roundtrip():
    co = FakeCustomObjects()
    co.create("ns", "Migration", {"metadata": {"name": "m1"}, "spec": {}})
    got = co.get("ns", "Migration", "m1")
    assert got["metadata"]["name"] == "m1"
