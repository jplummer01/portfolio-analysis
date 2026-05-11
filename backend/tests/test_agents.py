"""Tests for MAF v1.0 agent orchestration module."""

import asyncio
import os
import sys
import types

import pytest
import httpx
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
                record = AgentCallRecord(agent_name="analysis-agent", url="http://example.com/foundry/agents/analysis-agent/endpoint/protocols/invocations?api-version=v1")
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
            == "http://example.com/foundry/agents/analysis-agent/endpoint/protocols/invocations?api-version=v1"
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

        assert captured["scope"] == "https://ai.azure.com/.default"
        assert captured["timeout"] == 60.0
        assert (
            captured["url"]
            == "http://example.com/foundry/agents/analysis-agent/endpoint/protocols/invocations?api-version=v1"
        )
        assert captured["payload"] == {"existing_funds": ["SPY"]}
        assert captured["headers"] == {
            "Content-Type": "application/json",
            "Foundry-Features": "HostedAgents=V1Preview",
            "Authorization": "Bearer token-value",
        }
        assert captured["closed"] is True
        assert captured["status_checked"] is True
        assert result == {"ok": True}
        assert record.agent_name == "analysis-agent"
        assert record.status_code == 200
        assert record.latency_ms is not None
        assert record.error is None
        assert record.request_payload == {"existing_funds": ["SPY"]}
        assert record.response_body == {"ok": True}

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


class TestRemoteAgentErrorHandling:
    """Test that HTTP errors are properly wrapped in RemoteAgentError."""

    @pytest.mark.asyncio
    async def test_http_error_raises_remote_agent_error(self, monkeypatch):
        """HTTPStatusError must produce RemoteAgentError, not TypeError."""
        import src.agents.remote as remote_module
        from src.agents.remote import RemoteAgentError

        class FakeResponse:
            status_code = 500

            def json(self):
                return {"detail": "Internal Server Error"}

            def raise_for_status(self):
                raise httpx.HTTPStatusError(
                    "Server Error",
                    request=httpx.Request("POST", "http://fake"),
                    response=httpx.Response(500),
                )

        class FakeAsyncClient:
            def __init__(self, *, timeout):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json, headers):
                return FakeResponse()

        monkeypatch.setattr(remote_module.httpx, "AsyncClient", FakeAsyncClient)
        monkeypatch.delitem(sys.modules, "azure.identity.aio", raising=False)
        monkeypatch.delitem(sys.modules, "azure.identity", raising=False)
        monkeypatch.delitem(sys.modules, "azure", raising=False)

        proxy = remote_module.RemoteAnalysisProxy("http://example.com/foundry/")

        with pytest.raises(RemoteAgentError) as exc_info:
            await proxy.invoke({"existing_funds": ["SPY"]})

        err = exc_info.value
        assert err.record.agent_name == "analysis-agent"
        assert err.record.status_code == 500
        assert err.record.latency_ms is not None
        assert err.record.error is not None
        assert err.record.request_payload == {"existing_funds": ["SPY"]}
        assert err.record.response_body == {"detail": "Internal Server Error"}

    @pytest.mark.asyncio
    async def test_connection_error_raises_remote_agent_error(self, monkeypatch):
        """Connection errors should also produce RemoteAgentError with record."""
        import src.agents.remote as remote_module
        from src.agents.remote import RemoteAgentError

        class FakeAsyncClient:
            def __init__(self, *, timeout):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json, headers):
                raise httpx.ConnectError("Connection refused")

        monkeypatch.setattr(remote_module.httpx, "AsyncClient", FakeAsyncClient)
        monkeypatch.delitem(sys.modules, "azure.identity.aio", raising=False)
        monkeypatch.delitem(sys.modules, "azure.identity", raising=False)
        monkeypatch.delitem(sys.modules, "azure", raising=False)

        proxy = remote_module.RemoteAnalysisProxy("http://example.com/foundry/")

        with pytest.raises(RemoteAgentError) as exc_info:
            await proxy.invoke({"test": "data"})

        err = exc_info.value
        assert err.record.agent_name == "analysis-agent"
        assert err.record.status_code is None
        assert err.record.request_payload == {"test": "data"}
        assert err.record.response_body is None


