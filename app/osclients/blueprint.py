"""Read a PCD resmgr Cluster Blueprint and resolve NFS backend export paths, so the POD
can confirm two clouds share a Cinder export (fast, no manageable-list scan) and pick the
destination pool that mounts the same export.

Blueprint shape (root may be a list):
  {"storageBackends": {"<category>": {"<backend>": {"config": {"nfs_mount_points": "h:/p"}}}}}
A cinder pool host string is "<host-uuid>@<backend>#<pool>"; in PCD the pool segment
matches the blueprint <category> and the backend segment matches <backend>."""


def parse_nfs_backends(blueprint) -> dict:
    """-> {(category, backend): nfs_mount_points}"""
    root = blueprint[0] if isinstance(blueprint, list) else blueprint
    sb = (root or {}).get("storageBackends", {}) or {}
    out = {}
    for category, backends in sb.items():
        if not isinstance(backends, dict):
            continue
        for backend, spec in backends.items():
            mp = ((spec or {}).get("config") or {}).get("nfs_mount_points")
            if mp:
                out[(category, backend)] = mp
    return out


def _split_pool(pool_host: str):
    """'uuid@backend#pool' -> (backend, pool)"""
    backend = pool_host.split("@")[-1].split("#")[0]
    pool = pool_host.split("#")[-1] if "#" in pool_host else None
    return backend, pool


def export_for_pool(nfs_backends: dict, pool_host: str):
    """The NFS export a given cinder pool mounts, via the blueprint mapping. The cinder
    pool 'uuid@<backend>#<pool>' maps to blueprint (category==pool, backend==backend).
    Require both to disambiguate when a backend name repeats across categories; fall back
    to a unique single-field match only if the strict match finds nothing."""
    backend, pool = _split_pool(pool_host)
    for (category, bk), export in nfs_backends.items():
        if category == pool and bk == backend:
            return export
    # fallbacks for blueprints that don't follow the category==pool convention
    by_backend = [e for (c, bk), e in nfs_backends.items() if bk == backend]
    if len(by_backend) == 1:
        return by_backend[0]
    by_pool = [e for (c, bk), e in nfs_backends.items() if c == pool]
    if len(by_pool) == 1:
        return by_pool[0]
    return None


def dest_pool_for_export(dest_nfs_backends: dict, dest_pool_hosts: list, source_export: str):
    """Pick the destination cinder pool host that mounts `source_export`. Returns the
    pool host string (for `cinder manage --host`) or None if no shared export."""
    for ph in dest_pool_hosts:
        if export_for_pool(dest_nfs_backends, ph) == source_export:
            return ph
    return None


def fetch_blueprint(base_url: str, token: str):
    """Live: GET {base_url}/resmgr/v2/blueprint with a Keystone token."""
    import json
    import urllib.request
    req = urllib.request.Request(base_url.rstrip("/") + "/resmgr/v2/blueprint",
                                 headers={"X-Auth-Token": token, "Accept": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
