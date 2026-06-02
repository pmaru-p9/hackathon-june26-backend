"""Holds injectable repos/clients. Tests call set_repos() with fakes; production
wires real kubernetes + openstack clients at startup (Task A16)."""
_state = {"destinations": None, "migrations": None, "discovery": None}


def set_repos(**kw):
    _state.update({k: v for k, v in kw.items() if v is not None})


def get_destinations():
    return _state["destinations"]


def get_migrations():
    return _state["migrations"]


def get_discovery():
    return _state["discovery"]
