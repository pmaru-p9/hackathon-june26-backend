import pytest

from app.osclients.reauth import is_auth_error, reauth_on_expiry
from app.engine.runner import ReauthRequired


class Unauthorized(Exception):
    http_status = 401


class NotFound(Exception):
    http_status = 404


def test_is_auth_error_by_status_and_name():
    assert is_auth_error(Unauthorized()) is True
    assert is_auth_error(NotFound()) is False
    assert is_auth_error(RuntimeError("boom")) is False


def test_reauth_context_maps_401_to_reauth_required():
    with pytest.raises(ReauthRequired):
        with reauth_on_expiry():
            raise Unauthorized()


def test_reauth_context_passes_other_errors_through():
    with pytest.raises(NotFound):
        with reauth_on_expiry():
            raise NotFound()
