from app.engine.rollback import rollback_in_place, reverse_migrate
from app.engine.plan import MigrationPlan
from app.engine.base import MigrationContext
from app.osclients.nova import NovaOps
from app.osclients.cinder import CinderOps
from app.osclients.neutron import NeutronOps
from tests.fakes.openstack import FakeNova, FakeCinder, FakeNeutron


def _plan():
    return MigrationPlan(context=MigrationContext(), network_map=[{"destNetworkId": "n",
        "ip": "10.0.0.5", "mac": "fa:16:3e:00:00:01"}], server_id="s1", volume_ids=["v1"],
        root_volume_id="v1", volume_type="vt", az="az1", flavor_id="f1", sgs=["default"],
        keypair="kp", metadata={}, name="db", source_host="h@be#pool", attach_order=["v1"],
        source_cleanup="delete", dot_original=True,
        # NetApp NFS source pool: reverse re-manage builds the full-path source-name directly
        source_pool_host="h@netapp-nfs1#10.9.1.210:/cinder_nfs_vol1")


def test_regime_a_restores_flag_and_powers_on():
    nova = FakeNova(); nova.add_server("s1", status="SHUTOFF")
    nova.set_attachment("s1", "v1", delete_on_termination=False)   # was flipped to False
    neutron = FakeNeutron()
    cp = {"S1": {"destPortIds": ["port-x"]}, "C1": {"wasRunning": True},
          "C2": {"detachedData": []}, "C2b": {"dotOriginal": True, "flipped": True}}
    actions = rollback_in_place(NovaOps(nova), NeutronOps(neutron), checkpoints=cp, plan=_plan())
    assert nova.started == ["s1"]
    assert nova.attachment_dot("s1", "v1") is True       # flag restored to original
    assert "delete_port:port-x" in actions


def test_regime_b_reverse_migrate_recreates_source_no_data_delete():
    src_nova = FakeNova(); dst_nova = FakeNova(); dst_nova.add_server("dst-srv", status="ERROR")
    src_neutron = FakeNeutron(); dst_neutron = FakeNeutron()
    cinder = FakeCinder()
    cp = {"S1": {"destPortIds": ["dport"]}, "C2c": {"sourceDeleted": True},
          "C3": {"unmanaged": ["volume-v1"]},
          "C4": {"destVolIds": ["dst-v1"], "rootDestVolId": "dst-v1"},
          "C5": {"destServerId": "dst-srv"}}
    actions = reverse_migrate(NovaOps(src_nova), CinderOps(cinder), NovaOps(dst_nova),
        CinderOps(cinder), NeutronOps(src_neutron), NeutronOps(dst_neutron),
        checkpoints=cp, plan=_plan())
    assert "delete_dest_vm:dst-srv" in actions
    assert "unmanage_dest:dst-v1" in actions
    # NetApp renamed the file to volume-<destVolId> during C4; reverse re-manages by that
    # current name (not the original C3 source name).
    assert "remanage_source:volume-dst-v1" in actions
    assert any(a.startswith("recreate_source_port") for a in actions)
    assert "create_source_vm:s1-recreated" in actions
    assert not any(a.startswith("delete_volume") for a in actions)


def test_regime_b_backstop_raises_on_failure():
    import pytest
    from app.engine.rollback import ReverseMigrateError

    class BoomNeutron:
        def create_port(self, *a, **k):
            raise RuntimeError("neutron down")

    cinder = FakeCinder()
    cp = {"C2c": {"sourceDeleted": True}, "C3": {"unmanaged": ["volume-v1"]}}
    with pytest.raises(ReverseMigrateError):
        reverse_migrate(NovaOps(FakeNova()), CinderOps(cinder), NovaOps(FakeNova()),
            CinderOps(cinder), BoomNeutron(), NeutronOps(FakeNeutron()),
            checkpoints=cp, plan=_plan())
