from types import SimpleNamespace as NS

from app.osclients.connections import server_to_dict, DiscoveryConn
from app.osclients.profile import build_migration_profile


class FakeCompute:
    def __init__(self, server):
        self._server = server

    def get_server(self, vid):
        return self._server


class FakeNetwork:
    def __init__(self, ports):
        self._ports = ports

    def ports(self, device_id=None):
        return self._ports


def test_server_to_dict_boot_from_volume_and_nics():
    server = NS(
        id="s1",
        attached_volumes=[{"id": "v1"}, {"id": "v2"}],
        image={},                       # no base image -> boot from volume
        flavor={"vcpus": 4, "ram": 8192, "disk": 40},
        security_groups=[{"name": "default"}],
        key_name="kp",
        metadata={"a": "b"},
        block_device_mapping=[{"boot_index": 0, "volume_id": "v1"}],
    )
    port = NS(id="p1", network_id="n1", mac_address="fa:16:3e:aa:11",
              fixed_ips=[{"ip_address": "10.20.0.15"}])
    conn = NS(compute=FakeCompute(server), network=FakeNetwork([port]))

    d = server_to_dict(conn, "s1")
    assert d["boot_from_volume"] is True
    assert d["root_volume_id"] == "v1"
    assert d["attached_volumes"] == ["v1", "v2"]
    assert d["flavor"] == {"vcpus": 4, "ram": 8192, "disk": 40}
    assert d["nics"] == [{"port_id": "p1", "network_id": "n1",
                          "ip": "10.20.0.15", "mac": "fa:16:3e:aa:11"}]
    # feeds the existing profile builder cleanly
    prof = build_migration_profile(NS(server=lambda vid: d), "s1")
    assert prof["bootVolumeBacked"] is True and prof["rootVolumeId"] == "v1"


def test_discovery_conn_networks_group_subnets():
    nets = [NS(id="n1", name="app")]
    subs = [NS(network_id="n1", cidr="10.20.0.0/24")]
    network = NS(networks=lambda: nets, subnets=lambda: subs)
    conn = NS(network=network)
    out = DiscoveryConn(conn).networks()
    assert out == [{"id": "n1", "name": "app", "subnets": [{"cidr": "10.20.0.0/24"}]}]
