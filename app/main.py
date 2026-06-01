from fastapi import FastAPI

app = FastAPI(title="PCD Migration POD")

@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}
