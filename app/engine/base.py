from dataclasses import dataclass, field


@dataclass
class MigrationContext:
    is_admin: bool = False
    dest_reachable: bool = False
    volume_backed: bool = False
    shared_backend: bool = False
    resolved_volume_type: str | None = None
    flavor_match: bool = False
    ip_fits_and_free: bool = False
    mac_free: bool = False
    volumes_detachable: bool = False
    quota_ok: bool = False
    dot_readable: bool = False
    dot_is_true: bool = False
    dot_flippable: bool = False


@dataclass
class Check:
    id: str
    passed: bool
    message: str


@dataclass
class StepResult:
    step: str
    ok: bool
    checkpoint: dict = field(default_factory=dict)
    error: str = ""