class TestDistributedOrchestrationErrorPropagation:
    """Test that distributed orchestration errors carry agent call records."""

    @pytest.mark.asyncio
    async def test_analysis_failure_propagates_record(self, monkeypatch):
        import src.agents.distributed as distributed_module
        from src.agents.distributed import DistributedOrchestrationError
        from src.agents.remote import RemoteAgentError
        from src.api.models.debug import AgentCallRecord

        previous = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        os.environ["FOUNDRY_PROJECT_ENDPOINT"] = "http://example.com/foundry"
        try:
            _refresh_settings()

            async def failing_invoke(self, payload):
                record = AgentCallRecord(
                    agent_name="analysis-agent",
                    url="http://fake",
                    status_code=500,
                    latency_ms=100.0,
                    error="Server Error",
                    request_payload=payload,
                    response_body={"detail": "failure"},
                )
                raise RemoteAgentError("Server Error", record)

            monkeypatch.setattr(
                distributed_module.RemoteAnalysisProxy, "invoke", failing_invoke
            )

            orchestrator = distributed_module.DistributedOrchestratorAgent()
            with pytest.raises(DistributedOrchestrationError) as exc_info:
                await orchestrator.run_analysis(["SPY", "QQQ"])

            err = exc_info.value
            assert len(err.records) == 1
            assert err.records[0].agent_name == "analysis-agent"
            assert err.records[0].status_code == 500
            assert err.records[0].request_payload is not None
            assert err.records[0].response_body == {"detail": "failure"}
        finally:
            _restore_env_var("FOUNDRY_PROJECT_ENDPOINT", previous)
            _refresh_settings()

    @pytest.mark.asyncio
    async def test_recommendation_partial_failure_propagates_records(self, monkeypatch):
        """When one fan-out agent fails, records from both should be captured."""
        import src.agents.distributed as distributed_module
        from src.agents.distributed import DistributedOrchestrationError
        from src.agents.remote import RemoteAgentError
        from src.api.models.debug import AgentCallRecord

        previous = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        os.environ["FOUNDRY_PROJECT_ENDPOINT"] = "http://example.com/foundry"
        try:
            _refresh_settings()

            async def successful_analysis(self, payload):
                record = AgentCallRecord(
                    agent_name="analysis-agent",
                    url="http://fake",
                    status_code=200,
                    latency_ms=50.0,
                    request_payload=payload,
                    response_body={"data_quality": []},
                )
                return {"data_quality": []}, record

            async def failing_candidate(self, payload):
                record = AgentCallRecord(
                    agent_name="candidate-agent",
                    url="http://fake",
                    status_code=503,
                    latency_ms=200.0,
                    error="Service Unavailable",
                    request_payload=payload,
                    response_body="Service Unavailable",
                )
                raise RemoteAgentError("Service Unavailable", record)

            monkeypatch.setattr(
                distributed_module.RemoteAnalysisProxy, "invoke", successful_analysis
            )
            monkeypatch.setattr(
                distributed_module.RemoteCandidateProxy, "invoke", failing_candidate
            )

            orchestrator = distributed_module.DistributedOrchestratorAgent()
            with pytest.raises(DistributedOrchestrationError) as exc_info:
                await orchestrator.run_recommendation(["SPY"], ["VTI"])

            err = exc_info.value
            assert len(err.records) == 2
            agent_names = {r.agent_name for r in err.records}
            assert "analysis-agent" in agent_names
            assert "candidate-agent" in agent_names
        finally:
            _restore_env_var("FOUNDRY_PROJECT_ENDPOINT", previous)
            _refresh_settings()


