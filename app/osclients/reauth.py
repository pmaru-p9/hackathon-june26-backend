"""Map OpenStack auth failures (expired/invalid source token) to ReauthRequired so the
runner pauses in NeedsReauth between steps instead of falling into a destructive rollback."""
from contextlib import contextmanager

from app.engine.runner import ReauthRequired


def is_auth_error(exc: Exception) -> bool:
    # keystoneauth1 / openstacksdk raise classes named *Unauthorized with http_status 401.
    status = getattr(exc, "http_status", None) or getattr(exc, "status_code", None)
    if status == 401:
        return True
    name = type(exc).__name__.lower()
    return "unauthorized" in name or "authorizationfailure" in name


@contextmanager
def reauth_on_expiry():
    """Wrap source-side OpenStack calls: a 401/auth failure becomes ReauthRequired."""
    try:
        yield
    except ReauthRequired:
        raise
    except Exception as exc:  # noqa: BLE001
        if is_auth_error(exc):
            raise ReauthRequired(str(exc)) from exc
        raise
