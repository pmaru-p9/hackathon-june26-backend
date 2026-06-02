from app.store import adapters


def test_adapters_expose_fake_compatible_methods():
    co = adapters.K8sCustomObjectsAdapter.__dict__
    for m in ("create", "get", "list", "patch", "delete"):
        assert m in co
    sec = adapters.K8sSecretsAdapter.__dict__
    for m in ("read", "write", "delete"):
        assert m in sec
