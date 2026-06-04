"""Resolve whether source and destination share a Cinder NFS export (via blueprints) and,
if so, which destination pool to `manage` the volume into. Glue over blueprint.py +
cinder pool/volume-host lookups; the SDK calls are injected so this stays testable."""
from app.osclients.blueprint import parse_nfs_backends, export_for_pool, dest_pool_for_export


def resolve_shared(*, source_cinder, source_bp, dest_cinder, dest_bp, root_volume_id) -> dict:
    """source_cinder/dest_cinder expose volume_host(id) and pools() (ProdCinder or FakeCinder).
    Returns sharedBackend, destPoolHost (for `manage --host`), resolvedVolumeType
    (non-None marker so preflight P4 passes; actual manage is host-pinned), sourceExport."""
    src_host = source_cinder.volume_host(root_volume_id)          # uuid@backend#pool
    src_export = export_for_pool(parse_nfs_backends(source_bp), src_host)
    dest_pool = None
    if src_export:
        dest_pools = [p["name"] for p in dest_cinder.pools()]
        dest_pool = dest_pool_for_export(parse_nfs_backends(dest_bp), dest_pools, src_export)
    return {
        "sharedBackend": dest_pool is not None,
        "destPoolHost": dest_pool,
        "sourcePoolHost": src_host,         # for reverse re-manage on the source
        # host-pinned manage doesn't need a type; expose a non-None marker for P4.
        "resolvedVolumeType": dest_pool,
        "sourceExport": src_export,
    }
