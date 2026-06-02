from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.deps import get_destinations, get_discovery

router = APIRouter(prefix="/api/v1/destinations", tags=["destinations"])


class DestinationIn(BaseModel):
    name: str
    authUrl: str
    region: str
    username: str
    password: str
    projectName: str
    userDomain: str = "Default"
    projectDomain: str = "Default"


@router.post("", status_code=201)
def create(body: DestinationIn):
    repo = get_destinations()
    d = repo.create(name=body.name, auth_url=body.authUrl, region=body.region,
                    project_name=body.projectName, user_domain=body.userDomain,
                    project_domain=body.projectDomain, username=body.username,
                    password=body.password)
    return d   # never includes password


@router.get("")
def list_destinations():
    out = []
    for d in get_destinations().list():
        spec = {k: v for k, v in d["spec"].items() if k != "credentialsSecretRef"}
        out.append({"id": d["metadata"]["name"], **spec, "status": d.get("status", {})})
    return out


class DraftTestIn(BaseModel):
    authUrl: str
    username: str
    password: str
    projectName: str
    userDomain: str = "Default"
    projectDomain: str = "Default"


@router.post("/test")
def test_draft(body: DraftTestIn):
    """Validate unsaved credentials (the registration form tests before saving)."""
    ok, msg = get_discovery().test_draft(body.dict())
    if not ok:
        raise HTTPException(status_code=502, detail=msg)
    return {"reachable": True}


@router.post("/{did}/test")
def test_connection(did: str):
    disc = get_discovery()
    ok, msg = disc.test(did)
    get_destinations().set_status(did, reachable=ok, message=msg)
    if not ok:
        raise HTTPException(status_code=502, detail=msg)
    return {"reachable": True}


@router.get("/{did}/projects")
def projects(did: str):
    return get_discovery().projects(did)


@router.get("/{did}/azs")
def azs(did: str):
    return get_discovery().azs(did)


@router.get("/{did}/networks")
def networks(did: str):
    return get_discovery().networks(did)


@router.get("/{did}/flavors")
def flavors(did: str):
    return get_discovery().flavors(did)
