from types import SimpleNamespace as NS

from app.engine.assembly import assemble_runner
from app.osclients.nova import NovaOps
from app.osclients.cinder import CinderOps
from app.osclients.neutron import NeutronOps
from app.store.migrations import MigrationRepo
from tests.fakes.openstack import FakeNova, FakeCinder, FakeNeutron
from tests.fakes.k8s import FakeCustomObjects, FakeSecrets


SERVER = {
    "id": "s1", "flavor": {"vcpus": 1, "ram": 512, "disk": 0},
    "security_groups": [{"name": "default"}], "key_name": None, "metadata": {},
    "attached_volumes": [{"id": "v1"}], "boot_from_volume": True, "root_volume_id": "v1",
    "block_device_mapping": [{"boot_index": 0, "volume_id": "v1"}],
    "nics": [{"port_id": "p1", "network_id": "n1", "ip": "10.0.0.5", "mac": "fa:16:3e:00:00:01"}],
}


class FakeDiscovery:
    def source_conn(self, url, token, pid):
        return NS(server=lambda vid: {
            "id": SERVER["id"], "boot_from_volume": True, "root_volume_id": "v1",
            "attached_volumes": ["v1"], "flavor": SERVER["flavor"],
            "security_groups": ["default"], "key_name": None, "metadata": {},
            "nics": [{"port_id": "p1", "network_id": "n1", "ip": "10.0.0.5",
                      "mac": "fa:16:3e:00:00:01"}]})

    def assess(self, body, url, token, pid):
        # shared_backend False -> preflight P4 must fail (fail-safe default)
        return {"bootVolumeBacked": True, "isAdmin": False, "destReachable": True,
                "sharedBackend": False, "resolvedVolumeType": None, "flavorMatch": True,
                "volumesDetachable": True, "quotaOk": True,
                "nics": [{"ip": "10.0.0.5", "destFits": True, "macFree": True}]}

    def flavors(self, did):
        return [{"id": "f1", "name": "s", "vcpus": 1, "ram": 512, "disk": 0}]


def test_assemble_runner_runs_preflight_and_fails_safe():
    repo = MigrationRepo(FakeCustomObjects(), FakeSecrets(), namespace="ns")
    m = repo.create("s1", "db", "d1", "proj", "az1",
                    [{"sourcePortId": "p1", "destNetworkId": "n1", "ip": "10.0.0.5",
                      "mac": "fa:16:3e:00:00:01"}], {"auto": True}, {}, "keepStopped")
    repo.store_source_token(m["id"], "TKN", "http://src/v3", "pid")

    runner = assemble_runner(
        m["id"], migrations=repo, discovery=FakeDiscovery(),
        build_source_clients=lambda tok: (NovaOps(FakeNova()), CinderOps(FakeCinder())),
        build_dest_clients=lambda did, proj: (
            NovaOps(FakeNova()), CinderOps(FakeCinder()), NeutronOps(FakeNeutron()),
            "h@be#pool", "vt"))
    runner.run(m["id"])

    st = repo.get(m["id"])["status"]
    assert st["phase"] == "Failed" and "preflight" in st["message"]
