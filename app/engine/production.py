"""Translate a discovered migration-profile (built from live OpenStack calls) into a
MigrationContext for preflight, and provide a ProductionEngine that records each step
incrementally so the runner's rollback uses the true last-completed step.

Client responsibilities (cross-cloud):
  - source clients (src_nova, src_cinder) perform C1 stop, C2 detach, C3 unmanage
  - dest clients (dst_cinder, dst_nova) perform C4 manage, C5 create-server
  - dst_neutron pre-creates ports in staging
The `cutover()` generator takes both source and destination clients and yields each
StepResult as it completes, so failures leave accurate checkpoints. The end-to-end
source/dest split is exercised by the gated live suite (A-INT)."""
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
        volumes_detachable=p["volumesDetachable"], quota_ok=p["quotaOk"],
        dot_readable=p.get("dotReadable", False), dot_is_true=p.get("dotIsTrue", False),
        dot_flippable=p.get("dotFlippable", False))


class ProductionEngine:
    """Binds OpenStack clients + a MigrationPlan. Records each step into the repo as it
    completes (so failures leave accurate checkpoints) and threads runtime values
    (staged port ids → cutover; created dest server id → verify)."""

    def __init__(self, repo, src_nova, src_cinder, dst_nova, dst_cinder, dst_neutron, plan):
        self.repo = repo
        self.src_nova = src_nova
        self.src_cinder = src_cinder
        self.dst_nova = dst_nova
        self.dst_cinder = dst_cinder
        self.dst_neutron = dst_neutron
        self.plan = plan
        self._dest_port_ids = []
        self._dest_server_id = None

    @staticmethod
    def _mid(m):
        return m["metadata"]["name"] if "metadata" in m else m["id"]

    def preflight(self, m):
        from app.engine.preflight import run_preflight, preflight_passed
        checks = run_preflight(self.plan.context)
        return preflight_passed(checks), checks

    def stage(self, m):
        mid = self._mid(m)
        res = staging.stage_ports(self.dst_neutron, self.plan.network_map)
        self._dest_port_ids = res.checkpoint["destPortIds"]
        self.repo.checkpoint(mid, res.step, "done" if res.ok else "failed", res.checkpoint)
        return []

    def cutover(self, m):
        mid = self._mid(m)
        p = self.plan
        # C1-C3 on source clients, C4-C5 on destination clients (shared backend).
        for res in cutover.cutover(
                self.src_nova, self.src_cinder, self.dst_nova, self.dst_cinder,
                server_id=p.server_id, volume_ids=p.volume_ids,
                dest_port_ids=self._dest_port_ids, flavor_id=p.flavor_id, az=p.az,
                volume_type=p.volume_type, sgs=p.sgs, keypair=p.keypair, metadata=p.metadata,
                name=p.name, root_volume_id=p.root_volume_id, image_meta=p.image_meta):
            if res.step == "C5":
                self._dest_server_id = res.checkpoint["destServerId"]
            self.repo.checkpoint(mid, res.step, "done" if res.ok else "failed", res.checkpoint)
        return []

    def verify(self, m):
        mid = self._mid(m)
        for res in verify.verify_and_cleanup(self.dst_nova, self.src_nova,
                                             self._dest_server_id, self.plan.server_id,
                                             self.plan.source_cleanup):
            self.repo.checkpoint(mid, res.step, "done", res.checkpoint)
        return []

    def rollback(self, m, failed_at, checkpoints):
        rb.rollback(self.src_nova, self.dst_cinder, self.dst_neutron, failed_at=failed_at,
                    checkpoints=checkpoints, source_server_id=self.plan.server_id,
                    source_host=self.plan.source_host, attach_order=self.plan.attach_order)
