from fastapi import FastAPI
from app.api.endpoints import router

app = FastAPI(title="BROKS Platform", version="2.0.0")
app.include_router(router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok", "system": "BROKS Backend"}
