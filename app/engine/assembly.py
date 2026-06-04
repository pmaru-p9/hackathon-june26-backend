"""Assemble a MigrationRunner for a given Migration CR: gather the source profile +
preflight context (live), resolve destination facts, build the plan, and bind a
ProductionEngine. The live client construction is injected (build_source_clients /
build_dest_clients) so this orchestration is unit-testable with fakes."""
from app.osclients.profile import build_migration_profile
from app.osclients.nova import match_flavor
from app.engine.production import build_context_from_profile, ProductionEngine
from app.engine.plan import build_plan
from app.engine.runner import MigrationRunner


def assemble_runner(mid, *, migrations, discovery, build_source_clients, build_dest_clients):
    cr = migrations.get(mid)
    spec = cr["spec"]
    vm_id = spec["source"]["vmId"]
    tok = migrations.read_source_token(mid)   # {token, authUrl, projectId}
    launch_body = {
        "vmIds": [vm_id], "destinationId": spec["destinationRef"],
        "targetProject": spec["targetProject"], "az": spec["az"],
        "networkMap": spec["networkMap"], "flavor": spec.get("flavor", {"auto": True}),
        "sourceCleanup": spec.get("sourceCleanup", "keepStopped"),
    }

    # Full source profile (for the plan) + scored profile -> preflight context (live).
    source = discovery.source_conn(tok["authUrl"], tok["token"], tok["projectId"])
    profile = build_migration_profile(source, vm_id)
    context = build_context_from_profile(
        discovery.assess(launch_body, tok["authUrl"], tok["token"], tok["projectId"]))

    # Resolve destination flavor (override or spec-match).
    specs = profile.get("flavorSpecs") or {}
    dest_flavor_id = spec.get("flavor", {}).get("overrideId")
    if not dest_flavor_id and all(specs.get(k) is not None for k in ("vcpus", "ram", "disk")):
        match = match_flavor(discovery.flavors(spec["destinationRef"]), **specs)
        dest_flavor_id = match["id"] if match else None

    src_nova, src_cinder = build_source_clients(tok)
    dst = build_dest_clients(spec["destinationRef"], spec["targetProject"])
    # dst: (nova, cinder, neutron, pool_host, volume_type)
    dst_nova, dst_cinder, dst_neutron, dest_pool_host, dest_volume_type = dst

    plan = build_plan(spec, profile, context, dest_flavor_id=dest_flavor_id,
                      dest_volume_type=dest_volume_type, dest_pool_host=dest_pool_host)
    engine = ProductionEngine(migrations, src_nova, src_cinder, dst_nova, dst_cinder,
                              dst_neutron, plan)
    return MigrationRunner(migrations, engine)
