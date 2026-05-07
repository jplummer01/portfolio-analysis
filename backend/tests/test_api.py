"""API integration tests."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "timestamp" in data


class TestIngestEndpoints:
    @pytest.mark.asyncio
    async def test_ingest_symbols(self, client):
        resp = await client.post(
            "/api/ingest/symbols",
            json={"symbols": ["SPY", "QQQ"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["funds"]) == 2
        assert data["disclaimer"] != ""
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_ingest_symbols_unknown(self, client):
        resp = await client.post(
            "/api/ingest/symbols",
            json={"symbols": ["UNKNOWN_XYZ"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["warnings"]) > 0

    @pytest.mark.asyncio
    async def test_ingest_paste(self, client):
        resp = await client.post(
            "/api/ingest/paste",
            json={"text": "SPY, QQQ, VTI"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["funds"]) == 3

    @pytest.mark.asyncio
    async def test_ingest_upload_json(self, client):
        content = json.dumps(["SPY", "QQQ"]).encode()
        resp = await client.post(
            "/api/ingest/upload",
            files={"file": ("test.json", content, "application/json")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["funds"]) == 2

    @pytest.mark.asyncio
    async def test_ingest_upload_csv(self, client):
        content = b"symbol\nSPY\nQQQ\nVTI"
        resp = await client.post(
            "/api/ingest/upload",
            files={"file": ("test.csv", content, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["funds"]) == 3


class TestAnalyseEndpoint:
    @pytest.mark.asyncio
    async def test_analyse_basic(self, client):
        resp = await client.post(
            "/api/analyse",
            json={"existing_funds": ["SPY", "QQQ"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "overlap_matrix" in data
        assert "concentration" in data
        assert "top_overlaps" in data
        assert "data_quality" in data
        assert data["disclaimer"] != ""

    @pytest.mark.asyncio
    async def test_analyse_with_allocations(self, client):
        resp = await client.post(
            "/api/analyse",
            json={"existing_funds": ["SPY", "QQQ", "VTI"], "allocations": [0.5, 0.3, 0.2]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["overlap_matrix"]["funds"]) == 3

    @pytest.mark.asyncio
    async def test_analyse_overlap_matrix_symmetric(self, client):
        resp = await client.post(
            "/api/analyse",
            json={"existing_funds": ["SPY", "QQQ", "VTI"]},
        )
        data = resp.json()
        matrix = data["overlap_matrix"]["unweighted"]
        n = len(matrix)
        for i in range(n):
            for j in range(n):
                assert abs(matrix[i][j] - matrix[j][i]) < 1e-10

    @pytest.mark.asyncio
    async def test_analyse_data_quality(self, client):
        resp = await client.post(
            "/api/analyse",
            json={"existing_funds": ["SPY", "VXUS"]},
        )
        data = resp.json()
        dq = {e["symbol"]: e for e in data["data_quality"]}
        assert dq["SPY"]["is_stale"] is False
        assert dq["VXUS"]["is_stale"] is True


class TestRecommendEndpoint:
    @pytest.mark.asyncio
    async def test_recommend_basic(self, client):
        resp = await client.post(
            "/api/recommend",
            json={
                "existing_funds": ["SPY"],
                "candidate_funds": ["ARKK", "SCHD", "VXUS"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendations" in data
        assert "SPY" in data["recommendations"]
        candidates = data["recommendations"]["SPY"]
        assert len(candidates) == 3
        assert data["disclaimer"] != ""

    @pytest.mark.asyncio
    async def test_recommend_score_breakdown(self, client):
        resp = await client.post(
            "/api/recommend",
            json={
                "existing_funds": ["SPY"],
                "candidate_funds": ["ARKK"],
            },
        )
        data = resp.json()
        candidate = data["recommendations"]["SPY"][0]
        assert "breakdown" in candidate
        assert "overlap_reduction" in candidate["breakdown"]
        assert "performance" in candidate["breakdown"]
        assert "data_quality_penalty" in candidate["breakdown"]
        assert "cost_penalty" in candidate["breakdown"]
        assert candidate["total_score"] >= 0

    @pytest.mark.asyncio
    async def test_recommend_explanation_present(self, client):
        resp = await client.post(
            "/api/recommend",
            json={
                "existing_funds": ["QQQ"],
                "candidate_funds": ["SCHD"],
            },
        )
        data = resp.json()
        candidate = data["recommendations"]["QQQ"][0]
        assert candidate["explanation"] != ""

    @pytest.mark.asyncio
    async def test_recommend_missing_existing(self, client):
        resp = await client.post(
            "/api/recommend",
            json={
                "existing_funds": [],
                "candidate_funds": ["ARKK"],
            },
        )
        assert resp.status_code == 422  # Validation error (min_length=1)

    @pytest.mark.asyncio
    async def test_recommend_missing_candidates(self, client):
        resp = await client.post(
            "/api/recommend",
            json={
                "existing_funds": ["SPY"],
                "candidate_funds": [],
            },
        )
        assert resp.status_code == 422  # Validation error (min_length=1)
