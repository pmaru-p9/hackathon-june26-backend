import pytest

from app import deps


@pytest.fixture(autouse=True)
def _reset_injected_repos():
    """deps._state is a process-global set by set_repos(); reset it between tests so a
    repo/discovery injected by one test never leaks into another."""
    deps._state = {"destinations": None, "migrations": None, "discovery": None}
    yield
    deps._state = {"destinations": None, "migrations": None, "discovery": None}
