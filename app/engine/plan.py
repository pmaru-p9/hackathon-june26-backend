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
    dot_original: bool = False
    source_flavor_id: str = None       # original source flavor (for reverse migration)
    source_az: str = None              # original source AZ (for reverse migration)
    source_pool_host: str = None       # source cinder pool host (for reverse re-manage)


def build_plan(migration_spec: dict, source_profile: dict, context: MigrationContext, *,
               dest_flavor_id: str, dest_volume_type: str, dest_pool_host: str,
               dot_original: bool = False, source_pool_host: str = None) -> MigrationPlan:
    src_net_by_port = {n["portId"]: n.get("networkId") for n in source_profile.get("nics", [])}
    return MigrationPlan(
        context=context,
        # destNetworkId is where the dest port is created (cutover); sourceNetworkId is the
        # original network, needed to recreate the source port during reverse migration.
        network_map=[{"destNetworkId": n["destNetworkId"],
                      "sourceNetworkId": src_net_by_port.get(n["sourcePortId"]),
                      "ip": n["ip"], "mac": n["mac"]}
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
        # boot-from-volume is always a true move; the source instance is deleted to free
        # the root volume, so keepStopped does not apply.
        source_cleanup="delete",
        image_meta=source_profile.get("imageMeta", {}),
        dot_original=dot_original,
        source_flavor_id=source_profile.get("flavorId"),
        source_az=source_profile.get("availabilityZone"),
        source_pool_host=source_pool_host,
    )