class TestDistributedFallbackDebugInfo:
    """Test that fallback debug info surfaces partial agent call records."""

    @pytest.mark.asyncio
    async def test_analyse_distributed_fallback_shows_records(self, monkeypatch):
        from src.api.main import app
        import src.agents.distributed as distributed_module
        from src.agents.remote import RemoteAgentError
        from src.api.models.debug import AgentCallRecord

        previous_mode = os.environ.get("EXECUTION_MODE")
        previous_endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        os.environ["EXECUTION_MODE"] = "agent_distributed"
        os.environ["FOUNDRY_PROJECT_ENDPOINT"] = "http://example.com/foundry"
        try:
            _refresh_settings()

            async def failing_invoke(self, payload):
                record = AgentCallRecord(
                    agent_name="analysis-agent",
                    url="http://fake/invoke",
                    status_code=500,
                    latency_ms=150.0,
                    error="Internal Server Error",
                    request_payload=payload,
                    response_body={"detail": "error"},
                )
                raise RemoteAgentError("Internal Server Error", record)

            monkeypatch.setattr(
                distributed_module.RemoteAnalysisProxy, "invoke", failing_invoke
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/analyse?debug=true",
                    json={"existing_funds": ["SPY"]},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["debug_info"] is not None
            assert data["debug_info"]["fallback_used"] is True
            assert "agent_distributed" in data["debug_info"]["fallback_reason"]
            assert len(data["debug_info"]["agents_called"]) == 1
            agent_record = data["debug_info"]["agents_called"][0]
            assert agent_record["agent_name"] == "analysis-agent"
            assert agent_record["status_code"] == 500
            assert agent_record["request_payload"] is not None
            assert agent_record["response_body"] == {"detail": "error"}
        finally:
            _restore_env_var("EXECUTION_MODE", previous_mode)
            _restore_env_var("FOUNDRY_PROJECT_ENDPOINT", previous_endpoint)
            _refresh_settings()

    @pytest.mark.asyncio
    async def test_recommend_distributed_fallback_shows_records(self, monkeypatch):
        from src.api.main import app
        import src.agents.distributed as distributed_module
        from src.agents.remote import RemoteAgentError
        from src.api.models.debug import AgentCallRecord

        previous_mode = os.environ.get("EXECUTION_MODE")
        previous_endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        os.environ["EXECUTION_MODE"] = "agent_distributed"
        os.environ["FOUNDRY_PROJECT_ENDPOINT"] = "http://example.com/foundry"
        try:
            _refresh_settings()

            async def failing_invoke(self, payload):
                record = AgentCallRecord(
                    agent_name=self.agent_name,
                    url="http://fake/invoke",
                    status_code=502,
                    latency_ms=300.0,
                    error="Bad Gateway",
                    request_payload=payload,
                    response_body="Bad Gateway",
                )
                raise RemoteAgentError("Bad Gateway", record)

            monkeypatch.setattr(
                distributed_module.RemoteAnalysisProxy, "invoke", failing_invoke
            )
            monkeypatch.setattr(
                distributed_module.RemoteCandidateProxy, "invoke", failing_invoke
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/recommend?debug=true",
                    json={
                        "existing_funds": ["SPY"],
                        "candidate_funds": ["VTI"],
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["debug_info"] is not None
            assert data["debug_info"]["fallback_used"] is True
            assert len(data["debug_info"]["agents_called"]) == 2
        finally:
            _restore_env_var("EXECUTION_MODE", previous_mode)
            _restore_env_var("FOUNDRY_PROJECT_ENDPOINT", previous_endpoint)
            _refresh_settings()


# ---------------------------------------------------------------------------
# Tests for RemotePortfolioAssistantProxy (Responses protocol)
# ---------------------------------------------------------------------------


class TestRemotePortfolioAssistantProxy:
    """Verify RemotePortfolioAssistantProxy URL construction and invocation."""

    def test_url_uses_responses_protocol(self):
        from src.agents.remote import RemotePortfolioAssistantProxy

        proxy = RemotePortfolioAssistantProxy(
            "https://example.services.ai.azure.com/api/projects/my-project"
        )
        url = proxy._build_url()
        assert "/protocols/openai/v1/responses" in url
        assert "api-version=" in url
        assert "/agents/portfolio-assistant/" in url

    def test_custom_agent_name(self):
        from src.agents.remote import RemotePortfolioAssistantProxy

        proxy = RemotePortfolioAssistantProxy(
            "https://example.services.ai.azure.com/api/projects/my-project",
            agent_name="my-custom-assistant",
        )
        url = proxy._build_url()
        assert "/agents/my-custom-assistant/" in url

    def test_url_does_not_contain_invocations(self):
        from src.agents.remote import RemotePortfolioAssistantProxy

        proxy = RemotePortfolioAssistantProxy(
            "https://example.services.ai.azure.com/api/projects/my-project"
        )
        url = proxy._build_url()
        assert "/invocations" not in url

    @pytest.mark.asyncio
    async def test_invoke_success(self, monkeypatch):
        from src.agents.remote import RemotePortfolioAssistantProxy

        response_data = {
            "id": "resp_123",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "Analysis result"}]}],
            "output_text": "Analysis result",
        }

        async def mock_post(self_client, url, **kwargs):
            resp = httpx.Response(200, json=response_data, request=httpx.Request("POST", url))
            return resp

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        proxy = RemotePortfolioAssistantProxy("https://example.com/api/projects/test")
        result, record = await proxy.invoke("Analyse SPY and QQQ")

        assert result == response_data
        assert record.agent_name == "portfolio-assistant"
        assert record.status_code == 200
        assert record.error is None
        assert record.request_payload == {"input": "Analyse SPY and QQQ", "stream": False}
        assert record.response_body == response_data

    @pytest.mark.asyncio
    async def test_invoke_error_raises_remote_agent_error(self, monkeypatch):
        from src.agents.remote import RemotePortfolioAssistantProxy, RemoteAgentError

        async def mock_post(self_client, url, **kwargs):
            resp = httpx.Response(
                400,
                json={"error": "bad_request"},
                request=httpx.Request("POST", url),
            )
            return resp

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        proxy = RemotePortfolioAssistantProxy("https://example.com/api/projects/test")
        with pytest.raises(RemoteAgentError) as exc_info:
            await proxy.invoke("Bad request")

        assert exc_info.value.record.status_code == 400
        assert exc_info.value.record.request_payload == {"input": "Bad request", "stream": False}


