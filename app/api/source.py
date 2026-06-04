from fastapi import APIRouter, Header, Request

from app.osclients.profile import build_migration_profile
from app.api.authurl import normalize_auth_url
from app.deps import get_discovery

router = APIRouter(prefix="/api/v1/source", tags=["source"])


@router.get("/vms/{vm_id}/migration-profile")
def migration_profile(vm_id: str, request: Request, x_auth_token: str = Header(...),
                      x_auth_url: str = Header(...), x_project_id: str = Header(...)):
    auth_url = normalize_auth_url(x_auth_url, request)   # UI sends a relative "/keystone"
    conn = get_discovery().source_conn(auth_url, x_auth_token, x_project_id)
    return build_migration_profile(conn, vm_id)
