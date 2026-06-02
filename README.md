# pcd-migration

Migration POD for shared-backend, minimal-downtime VM moves between two PCD
(OpenStack) clouds. Moves a **volume-backed** VM by handing Cinder volume management
over (`unmanage` on source → `manage` on destination) with no data copy.

See the design spec and plan in the parent repo under
`docs/superpowers/specs/` and `docs/superpowers/plans/`.

## Layout
- `app/osclients/` — OpenStack client wrappers (cinder/nova/neutron/discovery/profile, sessions)
- `app/store/` — CRD + Secret repositories (DestinationPCD, Migration) and k8s adapters
- `app/engine/` — preflight (P1–P8) → staging → cutover (C1–C5) → verify, runner, rollback
- `app/api/` — FastAPI routes (destinations, source profile, migrations)
- `deploy/` — CRDs + Helm chart + RBAC

## Develop / test
```bash
python3.11 -m venv .venv311 && ./.venv311/bin/pip install -e ".[dev]"
./.venv311/bin/python -m pytest -q       # unit tests (no live infra)
./.venv311/bin/ruff check .
PCD_LIVE=1 ./.venv311/bin/python -m pytest tests/integration -v   # gated live suite
```

## Safety invariants (enforced in `app/engine/`)
- Rollback never deletes backend volume data — it only re-toggles management.
- A volume is never managed by both clouds at once (C4 manage runs strictly after C3 unmanage).
- Once the destination VM exists (C5) the runner never auto-rolls-back — it marks
  `NeedsAttention` for a human (tearing down a live VM is riskier than the failure).
- Each cutover step is checkpointed as it completes (the generator yields incrementally),
  so a mid-cutover failure leaves accurate state for rollback.

## Known integration gaps (validated only against live OpenStack)
These are intentionally not unit-mocked; complete and verify them via the gated
`tests/integration` suite (`PCD_LIVE=1`) against two shared-backend PCD envs:

1. **Production discovery/runner wiring (`app/wiring.py`).** `wire_production()` injects
   the destination and migration repos, but a `DiscoveryService` (with a real
   `conn_factory` building openstacksdk connections from saved creds, plus `source_conn`,
   `assess`, and `runner_for` that assembles a `ProductionEngine` + plan from a Migration
   CR) must be constructed and injected before launches will execute. Until then, the API
   stores migrations but does not run them in-cluster.
2. **`NeedsReauth` triggering.** `ReauthRequired` is defined and handled by the runner, but
   the client wrappers do not yet map the OpenStack SDK's token-expiry exception
   (`keystoneauth1` Unauthorized) to it. Map it at the session/client layer so mid-run
   token expiry pauses safely instead of falling into the generic failure path.
3. **Cancellation.** Cancel is cooperative and honored only before cutover begins; there is
   no mid-cutover interruption (by design — the downtime window must complete or roll back).
