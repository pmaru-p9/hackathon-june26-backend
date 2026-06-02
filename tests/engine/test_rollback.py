from app.engine.rollback import rollback
from app.osclients.nova import NovaOps
from app.osclients.cinder import CinderOps
from app.osclients.neutron import NeutronOps
from tests.fakes.openstack import FakeNova, FakeCinder, FakeNeutron


def test_rollback_after_C4_remanages_on_source_and_never_deletes_data():
    nova, cinder, neutron = FakeNova(), FakeCinder(), FakeNeutron()
    nova.add_server("s1", status="SHUTOFF")
    checkpoints = {"S1": {"destPortIds": ["port-x"]},
                   "C2": {"detached": ["v1"]},
                   "C3": {"unmanaged": ["volume-v1"]},
                   "C4": {"destVolIds": ["dst-v1"]}}
    actions = rollback(NovaOps(nova), CinderOps(cinder), NeutronOps(neutron),
                       failed_at="C4", checkpoints=checkpoints, source_server_id="s1",
                       source_host="h@be#pool", attach_order=["v1"])
    assert "unmanage_dest:dst-v1" in actions
    assert "remanage_source:volume-v1" in actions
    assert "reattach:v1" in actions
    assert "power_on:s1" in actions
    assert "delete_port:port-x" in actions
    assert not any(a.startswith("delete_volume") for a in actions)   # invariant
