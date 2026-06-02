import os

from fastapi import FastAPI

from app.deps import set_repos  # re-exported for tests
from app.api import destinations as destinations_api
from app.api import source as source_api
from app.api import migrations as migrations_api

app = FastAPI(title="PCD Migration POD")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


app.include_router(destinations_api.router)
app.include_router(source_api.router)
app.include_router(migrations_api.router)


@app.on_event("startup")
def _startup():
    if os.getenv("PCD_MIGRATION_PROD") == "1":
        from app.wiring import wire_production
        wire_production()


__all__ = ["app", "set_repos"]
