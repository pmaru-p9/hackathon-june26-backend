# Live validation checklist

The POD ships with all logic unit-tested. The items below need a live OpenStack/PCD
environment to confirm (unit tests mock the SDK). Tracked by the gated `tests/integration`
suite (`PCD_LIVE=1`).

## Validatable against ONE env (the source DU the POD runs in)
- [x] Pod deploys, `/healthz` 200, in-cluster `wire_production()` runs.
- [x] Register destination + list (CRD + Secret written; password only in Secret).
- [ ] **Test connection** — `POST /destinations/test` and `/destinations/{id}/test` against a
      real Keystone (`DiscoveryConn.authorize`). Register the DU's own Keystone to validate.
- [ ] **Discovery** — `/destinations/{id}/projects|azs|networks|flavors` return real data
      (`DiscoveryConn` SDK calls: `identity.projects`, `compute.availability_zones`,
      `network.networks/subnets`, `compute.flavors`).
- [ ] **Source migration-profile** — `GET /source/vms/{id}/migration-profile` against a real
      VM (`server_to_dict`: boot-from-volume detection, root-volume id, flavor specs, NIC
      ip/mac). Confirm boot-from-volume vs image-backed classification.

## Requires TWO shared-backend envs (true end-to-end)
- [ ] **Preflight `assess()` safety facts** (currently default to BLOCKING in
      `DiscoveryService.assess`): `shared_backend` (source volume backend == a dest pool),
      `resolved_volume_type` (dest type bound to that backend), `is_admin` (source token role),
      `volumes_detachable`, `quota_ok`. Implement + confirm; until then preflight P4/P1 fail
      safe and no migration executes.
- [ ] **`runner_factory`** (`app/wiring.py`, currently `None`): assemble `ProductionEngine`
      with a dest-scoped cinderclient (`ProdCinder`), source/dest `ProdNova`, `ProdNeutron`,
      and a `build_plan(...)`; resolve `dest_flavor_id`, `dest_volume_type`, and the dest
      cinder pool host.
- [ ] **Execution adapters** (`app/osclients/prod_clients.py`, marked LIVE-VALIDATE):
      - `ProdCinder.backend_name` — driver-specific array naming (default `volume-<uuid>`).
      - `ProdCinder.list_manageable/manage` — confirm `reference`/`safe_to_manage` shape and
        microversion ≥ 3.8.
      - `ProdNova.create_server` BDM/networks mapping; `detach/attach_volume`,
        `stop/start` semantics.
      - `ProdNeutron.create_port` preserves IP + MAC.
- [ ] **Cutover happy path + induced rollback** at C3/C4/C5 — assert no array data deleted,
      volume re-managed on source, source VM restarted.
- [ ] **NeedsReauth** — expire the source token mid-run; confirm pause (not rollback).

## How to run the gated suite
```bash
PCD_LIVE=1 ./.venv311/bin/python -m pytest tests/integration -v
```
