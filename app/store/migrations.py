import uuid

from app.store.crd import CrdStore
from app.store.secrets import SecretStore


class MigrationRepo:
    def __init__(self, co_client, sec_client, namespace):
        self.crd = CrdStore(co_client)
        self.sec = SecretStore(sec_client)
        self.ns = namespace

    def create(self, vm_id, vm_name, destination_ref, target_project, az, network_map,
               flavor, preserve, source_cleanup):
        mid = uuid.uuid4().hex[:8]
        body = {"metadata": {"name": mid},
                "spec": {"source": {"vmId": vm_id, "vmName": vm_name},
                         "destinationRef": destination_ref, "targetProject": target_project,
                         "az": az, "networkMap": network_map, "flavor": flavor,
                         "preserve": preserve, "sourceCleanup": source_cleanup,
                         "engine": {"type": "sharedBackend"}},
                "status": {"phase": "Pending", "steps": [], "message": ""}}
        self.crd.create(self.ns, "Migration", body)
        return {"id": mid, **body["spec"]}

    def get(self, mid):
        return self.crd.get(self.ns, "Migration", mid)

    def list(self):
        return self.crd.list(self.ns, "Migration")

    def set_phase(self, mid, phase, message=""):
        cur = self.get(mid)
        cur["status"]["phase"] = phase
        cur["status"]["message"] = message
        self.crd.patch(self.ns, "Migration", mid, {"status": cur["status"]})

    def checkpoint(self, mid, step, state, data=None):
        cur = self.get(mid)
        cur["status"]["steps"].append({"name": step, "state": state, "checkpoint": data or {}})
        self.crd.patch(self.ns, "Migration", mid, {"status": cur["status"]})

    def store_source_token(self, mid, token, auth_url, project_id):
        self.sec.write(self.ns, f"mig-token-{mid}",
                       {"token": token, "authUrl": auth_url, "projectId": project_id})

    def read_source_token(self, mid):
        return self.sec.read(self.ns, f"mig-token-{mid}")

    def clear_source_token(self, mid):
        self.sec.delete(self.ns, f"mig-token-{mid}")
