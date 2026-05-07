"""Tests for MAF v1.0 agent orchestration module."""

import os

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
                return expected

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

            async def fake_invoke(self, payload):
                assert payload == {
                    "existing_funds": ["SPY"],
                    "candidate_funds": ["VTI", "QQQ"],
                }
                return expected

            monkeypatch.setattr(
                distributed_module.RemoteRecommendationProxy,
                "invoke",
                fake_invoke,
            )

            orchestrator = distributed_module.DistributedOrchestratorAgent()
            response = await orchestrator.run_recommendation(["SPY"], ["VTI", "QQQ"])

            assert response.disclaimer is not None
            assert response.timestamp is not None
            assert "SPY" in response.recommendations
            assert len(response.recommendations["SPY"]) > 0
        finally:
            _restore_env_var("FOUNDRY_PROJECT_ENDPOINT", previous)
            _refresh_settings()


class TestRemoteAgentProxy:
    @pytest.mark.asyncio
    async def test_invoke_raises_not_implemented(self):
        from src.agents.remote import RemoteAnalysisProxy

        proxy = RemoteAnalysisProxy("http://example.com")
        with pytest.raises(NotImplementedError, match="EXECUTION_MODE=agent_local"):
            await proxy.invoke({})

    def test_proxy_names(self):
        from src.agents.remote import (
            RemoteAnalysisProxy,
            RemoteCandidateProxy,
            RemoteRecommendationProxy,
        )

        assert RemoteAnalysisProxy("x").agent_name == "ExistingPortfolioAnalysisAgent"
        assert RemoteCandidateProxy("x").agent_name == "CandidateUniverseAnalysisAgent"
        assert RemoteRecommendationProxy("x").agent_name == "RecommendationAgent"


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
