from app.osclients.cinder import CinderOps
from tests.fakes.openstack import FakeCinder


def test_unmanage_then_manage_uses_manageable_reference():
    fake = FakeCinder()
    fake.add_volume("v1", size=10, host="h@be#pool", bootable=True, backend_name="volume-v1")
    ops = CinderOps(client=fake)

    ref_id = ops.unmanage("v1")                      # source side
    assert ref_id == "volume-v1"

    pool = ops.resolve_pool()                        # dest side discovery
    assert pool == "h@be#pool"

    ref = ops.wait_for_manageable(pool, backend_name="volume-v1", attempts=3, delay=0)
    assert ref == {"source-name": "volume-v1"}

    new = ops.manage(host=pool, ref=ref, name="v1", volume_type="vt", bootable=True, az="az1")
    assert new["id"] == "dst-v1"
    assert fake.managed_on[0]["volume_type"] == "vt"
