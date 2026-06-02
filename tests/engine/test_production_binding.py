from app.engine.production import build_context_from_profile


def test_build_context_flags_volume_backed_and_ip_fit():
    profile = {"bootVolumeBacked": True, "isAdmin": True,
               "nics": [{"ip": "10.20.0.15", "destFits": True, "macFree": True}],
               "sharedBackend": True, "resolvedVolumeType": "vt",
               "flavorMatch": True, "volumesDetachable": True, "quotaOk": True,
               "destReachable": True}
    ctx = build_context_from_profile(profile)
    assert ctx.volume_backed and ctx.ip_fits_and_free and ctx.resolved_volume_type == "vt"
