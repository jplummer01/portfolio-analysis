"""Shared test fixtures."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    import httpx

    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")
