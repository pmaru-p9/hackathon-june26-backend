from types import SimpleNamespace

from app.api.authurl import normalize_auth_url


def _req(host="du.example.com", proto=None):
    h = {"host": host}
    if proto:
        h["x-forwarded-proto"] = proto
    return SimpleNamespace(headers=h)


def test_relative_auth_url_becomes_absolute_v3():
    # the PCD-UI sends "/keystone"; must resolve against the request host + add /v3
    assert normalize_auth_url("/keystone", _req()) == "https://du.example.com/keystone/v3"


def test_absolute_url_missing_v3_gets_v3():
    assert normalize_auth_url("https://du.example.com/keystone", _req()) == \
        "https://du.example.com/keystone/v3"


def test_absolute_v3_url_unchanged():
    u = "https://du.example.com/keystone/v3"
    assert normalize_auth_url(u, _req()) == u


def test_respects_forwarded_proto():
    assert normalize_auth_url("/keystone", _req(proto="https")).startswith("https://")
