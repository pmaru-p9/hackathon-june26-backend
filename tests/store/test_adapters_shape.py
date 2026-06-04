from app.store import adapters


class _RecordingApi:
    def __init__(self):
        self.created = None

    def create_namespaced_custom_object(self, group, version, ns, plural, body):
        self.created = (group, version, ns, plural, body)


def test_create_injects_apiversion_and_kind():
    api = _RecordingApi()
    adapters.K8sCustomObjectsAdapter(api).create(
        "ns", "DestinationPCD", {"metadata": {"name": "d1"}, "spec": {}})
    _, _, _, plural, body = api.created
    assert plural == "destinationpcds"
    assert body["apiVersion"] == "migration.pf9.io/v1alpha1"
    assert body["kind"] == "DestinationPCD"
    assert body["metadata"]["name"] == "d1"


def test_adapters_expose_fake_compatible_methods():
    co = adapters.K8sCustomObjectsAdapter.__dict__
    for m in ("create", "get", "list", "patch", "delete"):
        assert m in co
    sec = adapters.K8sSecretsAdapter.__dict__
    for m in ("read", "write", "delete"):
        assert m in sec
