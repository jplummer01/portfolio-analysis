"""Tests for MAF v1.0 agent orchestration module."""

import asyncio
import os
import sys
import types

import pytest
from httpx import ASGITransport, AsyncClient


def _restore_env_var(name: str, previous: str | None) -> None:
    if previous is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = previous


def _refresh_settings():
    from src.core import config
    import src.agents.distributed as distributed_module
    import src.api.routes.analyse as analyse_route
    import src.api.routes.recommend as recommend_route

    config.settings = config.Settings()
    analyse_route.settings = config.settings
    recommend_route.settings = config.settings
    distributed_module.settings = config.settings
    return config.settings


class TestAnalysisExecutor:
    @pytest.mark.asyncio
    async def test_run_returns_all_keys(self):
        from src.agents.executors import AnalysisExecutor

        executor = AnalysisExecutor()
        result = await executor.run({"existing_funds": ["SPY", "QQQ"], "allocations": None})

        assert "overlap_matrix" in result
        assert "concentration" in result
        assert "top_overlaps" in result
        assert "data_quality" in result
        assert "asset_allocation" in result
        assert "sector_exposure" in result
        assert "fee_analysis" in result

    @pytest.mark.asyncio
    async def test_run_with_allocations(self):
        from src.agents.executors import AnalysisExecutor

        executor = AnalysisExecutor()
        result = await executor.run(
            {"existing_funds": ["SPY", "QQQ"], "allocations": [0.6, 0.4]}
        )

        assert result["concentration"] is not None
        assert result["concentration"].total_tickers > 0

    def test_executor_name(self):
        from src.agents.executors import AnalysisExecutor

        assert AnalysisExecutor().name == "ExistingPortfolioAnalysisAgent"


class TestCandidateExecutor:
    @pytest.mark.asyncio
    async def test_run_returns_normalised_and_quality(self):
        from src.agents.executors import CandidateExecutor

        executor = CandidateExecutor()
        result = await executor.run({"candidate_funds": ["VTI", "SCHD"]})

        assert "normalised_candidates" in result
        assert "candidate_data_quality" in result
        assert [fund.symbol for fund in result["normalised_candidates"]] == ["VTI", "SCHD"]

    def test_executor_name(self):
        from src.agents.executors import CandidateExecutor

        assert CandidateExecutor().name == "CandidateUniverseAnalysisAgent"


class TestRecommendationExecutor:
    @pytest.mark.asyncio
    async def test_run_returns_recommendations(self):
        from src.agents.executors import RecommendationExecutor
        from src.services.portfolio_analysis import normalise_funds

        executor = RecommendationExecutor()
        result = await executor.run(
            {
                "existing_normalised": normalise_funds(["SPY"]),
                "candidate_normalised": normalise_funds(["VTI", "QQQ"]),
            }
        )

        assert "recommendations" in result
        assert "SPY" in result["recommendations"]
        assert len(result["recommendations"]["SPY"]) > 0

    def test_executor_name(self):
        from src.agents.executors import RecommendationExecutor

        assert RecommendationExecutor().name == "RecommendationAgent"


class TestPortfolioOrchestratorAgent:
    @pytest.mark.asyncio
    async def test_run_analysis_returns_response(self):
        from src.agents.orchestrator import PortfolioOrchestratorAgent

        orchestrator = PortfolioOrchestratorAgent()
        response = await orchestrator.run_analysis(["SPY", "QQQ"])

        assert response.disclaimer is not None
        assert response.timestamp is not None
        assert response.overlap_matrix is not None
        assert response.overlap_matrix.funds == ["SPY", "QQQ"]

    @pytest.mark.asyncio
    async def test_run_recommendation_returns_response(self):
        from src.agents.orchestrator import PortfolioOrchestratorAgent

        orchestrator = PortfolioOrchestratorAgent()
        response = await orchestrator.run_recommendation(["SPY"], ["VTI", "QQQ"])

        assert response.disclaimer is not None
        assert response.recommendations is not None
        assert "SPY" in response.recommendations
        assert len(response.recommendations["SPY"]) > 0

    def test_build_concurrent_workflow_returns_none_without_maf(self, monkeypatch):
        import src.agents.orchestrator as orchestrator_module

        monkeypatch.setattr(orchestrator_module, "MAF_ORCHESTRATIONS_AVAILABLE", False)
        monkeypatch.setattr(orchestrator_module, "ConcurrentBuilder", None)

        orchestrator = orchestrator_module.PortfolioOrchestratorAgent()

        assert orchestrator._build_concurrent_workflow() is None


