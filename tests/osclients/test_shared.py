from app.osclients.shared import resolve_shared


class FakeCin:
    def __init__(self, host=None, pools=None):
        self._host = host
        self._pools = pools or []

    def volume_host(self, vid):
        return self._host

    def pools(self):
        return [{"name": p} for p in self._pools]


SRC_BP = [{"storageBackends": {"nfs": {"nfs1": {"config": {"nfs_mount_points": "s:/shared"}}}}}]
DST_BP = [{"storageBackends": {
    "nfs": {"vt": {"config": {"nfs_mount_points": "s:/other"}}},
    "pm-nfs": {"nfs1": {"config": {"nfs_mount_points": "s:/shared"}}}}}]


def test_resolve_shared_finds_matching_dest_pool():
    src = FakeCin(host="u@nfs1#nfs")
    dst = FakeCin(pools=["a@vt#nfs", "b@nfs1#pm-nfs"])
    r = resolve_shared(source_cinder=src, source_bp=SRC_BP, dest_cinder=dst, dest_bp=DST_BP,
                       root_volume_id="v1")
    assert r["sharedBackend"] is True
    assert r["destPoolHost"] == "b@nfs1#pm-nfs"
    assert r["resolvedVolumeType"] == "b@nfs1#pm-nfs"


def test_resolve_shared_no_match():
    src = FakeCin(host="u@nfs1#nfs")
    dst = FakeCin(pools=["a@vt#nfs"])   # only s:/other, not s:/shared
    r = resolve_shared(source_cinder=src, source_bp=SRC_BP, dest_cinder=dst, dest_bp=DST_BP,
                       root_volume_id="v1")
    assert r["sharedBackend"] is False and r["destPoolHost"] is None
