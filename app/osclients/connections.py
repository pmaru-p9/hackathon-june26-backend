"""Build openstacksdk Connections and wrap them in the small interfaces the discovery
service and engine expect. SDK leaf-calls here are written to openstacksdk 3.x and must
be confirmed against a live cloud (see tests/integration + LIVE_VALIDATION.md)."""


def _connect(auth_type: str, auth: dict, region_name: str | None = None):
    import openstack
    return openstack.connect(auth_type=auth_type, auth=auth, region_name=region_name)


def source_connection(auth_url: str, token: str, project_id: str):
    return _connect("v3token", {"auth_url": auth_url, "token": token, "project_id": project_id})


def dest_connection(*, auth_url, username, password, project_name, user_domain,
                    project_domain, region_name=None):
    return _connect("v3password", {
        "auth_url": auth_url, "username": username, "password": password,
        "project_name": project_name, "user_domain_name": user_domain,
        "project_domain_name": project_domain}, region_name)


def dest_connection_project(*, auth_url, username, password, project_id, user_domain,
                            region_name=None):
    """Service-account connection scoped to a specific target project (by id) — where the
    migrated VM/volumes land. os-volume_manage creates the volume in the token's project."""
    return _connect("v3password", {
        "auth_url": auth_url, "username": username, "password": password,
        "project_id": project_id, "user_domain_name": user_domain}, region_name)


def cinder_client(conn, region_name=None):
    """python-cinderclient v3 from an openstacksdk Connection's session. Microversion 3.8
    is required for manageable-list. region_name must match the cloud's catalog region or
    endpoint lookup returns nothing (e.g. pools.list() comes back empty); default to the
    connection's own region."""
    from cinderclient import client as cc
    region = region_name or getattr(getattr(conn, "config", None), "region_name", None)
    return cc.Client("3.8", session=conn.session, region_name=region)


class DiscoveryConn:
    """Wraps an openstacksdk Connection for destination discovery + connectivity test."""

    def __init__(self, conn):
        self.conn = conn

    def authorize(self):
        # Forces a token fetch; raises on bad creds (mapped to a failed test()).
        return self.conn.authorize()

    def projects(self):
        return [{"id": p.id, "name": p.name} for p in self.conn.identity.projects()]

    def azs(self):
        return [{"name": az.name} for az in self.conn.compute.availability_zones()]

    def networks(self):
        subnets_by_net: dict = {}
        for s in self.conn.network.subnets():
            subnets_by_net.setdefault(s.network_id, []).append({"cidr": s.cidr})
        return [{"id": n.id, "name": n.name, "subnets": subnets_by_net.get(n.id, [])}
                for n in self.conn.network.networks()]

    def flavors(self):
        return [{"id": f.id, "name": f.name, "vcpus": f.vcpus, "ram": f.ram, "disk": f.disk}
                for f in self.conn.compute.flavors()]


class SourceConn:
    """Wraps a token-scoped Connection; .server() returns the dict build_migration_profile
    expects. Mapping below must be confirmed live (root-volume detection, flavor shape)."""

    def __init__(self, conn):
        self.conn = conn

    def server(self, vm_id: str) -> dict:
        return server_to_dict(self.conn, vm_id)


def server_to_dict(conn, vm_id: str) -> dict:
    """Pure-ish mapping of an SDK server (+ its ports/volumes) to the profile input dict.
    `conn` exposes compute.get_server / compute.get_flavor / network.ports."""
    s = conn.compute.get_server(vm_id)
    attached = [v["id"] for v in (getattr(s, "attached_volumes", None) or [])]
    # boot-from-volume: no base image set and at least one attached volume
    image = getattr(s, "image", None)
    image_id = image.get("id") if isinstance(image, dict) else getattr(image, "id", None)
    boot_from_volume = bool(attached) and not image_id
    # root volume: boot_index 0, else match the server's root_device_name, else the bootable
    # volume, else first attached. attached[0] alone is unreliable for multi-volume VMs.
    root_volume_id = _root_volume(conn, s, vm_id, attached)
    flavor = _flavor_specs(conn, s)
    nics = []
    for port in conn.network.ports(device_id=vm_id):
        for fixed in (port.fixed_ips or []):
            nics.append({"port_id": port.id, "network_id": port.network_id,
                         "ip": fixed.get("ip_address"), "mac": port.mac_address})
    fl = getattr(s, "flavor", None) or {}
    flavor_id = fl.get("id") if isinstance(fl, dict) else getattr(fl, "id", None)
    return {
        "id": s.id,
        "flavor": flavor,
        "flavor_id": flavor_id,
        "availability_zone": getattr(s, "availability_zone", None),
        "security_groups": [g.get("name") for g in (getattr(s, "security_groups", None) or [])],
        "key_name": getattr(s, "key_name", None),
        "metadata": dict(getattr(s, "metadata", None) or {}),
        "attached_volumes": attached,
        "boot_from_volume": boot_from_volume,
        "root_volume_id": root_volume_id,
        "nics": nics,
    }


def _root_volume(conn, server, vm_id: str, attached: list):
    # 1) explicit block_device_mapping with boot_index 0 (most authoritative when exposed)
    bdm = getattr(server, "block_device_mapping", None) or []
    for b in bdm:
        if b.get("boot_index") == 0 and b.get("volume_id"):
            return b["volume_id"]
    # 2) the attachment whose device is the server's root device (e.g. /dev/vda)
    root_dev = getattr(server, "root_device_name", None)
    if root_dev:
        try:
            for a in conn.compute.volume_attachments(vm_id):
                if getattr(a, "device", None) == root_dev:
                    return getattr(a, "volume_id", getattr(a, "id", None))
        except Exception:  # noqa: BLE001 -- fake/edge conns lack volume_attachments
            pass
    # 3) the bootable volume (ask cinder) — a data volume reports bootable False
    try:
        for vid in attached:
            v = conn.block_storage.get_volume(vid)
            flag = getattr(v, "is_bootable", getattr(v, "bootable", False))
            if str(flag).lower() == "true":
                return vid
    except Exception:  # noqa: BLE001 -- fake/edge conns lack block_storage
        pass
    # 4) last resort
    return attached[0] if attached else None


def _flavor_specs(conn, server) -> dict:
    fl = getattr(server, "flavor", None) or {}
    # Newer Nova embeds vcpus/ram/disk in server.flavor; otherwise look it up by id.
    if isinstance(fl, dict) and fl.get("vcpus") is not None:
        return {"vcpus": fl["vcpus"], "ram": fl["ram"], "disk": fl["disk"]}
    flavor_id = fl.get("id") if isinstance(fl, dict) else getattr(fl, "id", None)
    if flavor_id:
        f = conn.compute.get_flavor(flavor_id)
        return {"vcpus": f.vcpus, "ram": f.ram, "disk": f.disk}
    return {"vcpus": None, "ram": None, "disk": None}
