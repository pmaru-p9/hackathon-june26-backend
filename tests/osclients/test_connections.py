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


def test_root_volume_multivolume_uses_root_device_then_bootable():
    # no block_device_mapping exposed (common on plain get_server); the data volume is
    # listed first. Root must be resolved via root_device_name / bootable flag, not attached[0].
    server = NS(id="s2", attached_volumes=[{"id": "data"}, {"id": "root"}], image={},
                flavor={"vcpus": 2, "ram": 4096, "disk": 0},
                security_groups=[], key_name=None, metadata={},
                root_device_name="/dev/vda")           # no block_device_mapping
    attach = [NS(volume_id="data", device="/dev/vdb"), NS(volume_id="root", device="/dev/vda")]

    class C:
        def get_server(self, vid): return server
        def volume_attachments(self, vid): return attach
    class BS:
        def get_volume(self, vid):
            return NS(is_bootable=("true" if vid == "root" else "false"))
    port = NS(id="p", network_id="n", mac_address="m", fixed_ips=[{"ip_address": "1.2.3.4"}])
    conn = NS(compute=C(), network=FakeNetwork([port]), block_storage=BS())

    d = server_to_dict(conn, "s2")
    assert d["root_volume_id"] == "root"          # via root_device_name match, not attached[0]


def test_server_to_dict_resolves_flavor_name_to_uuid():
    # the embedded server flavor 'id' is actually the NAME on this cloud; server_to_dict
    # must resolve it to the real UUID so reverse-migration can recreate the source.
    server = NS(id="s3", attached_volumes=[{"id": "v1"}], image={},
                flavor={"id": "m1.medium.vol", "original_name": "m1.medium.vol",
                        "vcpus": 2, "ram": 4096, "disk": 0},
                security_groups=[], key_name=None, metadata={},
                block_device_mapping=[{"boot_index": 0, "volume_id": "v1"}])

    class C:
        def get_server(self, vid): return server
        def find_flavor(self, name, ignore_missing=True):
            return NS(id="b49a293b-real-uuid") if name == "m1.medium.vol" else None
    port = NS(id="p", network_id="n", mac_address="m", fixed_ips=[{"ip_address": "1.2.3.4"}])
    conn = NS(compute=C(), network=FakeNetwork([port]))

    d = server_to_dict(conn, "s3")
    assert d["flavor_id"] == "b49a293b-real-uuid"
