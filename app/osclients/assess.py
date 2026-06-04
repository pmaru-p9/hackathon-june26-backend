"""Pure scoring: turn the discovered source profile + gathered destination facts into
the profile dict consumed by app.engine.production.build_context_from_profile (which
feeds preflight P1-P8). The live assess() in DiscoveryService gathers the facts; this
function holds the testable per-NIC IP-fit / MAC-free logic."""
from app.osclients.neutron import ip_in_cidr


def score_profile(source_profile: dict, network_map: dict, dest_subnets: list,
                  dest_macs_in_use, *, is_admin: bool, dest_reachable: bool,
                  shared_backend: bool, resolved_volume_type, flavor_match: bool,
                  volumes_detachable: bool, quota_ok: bool) -> dict:
    macs = set(dest_macs_in_use or [])
    nics = []
    for nic in source_profile.get("nics", []):
        dest_net = network_map.get(nic["portId"])
        fits = False
        for s in dest_subnets:
            if s["network_id"] == dest_net and ip_in_cidr(nic["ip"], s["cidr"]):
                fits = nic["ip"] not in set(s.get("allocated", set()))
                break
        nics.append({"ip": nic["ip"], "destFits": fits, "macFree": nic["mac"] not in macs})
    return {
        "bootVolumeBacked": source_profile["bootVolumeBacked"],
        "isAdmin": is_admin,
        "destReachable": dest_reachable,
        "sharedBackend": shared_backend,
        "resolvedVolumeType": resolved_volume_type,
        "flavorMatch": flavor_match,
        "volumesDetachable": volumes_detachable,
        "quotaOk": quota_ok,
        "nics": nics,
    }
