from app.engine.preflight import run_preflight
from app.engine.base import MigrationContext


def make_ctx(**over):
    base = dict(is_admin=True, dest_reachable=True, volume_backed=True,
                shared_backend=True, resolved_volume_type="vt", flavor_match=True,
                ip_fits_and_free=True, mac_free=True, volumes_detachable=True,
                quota_ok=True)
    base.update(over)
    return MigrationContext(**base)


def test_all_pass():
    checks = run_preflight(make_ctx())
    assert all(c.passed for c in checks)


def test_not_volume_backed_fails_p3():
    checks = run_preflight(make_ctx(volume_backed=False))
    p3 = next(c for c in checks if c.id == "P3")
    assert p3.passed is False and "volume-backed" in p3.message.lower()


def test_ip_conflict_fails_p6():
    checks = run_preflight(make_ctx(ip_fits_and_free=False))
    assert next(c for c in checks if c.id == "P6").passed is False
