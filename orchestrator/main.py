from fastapi import FastAPI

app = FastAPI(title="CyberSec Orchestrator")


@app.get("/health")
async def health():
    return {"status": "ok"}
