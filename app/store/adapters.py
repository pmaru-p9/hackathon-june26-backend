import base64

from app.store.crd import GROUP, VERSION, PLURALS


class K8sCustomObjectsAdapter:
    def __init__(self, api):
        self.api = api

    def create(self, ns, kind, body):
        self.api.create_namespaced_custom_object(GROUP, VERSION, ns, PLURALS[kind], body)

    def get(self, ns, kind, name):
        return self.api.get_namespaced_custom_object(GROUP, VERSION, ns, PLURALS[kind], name)

    def list(self, ns, kind):
        return self.api.list_namespaced_custom_object(
            GROUP, VERSION, ns, PLURALS[kind])["items"]

    def patch(self, ns, kind, name, body):
        self.api.patch_namespaced_custom_object(GROUP, VERSION, ns, PLURALS[kind], name, body)

    def delete(self, ns, kind, name):
        self.api.delete_namespaced_custom_object(GROUP, VERSION, ns, PLURALS[kind], name)


class K8sSecretsAdapter:
    def __init__(self, core):
        self.core = core

    def write(self, ns, name, kv):
        from kubernetes.client import V1Secret, V1ObjectMeta
        data = {k: base64.b64encode(v.encode()).decode() for k, v in kv.items()}
        body = V1Secret(metadata=V1ObjectMeta(name=name), data=data)
        try:
            self.core.create_namespaced_secret(ns, body)
        except Exception:  # noqa: BLE001 — secret may already exist; replace it
            self.core.replace_namespaced_secret(name, ns, body)

    def read(self, ns, name):
        s = self.core.read_namespaced_secret(name, ns)
        return {k: base64.b64decode(v).decode() for k, v in (s.data or {}).items()}

    def delete(self, ns, name):
        self.core.delete_namespaced_secret(name, ns)