class TestDistributedOrchestratorAgent:
    def test_requires_foundry_endpoint(self):
        """DistributedOrchestratorAgent should raise if FOUNDRY_PROJECT_ENDPOINT not set."""

        import src.agents.distributed as distributed_module

        previous = os.environ.pop("FOUNDRY_PROJECT_ENDPOINT", None)
        try:
            _refresh_settings()
            with pytest.raises(RuntimeError, match="FOUNDRY_PROJECT_ENDPOINT"):
                distributed_module.DistributedOrchestratorAgent()
        finally:
            _restore_env_var("FOUNDRY_PROJECT_ENDPOINT", previous)
            _refresh_settings()

    @pytest.mark.asyncio
    async def test_run_analysis_returns_response(self, monkeypatch):
        import src.agents.distributed as distributed_module
        from src.agents.executors import AnalysisExecutor

        previous = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        os.environ["FOUNDRY_PROJECT_ENDPOINT"] = "http://example.com/foundry"
        try:
            _refresh_settings()
            expected = await AnalysisExecutor().run(
                {"existing_funds": ["SPY", "QQQ"], "allocations": None}
            )

            async def fake_invoke(self, payload):
                assert payload == {"existing_funds": ["SPY", "QQQ"], "allocations": None}
                from src.api.models.debug import AgentCallRecord
                record = AgentCallRecord(agent_name="analysis-agent", url="http://example.com/foundry/agents/analysis-agent/endpoint/protocols/invocations")
                return expected, record

            monkeypatch.setattr(distributed_module.RemoteAnalysisProxy, "invoke", fake_invoke)

            orchestrator = distributed_module.DistributedOrchestratorAgent()
            response = await orchestrator.run_analysis(["SPY", "QQQ"])

            assert response.disclaimer is not None
            assert response.timestamp is not None
            assert response.overlap_matrix.funds == ["SPY", "QQQ"]
        finally:
            _restore_env_var("FOUNDRY_PROJECT_ENDPOINT", previous)
            _refresh_settings()

    @pytest.mark.asyncio
    async def test_run_recommendation_returns_response(self, monkeypatch):
        import src.agents.distributed as distributed_module
        from src.agents.executors import RecommendationExecutor
        from src.services.portfolio_analysis import normalise_funds

        previous = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        os.environ["FOUNDRY_PROJECT_ENDPOINT"] = "http://example.com/foundry"
        try:
            _refresh_settings()
            expected = await RecommendationExecutor().run(
                {
                    "existing_normalised": normalise_funds(["SPY"]),
                    "candidate_normalised": normalise_funds(["VTI", "QQQ"]),
                }
            )
            analysis_started = asyncio.Event()
            candidate_started = asyncio.Event()
            release_fanout = asyncio.Event()

            async def fake_analysis(self, payload):
                assert payload == {"existing_funds": ["SPY"]}
                analysis_started.set()
                await candidate_started.wait()
                await release_fanout.wait()
                from src.api.models.debug import AgentCallRecord
                record = AgentCallRecord(agent_name="analysis-agent", url="http://fake")
                return {"data_quality": []}, record

            async def fake_candidate(self, payload):
                assert payload == {"candidate_funds": ["VTI", "QQQ"]}
                candidate_started.set()
                await analysis_started.wait()
                await release_fanout.wait()
                from src.api.models.debug import AgentCallRecord
                record = AgentCallRecord(agent_name="candidate-agent", url="http://fake")
                return {"normalised_candidates": normalise_funds(["VTI", "QQQ"])}, record

            async def fake_recommendation(self, payload):
                assert analysis_started.is_set()
                assert candidate_started.is_set()
                assert payload == {
                    "existing_funds": ["SPY"],
                    "candidate_funds": ["VTI", "QQQ"],
                }
                from src.api.models.debug import AgentCallRecord
                record = AgentCallRecord(agent_name="recommendation-agent", url="http://fake")
                return expected, record

            monkeypatch.setattr(
                distributed_module.RemoteAnalysisProxy,
                "invoke",
                fake_analysis,
            )
            monkeypatch.setattr(
                distributed_module.RemoteCandidateProxy,
                "invoke",
                fake_candidate,
            )
            monkeypatch.setattr(
                distributed_module.RemoteRecommendationProxy,
                "invoke",
                fake_recommendation,
            )

            orchestrator = distributed_module.DistributedOrchestratorAgent()
            response_task = asyncio.create_task(
                orchestrator.run_recommendation(["SPY"], ["VTI", "QQQ"])
            )
            await asyncio.wait_for(analysis_started.wait(), timeout=1.0)
            await asyncio.wait_for(candidate_started.wait(), timeout=1.0)
            release_fanout.set()
            response = await response_task

            assert response.disclaimer is not None
            assert response.timestamp is not None
            assert "SPY" in response.recommendations
            assert len(response.recommendations["SPY"]) > 0
        finally:
            _restore_env_var("FOUNDRY_PROJECT_ENDPOINT", previous)
            _refresh_settings()


