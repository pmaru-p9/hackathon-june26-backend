class ReauthRequired(Exception):
    ...


class MigrationRunner:
    """Drives a Migration through phases, persisting checkpoints. `engine` exposes
    preflight/stage/cutover/verify/rollback bound to the right OpenStack clients."""

    def __init__(self, repo, engine):
        self.repo = repo
        self.engine = engine

    def _record(self, mid, steps):
        for name, data in steps:
            self.repo.checkpoint(mid, step=name, state="done", data=data)

    def _cancelled(self, mid: str) -> bool:
        # Cooperative cancellation: the cancel endpoint sets phase=Failed with this message.
        st = self.repo.get(mid)["status"]
        return st["phase"] == "Failed" and "cancelled" in (st.get("message") or "").lower()

    def run(self, mid: str) -> None:
        m = self.repo.get(mid)
        try:
            self.repo.set_phase(mid, "Preflight")
            ok, checks = self.engine.preflight(m)
            if not ok:
                self.repo.set_phase(mid, "Failed", "preflight failed")
                return
            if self._cancelled(mid):
                return

            self.repo.set_phase(mid, "Staging")
            self._record(mid, self.engine.stage(m))
            # Last safe point to honour a cancel — once cutover starts we never abort.
            if self._cancelled(mid):
                checkpoints = self._checkpoints(mid)
                self.engine.rollback(m, failed_at="S1", checkpoints=checkpoints)
                self.repo.set_phase(mid, "RolledBack", "cancelled before cutover")
                return

            self.repo.set_phase(mid, "Cutover")
            self._record(mid, self.engine.cutover(m))
            self.repo.set_phase(mid, "Verifying")
            self._record(mid, self.engine.verify(m))
            self.repo.set_phase(mid, "Completed")
        except ReauthRequired:
            self.repo.set_phase(mid, "NeedsReauth", "source token expired")
        except Exception as exc:  # noqa: BLE001
            steps = [s["name"] for s in self.repo.get(mid)["status"]["steps"]]
            # Once the destination VM exists (C5) or we are verifying, auto-rollback is
            # unsafe — a human must reconcile. Never tear down a live destination VM.
            if "C5" in steps or self._last_step(mid) in ("V1", "V2"):
                self.repo.set_phase(mid, "NeedsAttention", f"post-create failure: {exc}")
            else:
                checkpoints = self._checkpoints(mid)
                self.engine.rollback(m, failed_at=self._last_step(mid) or "Preflight",
                                     checkpoints=checkpoints)
                self.repo.set_phase(mid, "RolledBack", str(exc))
        finally:
            # Drop the stored source token on every terminal state except NeedsReauth
            # (which needs it preserved so /reauth can resume).
            if self.repo.get(mid)["status"]["phase"] != "NeedsReauth":
                self.repo.clear_source_token(mid)

    def _last_step(self, mid):
        steps = self.repo.get(mid)["status"]["steps"]
        return steps[-1]["name"] if steps else None

    def _checkpoints(self, mid):
        return {s["name"]: s["checkpoint"] for s in self.repo.get(mid)["status"]["steps"]}

    def resume_inflight(self, namespace_migrations: list) -> list[str]:
        """Called on startup: any Migration left in a non-terminal phase is resumed."""
        terminal = {"Completed", "Failed", "RolledBack", "NeedsAttention"}
        resumed = []
        for m in namespace_migrations:
            if m["status"]["phase"] not in terminal | {"NeedsReauth"}:
                resumed.append(m["metadata"]["name"])
        return resumed
