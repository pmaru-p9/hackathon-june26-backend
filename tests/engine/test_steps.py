from app.engine.staging import stage_ports
from app.engine.cutover import cutover
from app.osclients.neutron import NeutronOps
from app.osclients.nova import NovaOps
from app.osclients.cinder import CinderOps
from tests.fakes.openstack import FakeNeutron, FakeNova, FakeCinder


def test_stage_creates_ports_with_ip_mac():
    neutron = FakeNeutron(); neutron.add_subnet("sub", "netD", "10.20.0.0/24")
    res = stage_ports(NeutronOps(neutron),
                      network_map=[{"destNetworkId": "netD", "ip": "10.20.0.15",
                                    "mac": "fa:16:3e:aa:11"}])
    assert res.ok and res.checkpoint["destPortIds"] == ["port-10.20.0.15"]


def test_cutover_full_sequence_records_checkpoints():
    nova = FakeNova(); nova.add_server("s1", status="ACTIVE")
    cinder = FakeCinder()
    cinder.add_volume("v1", size=10, host="h@be#pool", bootable=True, backend_name="volume-v1")
    results = cutover(NovaOps(nova), CinderOps(cinder),
                      server_id="s1", volume_ids=["v1"], dest_port_ids=["port-x"],
                      flavor_id="f1", az="az1", volume_type="vt", sgs=["default"],
                      keypair="kp", metadata={}, name="db", root_volume_id="v1",
                      image_meta={"hw_disk_bus": "virtio"})
    steps = {r.step: r for r in results}
    assert nova.stopped == ["s1"]                       # C1
    assert nova.detached == [("s1", "v1")]              # C2
    assert steps["C3"].checkpoint["unmanaged"] == ["volume-v1"]
    assert steps["C4"].checkpoint["destVolIds"] == ["dst-v1"]
    assert steps["C5"].checkpoint["destServerId"] == "dst-srv"
