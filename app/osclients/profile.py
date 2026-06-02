def build_migration_profile(source_conn, vm_id: str) -> dict:
    s = source_conn.server(vm_id)
    return {"vmId": s["id"], "bootVolumeBacked": s["boot_from_volume"],
            "rootVolumeId": s.get("root_volume_id"),
            "attachedVolumes": s["attached_volumes"],
            "flavorSpecs": s["flavor"], "securityGroups": s["security_groups"],
            "keyName": s["key_name"], "metadata": s["metadata"],
            "nics": [{"portId": n["port_id"], "networkId": n["network_id"],
                      "ip": n["ip"], "mac": n["mac"]} for n in s["nics"]]}
