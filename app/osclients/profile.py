def build_migration_profile(source_conn, vm_id: str) -> dict:
    s = source_conn.server(vm_id)
    return {"vmId": s["id"], "bootVolumeBacked": s["boot_from_volume"],
            "rootVolumeId": s.get("root_volume_id"),
            "attachedVolumes": s["attached_volumes"],
            "flavorSpecs": s["flavor"], "securityGroups": s["security_groups"],
            "flavorId": s.get("flavor_id"), "availabilityZone": s.get("availability_zone"),
            "keyName": s["key_name"], "metadata": s["metadata"],
            "userData": s.get("user_data"), "configDrive": s.get("config_drive", False),
            "nics": [{"portId": n["port_id"], "networkId": n["network_id"],
                      "ip": n["ip"], "mac": n["mac"]} for n in s["nics"]]}
