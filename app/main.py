"""FastAPI app: the local server the launcher starts and the browser talks to.

Minimal on purpose right now — a health check (for the launcher's
single-instance detection), one hello-world activity endpoint (to prove
the module contract reaches the browser), and the static front-end.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.activities.hello_world import HelloWorldActivity

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Typing Trainer")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/activities/hello-world")
def hello_world_activity() -> dict:
    return HelloWorldActivity().generate()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
