import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    """
    Session-scoped test client so the lifespan runs once per test session.
    """
    with TestClient(app) as c:
        yield c
