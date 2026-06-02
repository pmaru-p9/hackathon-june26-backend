"""Translate a discovered migration-profile (built from live OpenStack calls) into a
MigrationContext for preflight, and provide a ProductionEngine that records each step
incrementally so the runner's rollback uses the true last-completed step.

Client responsibilities (cross-cloud):
  - source clients (src_nova, src_cinder) perform C1 stop, C2 detach, C3 unmanage
  - dest clients (dst_cinder, dst_nova) perform C4 manage, C5 create-server
  - dst_neutron pre-creates ports in staging
The single-client `cutover()` helper from app.engine.cutover is used for the
shared-backend happy path where stop/detach/unmanage run on the source; the dest
manage/create are driven via the dest clients carried in `plan["cutoverArgs"]`.
The end-to-end source/dest split is exercised by the gated live suite (A-INT)."""
from app.engine.base import MigrationContext
from app.engine import staging, cutover, verify, rollback as rb


def build_context_from_profile(p: dict) -> MigrationContext:
    nics = p.get("nics", [])
    return MigrationContext(
        is_admin=p["isAdmin"], dest_reachable=p["destReachable"],
        volume_backed=p["bootVolumeBacked"], shared_backend=p["sharedBackend"],
        resolved_volume_type=p.get("resolvedVolumeType"), flavor_match=p["flavorMatch"],
        ip_fits_and_free=all(n["destFits"] for n in nics),
        mac_free=all(n["macFree"] for n in nics),
        volumes_detachable=p["volumesDetachable"], quota_ok=p["quotaOk"])


class ProductionEngine:
    """Binds OpenStack clients + a per-migration plan. Each phase method records its
    steps into the repo immediately so failures leave accurate checkpoints."""

    def __init__(self, repo, src_nova, src_cinder, dst_nova, dst_cinder, dst_neutron, plan):
        self.repo = repo
        self.src_nova = src_nova
        self.src_cinder = src_cinder
        self.dst_nova = dst_nova
        self.dst_cinder = dst_cinder
        self.dst_neutron = dst_neutron
        self.plan = plan

    @staticmethod
    def _mid(m):
        return m["metadata"]["name"] if "metadata" in m else m["id"]

    def preflight(self, m):
        from app.engine.preflight import run_preflight, preflight_passed
        checks = run_preflight(self.plan["context"])
        return preflight_passed(checks), checks

    def stage(self, m):
        mid = self._mid(m)
        res = staging.stage_ports(self.dst_neutron, self.plan["networkMap"])
        self.repo.checkpoint(mid, res.step, "done" if res.ok else "failed", res.checkpoint)
        return []  # already recorded

    def cutover(self, m):
        mid = self._mid(m)
        for res in cutover.cutover(self.src_nova, self.src_cinder, **self.plan["cutoverArgs"]):
            self.repo.checkpoint(mid, res.step, "done" if res.ok else "failed", res.checkpoint)
        return []

    def verify(self, m):
        mid = self._mid(m)
        for res in verify.verify_and_cleanup(self.src_nova, self.plan["destServerId"],
                                             self.plan["sourceServerId"],
                                             self.plan["sourceCleanup"]):
            self.repo.checkpoint(mid, res.step, "done", res.checkpoint)
        return []

    def rollback(self, m, failed_at, checkpoints):
        rb.rollback(self.src_nova, self.dst_cinder, self.dst_neutron, failed_at=failed_at,
                    checkpoints=checkpoints, source_server_id=self.plan["sourceServerId"],
                    source_host=self.plan["sourceHost"], attach_order=self.plan["attachOrder"])
