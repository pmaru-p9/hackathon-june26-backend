from app.osclients.assess import score_profile
from app.engine.production import build_context_from_profile
from app.engine.preflight import run_preflight, preflight_passed


SRC = {
    "bootVolumeBacked": True,
    "nics": [{"portId": "p1", "networkId": "n1", "ip": "10.20.0.15", "mac": "fa:16:3e:aa:11"}],
}


def test_score_profile_all_good_yields_passing_context():
    prof = score_profile(
        SRC, network_map={"p1": "netD"},
        dest_subnets=[{"network_id": "netD", "cidr": "10.20.0.0/24", "allocated": []}],
        dest_macs_in_use=[], is_admin=True, dest_reachable=True, shared_backend=True,
        resolved_volume_type="vt", flavor_match=True, volumes_detachable=True, quota_ok=True,
        dot_readable=True, dot_is_true=False, dot_flippable=True)
    assert prof["nics"][0]["destFits"] is True and prof["nics"][0]["macFree"] is True
    assert preflight_passed(run_preflight(build_context_from_profile(prof)))


def test_score_profile_passes_through_dot_fields():
    p = score_profile(SRC, network_map={"p1": "netD"},
        dest_subnets=[{"network_id": "netD", "cidr": "10.20.0.0/24", "allocated": []}],
        dest_macs_in_use=[], is_admin=True, dest_reachable=True, shared_backend=True,
        resolved_volume_type="vt", flavor_match=True, volumes_detachable=True, quota_ok=True,
        dot_readable=True, dot_is_true=True, dot_flippable=True)
    assert p["dotReadable"] is True and p["dotIsTrue"] is True and p["dotFlippable"] is True


def test_score_profile_ip_in_use_fails_fit():
    prof = score_profile(
        SRC, network_map={"p1": "netD"},
        dest_subnets=[{"network_id": "netD", "cidr": "10.20.0.0/24",
                       "allocated": ["10.20.0.15"]}],
        dest_macs_in_use=["fa:16:3e:aa:11"], is_admin=True, dest_reachable=True,
        shared_backend=True, resolved_volume_type="vt", flavor_match=True,
        volumes_detachable=True, quota_ok=True)
    assert prof["nics"][0]["destFits"] is False
    assert prof["nics"][0]["macFree"] is False
    checks = run_preflight(build_context_from_profile(prof))
    assert not preflight_passed(checks)
    assert next(c for c in checks if c.id == "P6").passed is False
