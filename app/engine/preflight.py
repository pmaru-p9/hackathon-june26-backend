from app.engine.base import Check, MigrationContext


def run_preflight(ctx: MigrationContext) -> list[Check]:
    return [
        Check("P1", ctx.is_admin, "user must hold admin role on source"),
        Check("P2", ctx.dest_reachable, "destination must be reachable with valid creds"),
        Check("P3", ctx.volume_backed, "VM must be volume-backed (boot-from-volume)"),
        Check("P4", ctx.shared_backend and ctx.resolved_volume_type is not None,
              "shared backend must be confirmed and a destination volume type resolved"),
        Check("P5", ctx.flavor_match, "a matching destination flavor must exist or be chosen"),
        Check("P6", ctx.ip_fits_and_free,
              "destination subnet must hold the fixed IP and it must be free"),
        Check("P7", ctx.volumes_detachable, "volumes must be detachable (no pending tasks)"),
        Check("P8", ctx.quota_ok, "destination quota must be sufficient"),
        Check("P9", ctx.dot_readable and (not ctx.dot_is_true or ctx.dot_flippable),
              "root delete_on_termination must be readable (Nova>=2.79) and, if True, "
              "updatable (Nova>=2.85) so the source instance can be safely deleted"),
    ]


def preflight_passed(checks: list[Check]) -> bool:
    return all(c.passed for c in checks)
