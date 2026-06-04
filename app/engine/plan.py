"""Assemble the static MigrationPlan consumed by ProductionEngine from a Migration CR
spec + the discovered source profile + resolved destination facts. Pure / unit-testable."""
from dataclasses import dataclass, field

from app.engine.base import MigrationContext


@dataclass
class MigrationPlan:
    context: MigrationContext
    network_map: list           # [{destNetworkId, ip, mac}] for stage_ports
    server_id: str              # source server id
    volume_ids: list
    root_volume_id: str
    volume_type: str            # resolved destination volume type
    az: str
    flavor_id: str
    sgs: list
    keypair: str
    metadata: dict
    name: str
    source_host: str            # destination cinder pool host (for manage / re-manage)
    attach_order: list
    source_cleanup: str
    image_meta: dict = field(default_factory=dict)


def build_plan(migration_spec: dict, source_profile: dict, context: MigrationContext, *,
               dest_flavor_id: str, dest_volume_type: str, dest_pool_host: str) -> MigrationPlan:
    return MigrationPlan(
        context=context,
        network_map=[{"destNetworkId": n["destNetworkId"], "ip": n["ip"], "mac": n["mac"]}
                     for n in migration_spec.get("networkMap", [])],
        server_id=source_profile["vmId"],
        volume_ids=list(source_profile["attachedVolumes"]),
        root_volume_id=source_profile["rootVolumeId"],
        volume_type=dest_volume_type,
        az=migration_spec["az"],
        flavor_id=dest_flavor_id,
        sgs=list(source_profile.get("securityGroups", [])),
        keypair=source_profile.get("keyName"),
        metadata=dict(source_profile.get("metadata", {})),
        name=migration_spec.get("source", {}).get("vmName", source_profile["vmId"]),
        source_host=dest_pool_host,
        attach_order=list(source_profile["attachedVolumes"]),
        source_cleanup=migration_spec.get("sourceCleanup", "keepStopped"),
        image_meta=source_profile.get("imageMeta", {}),
    )
