from app.osclients.nova import NovaOps, match_flavor
from tests.fakes.openstack import FakeNova


def test_match_flavor_by_specs():
    flavors = [dict(id="f1", name="m1.small", vcpus=1, ram=2048, disk=20),
               dict(id="f2", name="m1.large", vcpus=4, ram=8192, disk=40)]
    assert match_flavor(flavors, vcpus=4, ram=8192, disk=40)["id"] == "f2"
    assert match_flavor(flavors, vcpus=8, ram=1, disk=1) is None


def test_stop_and_detach_recorded():
    fake = FakeNova(); fake.add_server("s1", status="ACTIVE")
    ops = NovaOps(client=fake)
    ops.stop("s1"); ops.detach_volume("s1", "v1")
    assert fake.stopped == ["s1"] and fake.detached == [("s1", "v1")]
