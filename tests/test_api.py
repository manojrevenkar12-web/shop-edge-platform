from fastapi.testclient import TestClient

from sep.service.api import create_app


def test_health_and_reports():
    c = TestClient(create_app())
    assert c.get("/api/health").json() == {"ok": True}
    assert c.get("/api/results").status_code in (200, 404)
    assert c.get("/api/blackfriday").status_code in (200, 404)


def test_the_dashboard_gets_the_same_held_out_verdict_as_the_cli():
    import json
    from pathlib import Path

    from sep.eval.cli import gate
    ho = Path(__file__).resolve().parents[1] / "reports" / "heldout.json"
    if not ho.exists():
        return
    body = TestClient(create_app()).get("/api/results").json()
    assert body["heldout_gate_fails"] == gate(json.loads(ho.read_text()))