class TestRemoteAgentProxy:
    def test_build_url(self):
        from src.agents.remote import RemoteAnalysisProxy

        proxy = RemoteAnalysisProxy("http://example.com/foundry/")

        assert (
            proxy._build_url()
            == "http://example.com/foundry/agents/analysis-agent/endpoint/protocols/invocations"
        )

    @pytest.mark.asyncio
    async def test_invoke_posts_payload(self, monkeypatch):
        import src.agents.remote as remote_module

        captured: dict[str, object] = {}

        class FakeToken:
            token = "token-value"

        class FakeCredential:
            async def get_token(self, scope):
                captured["scope"] = scope
                return FakeToken()

            async def close(self):
                captured["closed"] = True

        azure_module = types.ModuleType("azure")
        azure_module.__path__ = []
        identity_module = types.ModuleType("azure.identity")
        identity_module.__path__ = []
        aio_module = types.ModuleType("azure.identity.aio")
        aio_module.DefaultAzureCredential = FakeCredential
        monkeypatch.setitem(sys.modules, "azure", azure_module)
        monkeypatch.setitem(sys.modules, "azure.identity", identity_module)
        monkeypatch.setitem(sys.modules, "azure.identity.aio", aio_module)

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                captured["status_checked"] = True

            def json(self):
                return {"ok": True}

        class FakeAsyncClient:
            def __init__(self, *, timeout):
                captured["timeout"] = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json, headers):
                captured["url"] = url
                captured["payload"] = json
                captured["headers"] = headers
                return FakeResponse()

        monkeypatch.setattr(remote_module.httpx, "AsyncClient", FakeAsyncClient)

        result, record = await remote_module.RemoteAnalysisProxy(
            "http://example.com/foundry/"
        ).invoke({"existing_funds": ["SPY"]})

        assert captured["scope"] == "https://cognitiveservices.azure.com/.default"
        assert captured["timeout"] == 60.0
        assert (
            captured["url"]
            == "http://example.com/foundry/agents/analysis-agent/endpoint/protocols/invocations"
        )
        assert captured["payload"] == {"existing_funds": ["SPY"]}
        assert captured["headers"] == {
            "Content-Type": "application/json",
            "Authorization": "Bearer token-value",
        }
        assert captured["closed"] is True
        assert captured["status_checked"] is True
        assert result == {"ok": True}
        assert record.agent_name == "analysis-agent"
        assert record.status_code == 200
        assert record.latency_ms is not None
        assert record.error is None

    def test_proxy_names(self):
        from src.agents.remote import (
            RemoteAnalysisProxy,
            RemoteCandidateProxy,
            RemoteRecommendationProxy,
        )

        assert RemoteAnalysisProxy("x").agent_name == "analysis-agent"
        assert RemoteCandidateProxy("x").agent_name == "candidate-agent"
        assert RemoteRecommendationProxy("x").agent_name == "recommendation-agent"


