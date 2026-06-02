from app.osclients.profile import build_migration_profile


class FakeSourceConn:
    def server(self, vid):
        return {"id": vid, "flavor": {"vcpus": 4, "ram": 8192, "disk": 40},
                "security_groups": ["default"], "key_name": "kp", "metadata": {"a": "b"},
                "attached_volumes": ["v-root", "v-data"], "boot_from_volume": True,
                "root_volume_id": "v-root",
                "nics": [{"port_id": "p1", "network_id": "n1", "ip": "10.20.0.15",
                          "mac": "fa:16:3e:aa:11"}]}


def test_profile_marks_volume_backed_and_lists_nics():
    prof = build_migration_profile(FakeSourceConn(), "vmX")
    assert prof["bootVolumeBacked"] is True
    assert prof["rootVolumeId"] == "v-root"
    assert len(prof["nics"]) == 1 and prof["nics"][0]["ip"] == "10.20.0.15"
    assert prof["flavorSpecs"] == {"vcpus": 4, "ram": 8192, "disk": 40}