# ---------------------------------------------------------------------------
# Tests for portfolio-assistant tool functions (via executors)
# ---------------------------------------------------------------------------


class TestPortfolioAssistantTools:
    """Verify that the tool functions the portfolio-assistant uses work correctly."""

    @pytest.mark.asyncio
    async def test_analysis_executor_produces_expected_keys(self):
        from src.agents.executors import AnalysisExecutor

        executor = AnalysisExecutor()
        result = await executor.run({"existing_funds": ["SPY", "QQQ"], "allocations": None})
        assert "overlap_matrix" in result
        assert "concentration" in result
        assert "data_quality" in result

    @pytest.mark.asyncio
    async def test_candidate_executor_produces_expected_keys(self):
        from src.agents.executors import CandidateExecutor

        executor = CandidateExecutor()
        result = await executor.run({"candidate_funds": ["ARKK", "SCHD"]})
        assert "normalised_candidates" in result
        assert "candidate_data_quality" in result

    @pytest.mark.asyncio
    async def test_recommendation_executor_produces_expected_keys(self):
        from src.agents.executors import RecommendationExecutor
        from src.services.portfolio_analysis import normalise_funds

        existing = normalise_funds(["SPY"])
        candidates = normalise_funds(["ARKK", "SCHD"])
        executor = RecommendationExecutor()
        result = await executor.run(
            {"existing_normalised": existing, "candidate_normalised": candidates}
        )
        assert "recommendations" in result


# ---------------------------------------------------------------------------
# Tests for agent-metadata.yaml
# ---------------------------------------------------------------------------


class TestAgentMetadata:
    """Verify the agent-metadata.yaml contains portfolio-assistant."""

    def test_metadata_has_portfolio_assistant(self):
        import yaml

        metadata_path = os.path.join(
            os.path.dirname(__file__), "..", "foundry", "agent-metadata.yaml"
        )
        with open(metadata_path) as f:
            metadata = yaml.safe_load(f)

        agent_names = [a["name"] for a in metadata["agents"]]
        assert "PortfolioAssistant" in agent_names

        assistant = next(a for a in metadata["agents"] if a["name"] == "PortfolioAssistant")
        assert assistant["protocol"] == "responses"
        assert assistant["role"] == "portfolio-assistant"
