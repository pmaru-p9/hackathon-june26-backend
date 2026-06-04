from app.engine.base import MigrationContext
from app.engine.plan import build_plan
from app.engine.production import ProductionEngine
from app.engine.runner import MigrationRunner
from app.osclients.nova import NovaOps
from app.osclients.cinder import CinderOps
from app.osclients.neutron import NeutronOps
from app.store.migrations import MigrationRepo
from tests.fakes.openstack import FakeNova, FakeCinder, FakeNeutron
from tests.fakes.k8s import FakeCustomObjects, FakeSecrets


SPEC = {
    "source": {"vmId": "s1", "vmName": "db"},
    "az": "az1",
    "networkMap": [{"sourcePortId": "p1", "destNetworkId": "netD",
                    "ip": "10.20.0.15", "mac": "fa:16:3e:aa:11"}],
    "sourceCleanup": "keepStopped",
}
PROFILE = {
    "vmId": "s1", "attachedVolumes": ["v1"], "rootVolumeId": "v1",
    "securityGroups": ["default"], "keyName": "kp", "metadata": {"a": "b"},
}


def all_pass_context():
    return MigrationContext(is_admin=True, dest_reachable=True, volume_backed=True,
                            shared_backend=True, resolved_volume_type="vt", flavor_match=True,
                            ip_fits_and_free=True, mac_free=True, volumes_detachable=True,
                            quota_ok=True)


def test_build_plan_maps_fields():
    plan = build_plan(SPEC, PROFILE, all_pass_context(),
                      dest_flavor_id="f1", dest_volume_type="vt", dest_pool_host="h@be#pool")
    assert plan.server_id == "s1"
    assert plan.volume_ids == ["v1"] and plan.root_volume_id == "v1"
    assert plan.network_map == [{"destNetworkId": "netD", "ip": "10.20.0.15",
                                 "mac": "fa:16:3e:aa:11"}]
    assert plan.flavor_id == "f1" and plan.volume_type == "vt" and plan.az == "az1"
    assert plan.name == "db" and plan.source_cleanup == "delete"


def test_production_engine_happy_path_threads_ports_and_server():
    repo = MigrationRepo(FakeCustomObjects(), FakeSecrets(), namespace="ns")
    m = repo.create("s1", "db", "d1", "t", "az1", SPEC["networkMap"], {"auto": True}, {},
                    "keepStopped")
    src_nova = FakeNova(); src_nova.add_server("s1", status="ACTIVE")
    dst_nova = FakeNova()
    cinder = FakeCinder()   # shared backend: one array backs source + destination
    cinder.add_volume("v1", size=10, host="h@be#pool", bootable=True, backend_name="volume-v1")
    neutron = FakeNeutron(); neutron.add_subnet("sub", "netD", "10.20.0.0/24")

    plan = build_plan(SPEC, PROFILE, all_pass_context(),
                      dest_flavor_id="f1", dest_volume_type="vt", dest_pool_host="h@be#pool")
    engine = ProductionEngine(repo, NovaOps(src_nova), CinderOps(cinder), NovaOps(dst_nova),
                              CinderOps(cinder), NeutronOps(neutron), plan)
    MigrationRunner(repo, engine).run(m["id"])

    status = repo.get(m["id"])["status"]
    assert status["phase"] == "Completed"
    steps = {s["name"]: s["checkpoint"] for s in status["steps"]}
    assert steps["S1"]["destPortIds"] == ["port-10.20.0.15"]   # staged
    assert steps["C4"]["destVolIds"] == ["dst-v1"]             # managed on dest
    assert steps["C5"]["destServerId"] == "dst-srv"           # created on dest
    assert src_nova.stopped == ["s1"] and dst_nova.created     # source stopped, dest created
