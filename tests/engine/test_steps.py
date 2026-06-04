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


def test_cutover_bootvol_deletes_source_and_preserves_dot():
    src_nova = FakeNova(); src_nova.add_server("s1", status="ACTIVE")
    src_nova.set_attachment("s1", "vroot", delete_on_termination=True)
    dst_nova = FakeNova()
    cinder = FakeCinder()   # shared backend
    cinder.add_volume("vroot", size=1, host="h@be#pool", bootable=True, backend_name="volume-vroot")
    cinder.add_volume("vdata", size=1, host="h@be#pool", bootable=False, backend_name="volume-vdata")
    results = list(cutover(NovaOps(src_nova), CinderOps(cinder), NovaOps(dst_nova),
        CinderOps(cinder), server_id="s1", volume_ids=["vroot", "vdata"], root_volume_id="vroot",
        dest_pool_host="h@be#pool", dest_port_ids=["port-x"], flavor_id="f1", az="az1",
        volume_type="vt", sgs=["default"], keypair="kp", metadata={}, name="db", image_meta={}))
    steps = {r.step: r for r in results}
    assert src_nova.detached == [("s1", "vdata")]          # C2 data only, NOT vroot
    assert steps["C2b"].checkpoint == {"dotOriginal": True, "flipped": True}
    assert src_nova.deleted == ["s1"]                       # C2c deletes source
    assert set(steps["C3"].checkpoint["unmanaged"]) == {"volume-vroot", "volume-vdata"}
    assert steps["C4"].checkpoint["rootDestVolId"] == "dst-vroot"
    assert steps["C5"].checkpoint["destServerId"] == "dst-srv"
    assert dst_nova.created[0]["root_delete_on_termination"] is True


def test_cutover_is_incremental_generator():
    """A mid-cutover failure must still yield the earlier steps (so they get checkpointed)."""
    src_nova = FakeNova(); src_nova.add_server("s1", status="ACTIVE")
    cinder = FakeCinder()   # no volume added -> C3 unmanage (backend_name) raises KeyError
    gen = cutover(NovaOps(src_nova), CinderOps(cinder), NovaOps(FakeNova()), CinderOps(cinder),
                  server_id="s1", volume_ids=["missing"], root_volume_id="missing",
                  dest_pool_host="h@be#pool", dest_port_ids=[], flavor_id="f", az="az",
                  volume_type="vt", sgs=[], keypair="kp", metadata={}, name="db", image_meta={})
    yielded = []
    with pytest.raises(KeyError):
        for res in gen:
            yielded.append(res.step)
    # C2c's wait_available looks up the (missing) volume's status -> KeyError before C2c yields
    assert yielded == ["C1", "C2", "C2b"]


def test_verify_raises_when_dest_not_active():
    dst = FakeNova(); dst.add_server("dst-srv", status="ERROR")
    with pytest.raises(DestVmNotActive):
        verify_and_cleanup(NovaOps(dst), "dst-srv")


def test_verify_ok_when_dest_active_records_source_already_deleted():
    dst = FakeNova(); dst.add_server("dst-srv", status="ACTIVE")
    results = verify_and_cleanup(NovaOps(dst), "dst-srv")
    steps = {r.step: r.checkpoint for r in results}
    assert steps["V1"]["destServerId"] == "dst-srv"
    assert steps["V2"]["sourceAlreadyDeleted"] is True


def test_verify_waits_through_build_until_active():
    # a freshly created dest VM is briefly BUILD; V1 must poll, not fail on the first check
    class _BuildingNova:
        def __init__(self):
            self.seq = ["BUILD", "BUILD", "ACTIVE"]
        def server_status(self, sid):
            return self.seq.pop(0) if len(self.seq) > 1 else self.seq[0]
    results = verify_and_cleanup(_BuildingNova(), "dst-srv", attempts=5, delay=0)
    assert {r.step for r in results} == {"V1", "V2"}
