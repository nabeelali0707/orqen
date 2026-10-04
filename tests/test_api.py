import pytest

pytest.importorskip("starlette")
from starlette.testclient import TestClient

from orqen.api import Principal, create_app
from orqen.service import demo_service

TOKEN = "a" * 40
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Idempotency-Key": "request-1"}


def test_authenticated_execution_and_owner_isolation(tmp_path):
    app = create_app(
        demo_service(tmp_path / "db"), {TOKEN: Principal("alice"), "b" * 40: Principal("bob")}
    )
    with TestClient(app) as client:
        assert client.get("/v1/runs").status_code == 401
        assert client.get("/health").status_code == 200
        assert client.get("/").headers["content-security-policy"]
        assert "Execution, with evidence" in client.get("/").text
        response = client.post(
            "/v1/runs", headers=HEADERS, json={"task": "addition", "inputs": {"a": 2, "b": 3}}
        )
        assert response.status_code == 200 and response.json()["trace"]["verified"]
        row = response.json()
        assert client.get(f"/v1/runs/{row['id']}", headers=HEADERS).json() == row
        assert (
            client.get(
                f"/v1/runs/{row['id']}", headers={"Authorization": f"Bearer {'b' * 40}"}
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/v1/runs", headers=HEADERS, json={"task": "addition", "inputs": {"a": 9, "b": 3}}
            ).status_code
            == 409
        )


def test_rejects_oversize_and_client_permission_injection(tmp_path):
    with TestClient(create_app(demo_service(tmp_path / "db"), {TOKEN: Principal("a")})) as client:
        assert (
            client.post(
                "/v1/runs",
                headers=HEADERS,
                json={"task": "addition", "inputs": {}, "permissions": ["admin"]},
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/v1/runs",
                headers={**HEADERS, "Content-Type": "application/json"},
                content=" " * 17000,
            ).status_code
            == 413
        )
        assert client.get("/v1/runs", headers=HEADERS).json() == []


def test_missing_secret_fails_closed(tmp_path):
    with pytest.raises(ValueError):
        create_app(demo_service(tmp_path / "db"), {"weak": Principal("a")})
