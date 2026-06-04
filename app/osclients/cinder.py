import time


class ManageableNotReady(Exception):
    ...


class VolumeNotAvailable(Exception):
    ...


class CinderOps:
    """Thin wrapper translating engine intent into Cinder admin API calls.
    `client` exposes: unmanage(id), list_manageable(host), manage(...),
    set_image_metadata(id, meta), services(), pools(). In production this is a
    cinderclient v3 adapter; in tests it's FakeCinder."""

    def __init__(self, client):
        self.c = client

    def unmanage(self, volume_id: str, attempts: int = 6, delay: int = 5) -> str:
        """Unmanage from this Cinder. The NFS driver can async-fail into
        'error_unmanaging'; detect it, reset-state to available, and retry until the
        volume is gone (success) or attempts are exhausted."""
        backend_name = self.c.backend_name(volume_id)
        self.c.unmanage(volume_id)          # POST volumes/{id}/action {"os-unmanage": null}
        for _ in range(attempts):
            status = self.c.volume_status_or_none(volume_id)
            if status is None:
                return backend_name          # gone from this Cinder = unmanaged
            if status == "error_unmanaging":
                self.c.reset_state(volume_id, "available")
                self.c.unmanage(volume_id)
            if delay:
                time.sleep(delay)
        return backend_name

    def unmanage_by_id(self, volume_id: str) -> None:
        """Unmanage a volume by id without needing it tracked locally — used to release
        a destination-managed volume during rollback (we don't need its backend name)."""
        self.c.unmanage(volume_id)

    def wait_available(self, volume_id: str, attempts: int, delay: int) -> None:
        """After deleting a boot-from-volume instance the root volume detaches
        asynchronously; Cinder rejects unmanage until it is 'available'."""
        for _ in range(attempts):
            if self.c.volume_status(volume_id) == "available":
                return
            if delay:
                time.sleep(delay)
        raise VolumeNotAvailable(f"{volume_id} did not become available before unmanage")

    def resolve_pool(self) -> str:
        pools = self.c.pools()
        if not pools:
            raise RuntimeError("no cinder-volume pools on destination")
        return pools[0]["name"]             # h@be#pool

    def wait_for_manageable(self, host: str, backend_name: str, attempts: int, delay: int) -> dict:
        for _ in range(attempts):
            for entry in self.c.list_manageable(host):
                ref = entry["reference"]
                if ref.get("source-name") == backend_name and entry.get("safe_to_manage"):
                    return ref
            if delay:
                time.sleep(delay)
        raise ManageableNotReady(f"{backend_name} not manageable on {host}")

    def manage(self, host, ref, name, volume_type, bootable, az, metadata=None) -> dict:
        return self.c.manage(host=host, ref=ref, name=name, volume_type=volume_type,
                             bootable=bootable, availability_zone=az, metadata=metadata)

    def set_image_metadata(self, volume_id: str, meta: dict) -> None:
        self.c.set_image_metadata(volume_id, meta)
