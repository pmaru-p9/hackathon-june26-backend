"""Production client adapters satisfying the interfaces app.osclients.{cinder,nova,neutron}
Ops expect, backed by openstacksdk / python-cinderclient.

LIVE-VALIDATE: the execution path (cutover/rollback) cannot be exercised without two
shared-backend clouds. Every SDK leaf-call below is written to the documented API and
marked; confirm via tests/integration (PCD_LIVE) before a real migration."""
from app.config import settings


class ProdCinder:
    """Implements the CinderOps `.c` surface over python-cinderclient v3."""

    def __init__(self, cinder, backend_name_fmt: str = "volume-{id}"):
        self.cinder = cinder
        self._fmt = backend_name_fmt  # driver-specific array naming; default RBD/LVM style

    def backend_name(self, vid):
        # LIVE-VALIDATE: driver-specific. Most drivers name the array volume "volume-<uuid>".
        return self._fmt.format(id=vid)

    def volume_host(self, vid):
        # 'uuid@backend#pool' — used to resolve the source NFS export via the blueprint.
        return self.cinder.volumes.get(vid)._info.get("os-vol-host-attr:host")

    def volume_status(self, vid):
        return self.cinder.volumes.get(vid).status

    def volume_status_or_none(self, vid):
        # Returns the volume's status, or None if it is gone from this Cinder (a successful
        # unmanage removes the volume record). cinderclient raises NotFound -> 404.
        try:
            return self.cinder.volumes.get(vid).status
        except Exception:  # noqa: BLE001 -- NotFound (volume gone) is the success signal
            return None

    def reset_state(self, vid, status):
        # admin os-reset_status; clears a stuck 'error_unmanaging' back to 'available' so the
        # unmanage can be retried.
        self.cinder.volumes.reset_state(vid, state=status, attach_status="detached")

    def unmanage(self, vid):
        self.cinder.volumes.unmanage(vid)

    def list_manageable(self, host):
        out = []
        for e in self.cinder.volumes.list_manageable(host, detailed=True):
            d = e.to_dict() if hasattr(e, "to_dict") else dict(e)
            out.append({"reference": d.get("reference"), "size": d.get("size"),
                        "safe_to_manage": d.get("safe_to_manage")})
        return out

    def manage(self, host, ref, name, volume_type, bootable, availability_zone, metadata=None):
        v = self.cinder.volumes.manage(host=host, ref=ref, name=name, volume_type=volume_type,
                                       bootable=bootable, availability_zone=availability_zone,
                                       metadata=metadata)
        return {"id": v.id}

    def set_image_metadata(self, vid, meta):
        if meta:
            self.cinder.volumes.set_image_metadata(vid, meta)

    def services(self):
        return [{"binary": s.binary, "host": s.host, "state": s.state}
                for s in self.cinder.services.list(binary="cinder-volume")]

    def pools(self):
        # cinderclient PoolManager.list uses `detailed=`, not `detail=`.
        return [{"name": p.name, "backend_name": getattr(p, "volume_backend_name", None)}
                for p in self.cinder.pools.list(detailed=True)]


class ProdNova:
    """Implements the NovaOps `.c` surface over openstacksdk conn.compute."""

    def __init__(self, conn):
        self.conn = conn

    def stop(self, sid):
        self.conn.compute.stop_server(sid)
        self.conn.compute.wait_for_server(self.conn.compute.get_server(sid), status="SHUTOFF")

    def start(self, sid):
        self.conn.compute.start_server(sid)

    def detach_volume(self, sid, vid):
        # SDK signature is (server, volume) — server first.
        self.conn.compute.delete_volume_attachment(sid, vid)

    def attach_volume(self, sid, vid):
        self.conn.compute.create_volume_attachment(sid, volume_id=vid)

    def create_server(self, **kw):
        # Translate our generic kwargs to the SDK's create_server signature. The root
        # volume gets boot_index 0 and the caller-supplied delete_on_termination; data
        # volumes get boot_index -1 and delete_on_termination False.
        root = kw.get("root_volume_id")
        root_dot = kw.get("root_delete_on_termination", False)
        bdm = []
        for v in kw.get("block_device_mapping", []):
            is_root = v == root
            bdm.append({"uuid": v, "source_type": "volume", "destination_type": "volume",
                        "boot_index": 0 if is_root else -1,
                        "delete_on_termination": root_dot if is_root else False})
        attrs = dict(
            name=kw["name"], flavor_id=kw["flavor"],
            networks=[{"port": p} for p in kw.get("ports", [])],
            block_device_mapping_v2=bdm,
            availability_zone=kw.get("availability_zone"),   # always passed (per design)
            metadata=kw.get("metadata") or {},
            security_groups=[{"name": g} for g in (kw.get("security_groups") or [])])
        # Optional fields rejected by Nova if sent as null — include only when set.
        if kw.get("key_name"):
            attrs["key_name"] = kw["key_name"]
        # Preserve cloud-init inputs so the recreated VM re-applies its first-boot config
        # (passwords, users, etc.). user_data is the base64 string Nova returned for the source.
        if kw.get("user_data"):
            attrs["user_data"] = kw["user_data"]
        if kw.get("config_drive"):
            attrs["config_drive"] = True
        srv = self.conn.compute.create_server(**attrs)
        return {"id": srv.id}

    def delete(self, sid):
        self.conn.compute.delete_server(sid)

    def server_status(self, sid):
        return self.conn.compute.get_server(sid).status

    def attachment_dot(self, server_id, volume_id):
        # Nova volume-attachments API (>=2.79 exposes delete_on_termination). The SDK's
        # get_volume_attachment(id, server) is finicky; list and match by volume id.
        for a in self.conn.compute.volume_attachments(server_id):
            if getattr(a, "volume_id", getattr(a, "id", None)) == volume_id:
                return bool(getattr(a, "delete_on_termination", False))
        return False

    def set_attachment_dot(self, server_id, volume_id, value):
        # microversion >= 2.85 required to update delete_on_termination.
        # SDK signature is (server, volume) — server first.
        self.conn.compute.update_volume_attachment(server_id, volume_id,
                                                   delete_on_termination=value)


class ProdNeutron:
    """Implements the NeutronOps `.c` surface over openstacksdk conn.network."""

    def __init__(self, conn):
        self.conn = conn

    def create_port(self, network_id, fixed_ip, mac):
        p = self.conn.network.create_port(
            network_id=network_id, fixed_ips=[{"ip_address": fixed_ip}], mac_address=mac)
        return p.id

    def delete_port(self, pid):
        # idempotent: a staged port may already be gone (e.g. partial rollback)
        self.conn.network.delete_port(pid, ignore_missing=True)


def manageable_poll(cinder_ops, pool, backend_name):
    """Convenience used by the engine: poll manageable-list with the configured cadence."""
    return cinder_ops.wait_for_manageable(
        pool, backend_name, attempts=settings.manageable_poll_attempts,
        delay=settings.manageable_poll_seconds)
