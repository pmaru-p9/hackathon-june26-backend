"""Normalize the X-Auth-Url header into an absolute Keystone v3 URL.

The PCD-UI sends a RELATIVE auth URL (e.g. `/keystone`) because the browser resolves it
against the DU origin. Server-side, openstacksdk needs an ABSOLUTE url or endpoint
discovery fails with EndpointNotFound. The POD is co-located with Keystone on the DU, so
we rebuild the absolute URL from the request's own host when a relative value is sent, and
ensure the `/v3` suffix.
"""
from fastapi import Request


def normalize_auth_url(x_auth_url: str, request: Request) -> str:
    u = (x_auth_url or "").strip()
    if not u.lower().startswith("http"):           # relative (e.g. "/keystone")
        host = request.headers.get("host", "")
        scheme = request.headers.get("x-forwarded-proto", "https")
        path = u if u.startswith("/") else "/" + u
        u = f"{scheme}://{host}{path}"
    if not u.rstrip("/").endswith("/v3"):           # ensure Keystone v3
        u = u.rstrip("/") + "/v3"
    return u
