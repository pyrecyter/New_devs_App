from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import dashboard as dashboard_module
from app.models.auth import AuthenticatedUser
from app.services.reservations import PropertyNotFoundError
from tests.conftest import make_user


def build_client(user: AuthenticatedUser, monkeypatch, summary=None, error=None) -> TestClient:
    async def fake_summary(property_id, tenant_id, month, year):
        if error:
            raise error
        return summary or {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "total": "2250.00",
            "currency": "USD",
            "count": 4,
            "month": month,
            "year": year,
        }

    monkeypatch.setattr(dashboard_module, "get_revenue_summary", fake_summary)

    app = FastAPI()
    app.include_router(dashboard_module.router, prefix="/api/v1")
    app.dependency_overrides[dashboard_module.get_current_user] = lambda: user
    return TestClient(app)


def test_dashboard_rejects_missing_tenant(monkeypatch):
    client = build_client(make_user(None), monkeypatch)
    response = client.get("/api/v1/dashboard/summary", params={
        "property_id": "prop-001",
        "month": 3,
        "year": 2024,
    })
    assert response.status_code == 403


def test_dashboard_returns_decimal_string_not_float(monkeypatch, sunset_user):
    client = build_client(sunset_user, monkeypatch)
    response = client.get("/api/v1/dashboard/summary", params={
        "property_id": "prop-001",
        "month": 3,
        "year": 2024,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_revenue"] == "2250.00"
    assert isinstance(payload["total_revenue"], str)
    assert payload["reservations_count"] == 4
    assert payload["month"] == 3
    assert payload["year"] == 2024


def test_dashboard_isolates_ocean_property_overlap(monkeypatch, ocean_user):
    client = build_client(
        ocean_user,
        monkeypatch,
        summary={
            "property_id": "prop-001",
            "tenant_id": "tenant-b",
            "total": "0.00",
            "currency": "USD",
            "count": 0,
            "month": 3,
            "year": 2024,
        },
    )
    response = client.get("/api/v1/dashboard/summary", params={
        "property_id": "prop-001",
        "month": 3,
        "year": 2024,
    })
    assert response.status_code == 200
    assert response.json()["total_revenue"] == "0.00"


def test_dashboard_unknown_property_is_404(monkeypatch, sunset_user):
    client = build_client(
        sunset_user,
        monkeypatch,
        error=PropertyNotFoundError("missing"),
    )
    response = client.get("/api/v1/dashboard/summary", params={
        "property_id": "prop-missing",
        "month": 3,
        "year": 2024,
    })
    assert response.status_code == 404
