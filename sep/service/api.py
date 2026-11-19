"""FastAPI: the evaluation results and the Black Friday replay for the dashboard."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from sep.config import ROOT, load

REPORTS = ROOT / "reports"


def _json(name: str) -> dict:
    p = REPORTS / f"{name}.json"
    if not p.exists():
        raise HTTPException(404, f"{name} report not generated yet: run python -m sep.eval.cli evaluate")
    return json.loads(p.read_text())


def create_app() -> FastAPI:
    app = FastAPI(title="shop-edge-platform", version="1.0.0")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/api/results")
    def results() -> dict:
        ho = REPORTS / "heldout.json"
        from sep.eval.cli import gate

        heldout = json.loads(ho.read_text()) if ho.exists() else None
        return {"dev": _json("dev"), "heldout": heldout, "gate": load("gate")["platform"],
                "heldout_gate_fails": gate(heldout) if heldout else None}

    @app.get("/api/blackfriday")
    def blackfriday() -> dict:
        return _json("blackfriday")

    web = Path(os.environ.get("SEP_WEB_DIST", ROOT / "web" / "dist"))
    if web.exists():
        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    return app


app = create_app()
