import uuid

from app.store.crd import CrdStore
from app.store.secrets import SecretStore


class DestinationRepo:
    def __init__(self, co_client, sec_client, namespace):
        self.crd = CrdStore(co_client)
        self.sec = SecretStore(sec_client)
        self.ns = namespace

    def _id(self):
        return uuid.uuid4().hex[:8]

    def create(self, name, auth_url, region, project_name, user_domain, project_domain,
               username, password):
        did = self._id()
        secret_name = f"dest-pcd-{did}"
        self.sec.write(self.ns, secret_name,
                       {"username": username, "password": password,
                        "project_name": project_name, "user_domain": user_domain,
                        "project_domain": project_domain})
        body = {"metadata": {"name": did},
                "spec": {"name": name, "authUrl": auth_url, "region": region,
                         "projectName": project_name, "userDomain": user_domain,
                         "projectDomain": project_domain, "credentialsSecretRef": secret_name},
                "status": {"reachable": None, "message": ""}}
        self.crd.create(self.ns, "DestinationPCD", body)
        return {"id": did, **body["spec"]}

    def list(self):
        return self.crd.list(self.ns, "DestinationPCD")

    def get(self, did):
        return self.crd.get(self.ns, "DestinationPCD", did)

    def creds(self, did):
        ref = self.get(did)["spec"]["credentialsSecretRef"]
        return self.sec.read(self.ns, ref)

    def set_status(self, did, reachable, message):
        self.crd.patch(self.ns, "DestinationPCD", did,
                       {"status": {"reachable": reachable, "message": message}})

    def delete(self, did):
        ref = self.get(did)["spec"]["credentialsSecretRef"]
        self.sec.delete(self.ns, ref)
        self.crd.delete(self.ns, "DestinationPCD", did)
