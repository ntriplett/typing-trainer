"""Integration tests against the real FastAPI app (in-process, via TestClient).

No real socket/subprocess here — that's covered by the launcher e2e test.
This just proves the app wiring (routes, static files, activity module).
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_index_serves_html_page():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Typing Trainer" in resp.text


def test_hello_world_activity_endpoint():
    resp = client.get("/api/activities/hello-world")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "hello_world"
    assert body["kind"] == "practice"
    assert "Hello, typer!" in body["message"]


def test_analysis_page_is_served():
    resp = client.get("/analysis")
    assert resp.status_code == 200
    assert "Progress" in resp.text


def test_static_js_is_served():
    resp = client.get("/static/js/session.js")
    assert resp.status_code == 200
    assert "fetchStepContent" in resp.text


def test_static_assets_are_never_cached():
    # StaticFiles alone doesn't set Cache-Control, which lets browsers
    # heuristically reuse a stale .js/.css file without even checking
    # for updates -- the real cause behind two rounds of "I fixed it
    # but the browser is still running old code."
    resp = client.get("/static/js/session.js")
    assert resp.headers["cache-control"] == "no-store"


def test_page_routes_are_never_cached_either():
    # FileResponse has the same heuristic-caching problem as StaticFiles
    # -- this is what made analysis.html specifically need a hard
    # refresh after edits (the page route itself wasn't covered by the
    # earlier /static/-only fix).
    for path in ("/", "/session", "/analysis", "/teach-lab"):
        resp = client.get(path)
        assert resp.headers["cache-control"] == "no-store", path
