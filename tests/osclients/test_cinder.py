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


def test_wait_available_polls_until_managing_settles():
    # NetApp manage is async: 'managing' -> 'available'. wait_available must block until then.
    class _AsyncManage:
        def __init__(self):
            self.seq = ["managing", "managing", "available"]
        def volume_status(self, vid):
            return self.seq.pop(0) if len(self.seq) > 1 else self.seq[0]
    ops = CinderOps(client=_AsyncManage())
    ops.wait_available("dst-1", attempts=5, delay=0)   # returns (no raise) once available


def test_resolve_manage_ref_nfs_builds_full_path_without_listing():
    fake = FakeCinder()
    ops = CinderOps(client=fake)
    host = "h@netapp-nfs1#10.9.1.210:/cinder_nfs_vol1"

    ref = ops.resolve_manage_ref(host, "volume-abc", attempts=3, delay=0)

    # full share-path source-name, and list_manageable was never consulted
    assert ref == {"source-name": "10.9.1.210:/cinder_nfs_vol1/volume-abc"}
    assert fake._unmanaged == {}      # no manageable scan happened


def test_resolve_manage_ref_block_falls_back_to_manageable_list():
    fake = FakeCinder()
    fake.add_volume("v1", size=10, host="h@be#pool", bootable=True, backend_name="volume-v1")
    ops = CinderOps(client=fake)
    ops.unmanage("v1")               # populates the manageable list on h@be#pool

    ref = ops.resolve_manage_ref("h@be#pool", "volume-v1", attempts=3, delay=0)

    assert ref == {"source-name": "volume-v1"}


class _ErrorUnmanagingCinder:
    """Simulates the NFS driver: the first unmanage async-fails into 'error_unmanaging';
    after a reset-state to 'available', the next unmanage succeeds (volume gone)."""
    def __init__(self):
        self.status = "available"
        self.unmanage_calls = 0
        self.resets = []
    def backend_name(self, vid):
        return f"volume-{vid}"
    def unmanage(self, vid):
        self.unmanage_calls += 1
        # first attempt fails into error_unmanaging; after a reset it succeeds (gone)
        self.status = None if self.status == "available" and self.unmanage_calls > 1 \
            else "error_unmanaging"
    def volume_status_or_none(self, vid):
        return self.status
    def reset_state(self, vid, status):
        self.resets.append((vid, status))
        self.status = status


def test_unmanage_resets_and_retries_on_error_unmanaging():
    fake = _ErrorUnmanagingCinder()
    ops = CinderOps(client=fake)

    ref_id = ops.unmanage("v1", attempts=5, delay=0)

    assert ref_id == "volume-v1"
    assert fake.resets == [("v1", "available")]   # reset once
    assert fake.unmanage_calls == 2               # original + one retry
    assert fake.status is None                    # gone = unmanaged
