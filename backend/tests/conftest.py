from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest

from app.models.auth import AuthenticatedUser


class FakeRedis:
    def __init__(self):
        self.store: Dict[str, str] = {}

    async def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value


class FakeResult:
    def __init__(self, row: Any):
        self._row = row

    def fetchone(self):
        return self._row


class FakeSession:
    def __init__(self, row: Any, captured: Dict[str, Any]):
        self.row = row
        self.captured = captured

    async def execute(self, query, params):
        self.captured["query"] = str(query)
        self.captured["params"] = params
        return FakeResult(self.row)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, row: Any):
        self.row = row
        self.captured: Dict[str, Any] = {}

    async def initialize(self):
        return None

    def get_session(self):
        return FakeSession(self.row, self.captured)


def make_user(tenant_id: Optional[str]) -> AuthenticatedUser:
    return AuthenticatedUser(
        id="user-1",
        email="sunset@propertyflow.com",
        permissions=[],
        cities=[],
        is_admin=False,
        tenant_id=tenant_id,
    )


@pytest.fixture
def sunset_user():
    return make_user("tenant-a")


@pytest.fixture
def ocean_user():
    return make_user("tenant-b")


@pytest.fixture
def seed_check_in_boundary():
    return datetime(2024, 2, 29, 23, 30, tzinfo=timezone.utc)


@pytest.fixture
def sunset_march_row():
    return SimpleNamespace(
        total_revenue=Decimal("2250.000"),
        reservation_count=4,
        timezone="Europe/Paris",
    )


@pytest.fixture
def ocean_prop001_row():
    return SimpleNamespace(
        total_revenue=Decimal("0"),
        reservation_count=0,
        timezone="America/New_York",
    )
