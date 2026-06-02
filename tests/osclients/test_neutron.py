from app.osclients.neutron import NeutronOps, ip_in_cidr
from tests.fakes.openstack import FakeNeutron


def test_ip_in_cidr():
    assert ip_in_cidr("10.20.0.15", "10.20.0.0/24") is True
    assert ip_in_cidr("10.99.0.15", "10.20.0.0/24") is False


def test_create_port_preserves_ip_mac():
    fake = FakeNeutron(); fake.add_subnet("sub1", "net1", "10.20.0.0/24")
    ops = NeutronOps(client=fake)
    pid = ops.create_port("net1", "10.20.0.15", "fa:16:3e:aa:11")
    assert fake.ports[pid]["fixed_ip"] == "10.20.0.15"
    assert fake.ports[pid]["mac"] == "fa:16:3e:aa:11"
