from app.engine.staging import stage_ports
from app.engine.cutover import cutover
from app.engine.verify import verify_and_cleanup, DestVmNotActive
from app.osclients.neutron import NeutronOps
from app.osclients.nova import NovaOps
from app.osclients.cinder import CinderOps
from tests.fakes.openstack import FakeNeutron, FakeNova, FakeCinder
import pytest


def test_stage_creates_ports_with_ip_mac():
    neutron = FakeNeutron(); neutron.add_subnet("sub", "netD", "10.20.0.0/24")
    res = stage_ports(NeutronOps(neutron),
                      network_map=[{"destNetworkId": "netD", "ip": "10.20.0.15",
                                    "mac": "fa:16:3e:aa:11"}])
    assert res.ok and res.checkpoint["destPortIds"] == ["port-10.20.0.15"]


def test_cutover_full_sequence_records_checkpoints():
    src_nova = FakeNova(); src_nova.add_server("s1", status="ACTIVE")
    dst_nova = FakeNova()
    cinder = FakeCinder()   # shared backend: same array backs source and destination
    cinder.add_volume("v1", size=10, host="h@be#pool", bootable=True, backend_name="volume-v1")
    results = list(cutover(NovaOps(src_nova), CinderOps(cinder), NovaOps(dst_nova),
                           CinderOps(cinder),
                           server_id="s1", volume_ids=["v1"], dest_port_ids=["port-x"],
                           flavor_id="f1", az="az1", volume_type="vt", sgs=["default"],
                           keypair="kp", metadata={}, name="db", root_volume_id="v1",
                           image_meta={"hw_disk_bus": "virtio"}))
    steps = {r.step: r for r in results}
    assert src_nova.stopped == ["s1"]                   # C1 on source
    assert src_nova.detached == [("s1", "v1")]          # C2 on source
    assert steps["C3"].checkpoint["unmanaged"] == ["volume-v1"]
    assert steps["C4"].checkpoint["destVolIds"] == ["dst-v1"]
    assert steps["C5"].checkpoint["destServerId"] == "dst-srv"
    assert dst_nova.created                              # C5 on destination


def test_cutover_is_incremental_generator():
    """A mid-cutover failure must still yield the earlier steps (so they get checkpointed)."""
    src_nova = FakeNova(); src_nova.add_server("s1", status="ACTIVE")
    cinder = FakeCinder()   # no volume added -> C3 unmanage raises KeyError mid-stream
    gen = cutover(NovaOps(src_nova), CinderOps(cinder), NovaOps(FakeNova()), CinderOps(cinder),
                  server_id="s1", volume_ids=["missing"], dest_port_ids=[], flavor_id="f",
                  az="az", volume_type="vt", sgs=[], keypair="kp", metadata={}, name="db",
                  root_volume_id="missing", image_meta={})
    yielded = []
    with pytest.raises(KeyError):
        for res in gen:
            yielded.append(res.step)
    assert yielded == ["C1", "C2"]   # C1/C2 emitted before C3 failed


def test_verify_raises_when_dest_not_active():
    dst = FakeNova(); dst.add_server("dst-srv", status="ERROR")
    src = FakeNova(); src.add_server("s1", status="SHUTOFF")
    with pytest.raises(DestVmNotActive):
        verify_and_cleanup(NovaOps(dst), NovaOps(src), "dst-srv", "s1", "keepStopped")


def test_verify_deletes_source_when_requested():
    dst = FakeNova(); dst.add_server("dst-srv", status="ACTIVE")
    src = FakeNova(); src.add_server("s1", status="SHUTOFF")
    verify_and_cleanup(NovaOps(dst), NovaOps(src), "dst-srv", "s1", "delete")
    assert src.deleted == ["s1"]
