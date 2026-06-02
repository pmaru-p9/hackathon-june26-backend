from fastapi import APIRouter, Header, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.deps import get_migrations, get_discovery

router = APIRouter(prefix="/api/v1/migrations", tags=["migrations"])


class LaunchIn(BaseModel):
    vmIds: list[str]
    vmName: str
    destinationId: str
    targetProject: str
    az: str
    networkMap: list[dict]
    flavor: dict
    preserve: dict
    sourceCleanup: str


@router.post("/preflight")
def preflight(body: LaunchIn, x_auth_token: str = Header(...),
              x_auth_url: str = Header(...), x_project_id: str = Header(...)):
    """No-mutation: build the context from live data and run P1-P8. The UI Review
    step renders these results and only enables Migrate when all pass."""
    from app.engine.production import build_context_from_profile
    from app.engine.preflight import run_preflight
    disc = get_discovery()
    profile = disc.assess(body.dict(), x_auth_url, x_auth_token, x_project_id)
    checks = run_preflight(build_context_from_profile(profile))
    return [{"id": c.id, "passed": c.passed, "message": c.message} for c in checks]


@router.post("", status_code=202)
def launch(body: LaunchIn, background: BackgroundTasks,
           x_auth_token: str = Header(...), x_auth_url: str = Header(...),
           x_project_id: str = Header(...)):
    repo = get_migrations()
    m = repo.create(vm_id=body.vmIds[0], vm_name=body.vmName,
                    destination_ref=body.destinationId, target_project=body.targetProject,
                    az=body.az, network_map=body.networkMap, flavor=body.flavor,
                    preserve=body.preserve, source_cleanup=body.sourceCleanup)
    repo.store_source_token(m["id"], x_auth_token, x_auth_url, x_project_id)
    disc = get_discovery()
    runner = disc.runner_for(m["id"]) if disc else None
    if runner:
        background.add_task(runner.run, m["id"])
    return {"id": m["id"]}


@router.get("")
def list_migrations():
    return [{"id": x["metadata"]["name"], **x["spec"], "status": x["status"]}
            for x in get_migrations().list()]


@router.get("/{mid}")
def get_migration(mid: str):
    try:
        return get_migrations().get(mid)
    except KeyError:
        raise HTTPException(status_code=404, detail="not found")


@router.post("/{mid}/cancel")
def cancel(mid: str):
    get_migrations().set_phase(mid, "Failed", "cancelled by user")
    return {"cancelled": True}


class ReauthIn(BaseModel):
    token: str
    authUrl: str
    projectId: str


@router.post("/{mid}/reauth")
def reauth(mid: str, body: ReauthIn, background: BackgroundTasks):
    repo = get_migrations()
    repo.store_source_token(mid, body.token, body.authUrl, body.projectId)
    repo.set_phase(mid, "Pending", "resuming after reauth")
    disc = get_discovery()
    runner = disc.runner_for(mid) if disc else None
    if runner:
        background.add_task(runner.run, mid)
    return {"resumed": True}
