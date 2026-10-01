from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from ready_set_wash.app import create_app
from ready_set_wash.config import Settings
from ready_set_wash.domain import Rate
from ready_set_wash.providers import PriceUnavailable

QUERY = """query($deadline: DateTime!){dashboard(deadline:$deadline){mode
prices{start end pencePerKwh}
plan{start end costPence nowCostPence savingsPence}}}"""


@pytest.fixture
def client():
    with TestClient(create_app(Settings())) as client:
        yield client


def request_plan(client, deadline=None, query=QUERY):
    deadline = deadline or (datetime.now(UTC) + timedelta(hours=8)).isoformat()
    return client.post("/graphql", json={"query": query, "variables": {"deadline": deadline}})


def test_local_pages_and_headers(client):
    assert client.get("/health").json() == {"status": "ok"}
    response = client.get("/")
    assert "The right time" in response.text
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert client.get("/styles.css").status_code == 200
    assert client.get("/app.js").status_code == 200
    assert client.get("/does-not-exist").status_code == 404
    assert client.get("/", headers={"host": "evil.com"}).status_code == 400


def test_graphql_round_trip(client):
    result = request_plan(client)
    assert result.status_code == 200
    dashboard = result.json()["data"]["dashboard"]
    assert dashboard["mode"] == "demo"
    assert len(dashboard["prices"]) == 96
    assert dashboard["plan"]["savingsPence"] >= 0
    assert "apiKey" not in result.text


def test_graphql_invalid_input(client):
    assert "errors" in request_plan(client, "2020-01-01T00:00:00Z").json()
    assert "errors" in request_plan(client, "2026-10-01T12:00:00").json()
    assert "errors" in client.post("/graphql", json={"query": "{secret}"}).json()


def test_upstream_failure_is_safe(client):
    client.app.state.provider.rates = AsyncMock(side_effect=PriceUnavailable("Prices unavailable"))
    payload = request_plan(client).json()
    assert payload["data"] is None
    assert payload["errors"][0]["message"] == "Prices unavailable"


def test_missing_now_price(client):
    now = datetime.now(UTC)
    client.app.state.provider.rates = AsyncMock(
        return_value=[
            Rate(
                now + timedelta(hours=1),
                now + timedelta(hours=4),
                Decimal(10),
            )
        ]
    )
    plan = request_plan(client).json()["data"]["dashboard"]["plan"]
    assert plan["nowCostPence"] is None
    assert plan["savingsPence"] is None


def test_request_security(client):
    assert (
        client.post("/graphql", json={}, headers={"origin": "https://evil.test"}).status_code == 403
    )
    assert client.post("/graphql", content="abc").status_code == 415
    assert (
        client.post(
            "/graphql", content="x" * 9000, headers={"content-type": "application/json"}
        ).status_code
        == 413
    )
    assert (
        client.post("/graphql", json={}, headers={"origin": "http://testserver"}).status_code != 403
    )


def test_graphql_alias_limit(client):
    query = (
        "{"
        + " ".join(f'a{i}: dashboard(deadline:"2026-10-01T18:00:00Z"){{mode}}' for i in range(5))
        + "}"
    )
    assert "errors" in client.post("/graphql", json={"query": query}).json()


def test_default_factory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200


def test_energy_input_removed_from_public_contract(client):
    response = client.post(
        "/graphql",
        json={"query": '{dashboard(deadline:"2026-10-01T18:00:00Z", energyKwh:1){mode}}'},
    )
    assert "Unknown argument 'energyKwh'" in response.json()["errors"][0]["message"]