class TestAgentLocalRoutes:
    """Test that routes dispatch to orchestrator in agent_local mode."""

    @pytest.mark.asyncio
    async def test_analyse_with_agent_local(self):
        from src.api.main import app

        previous = os.environ.get("EXECUTION_MODE")
        os.environ["EXECUTION_MODE"] = "agent_local"
        try:
            _refresh_settings()
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/analyse",
                    json={"existing_funds": ["SPY", "QQQ"]},
                )

            assert response.status_code == 200
            data = response.json()
            assert "disclaimer" in data
            assert "overlap_matrix" in data
        finally:
            _restore_env_var("EXECUTION_MODE", previous)
            _refresh_settings()

    @pytest.mark.asyncio
    async def test_recommend_with_agent_local(self):
        from src.api.main import app

        previous = os.environ.get("EXECUTION_MODE")
        os.environ["EXECUTION_MODE"] = "agent_local"
        try:
            _refresh_settings()
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/recommend",
                    json={
                        "existing_funds": ["SPY"],
                        "candidate_funds": ["VTI", "QQQ"],
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert "disclaimer" in data
            assert "recommendations" in data
        finally:
            _restore_env_var("EXECUTION_MODE", previous)
            _refresh_settings()


class TestDebugMode:
    """Test that ?debug=true returns debug_info in responses."""

    @pytest.mark.asyncio
    async def test_analyse_debug_true_returns_debug_info(self):
        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/analyse?debug=true",
                json={"existing_funds": ["SPY", "QQQ"]},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["debug_info"] is not None
        assert "execution_mode" in data["debug_info"]
        assert "fallback_used" in data["debug_info"]
        assert "total_latency_ms" in data["debug_info"]

    @pytest.mark.asyncio
    async def test_analyse_debug_false_returns_null_debug_info(self):
        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/analyse",
                json={"existing_funds": ["SPY", "QQQ"]},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["debug_info"] is None

    @pytest.mark.asyncio
    async def test_recommend_debug_true_returns_debug_info(self):
        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/recommend?debug=true",
                json={
                    "existing_funds": ["SPY"],
                    "candidate_funds": ["ARKK", "SCHD"],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["debug_info"] is not None
        assert data["debug_info"]["execution_mode"] == "direct"
        assert data["debug_info"]["fallback_used"] is False

    @pytest.mark.asyncio
    async def test_recommend_debug_false_returns_null_debug_info(self):
        from src.api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/recommend",
                json={
                    "existing_funds": ["SPY"],
                    "candidate_funds": ["ARKK", "SCHD"],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["debug_info"] is None

    @pytest.mark.asyncio
    async def test_analyse_debug_with_agent_local_fallback(self):
        """When agent_local fails, debug_info should show fallback_used=True."""
        from src.api.main import app

        previous = os.environ.get("EXECUTION_MODE")
        os.environ["EXECUTION_MODE"] = "agent_local"
        try:
            _refresh_settings()

            # agent_local works in this env, so fallback_used should be False
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/analyse?debug=true",
                    json={"existing_funds": ["SPY"]},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["debug_info"] is not None
            assert data["debug_info"]["execution_mode"] == "agent_local"
        finally:
            _restore_env_var("EXECUTION_MODE", previous)
            _refresh_settings()
