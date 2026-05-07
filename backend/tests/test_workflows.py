"""Workflow orchestration tests."""

import pytest

from src.api.models.analysis import AnalyseRequest
from src.api.models.recommendation import RecommendRequest
from src.api.routes import analyse as analyse_route
from src.api.routes import recommend as recommend_route
from src.core.config import ExecutionMode, Settings
from src.core.disclaimer import DISCLAIMER
from src.tools.concentration import compute_concentration
from src.tools.normalise import normalise_holdings
from src.tools.overlap import compute_overlap_matrix
from src.tools.scoring import score_candidates
import src.workflows.analysis_workflow as analysis_workflows
import src.workflows.recommendation_workflow as recommendation_workflows


@pytest.mark.asyncio
async def test_analysis_pipeline_direct():
    request = AnalyseRequest(existing_funds=["SPY", "QQQ"], allocations=[0.6, 0.4])

    response = await analysis_workflows.run_analysis_pipeline(request)

    fund_inputs = analysis_workflows._get_fund_inputs(request.existing_funds)
    normalised = normalise_holdings(fund_inputs)
    symbols, unweighted, weighted = compute_overlap_matrix(normalised)
    concentration = compute_concentration(normalised, request.allocations)

    assert response.overlap_matrix.funds == symbols
    assert response.overlap_matrix.unweighted == unweighted
    assert response.overlap_matrix.weighted == weighted
    assert response.concentration.total_tickers == concentration.total_tickers
    assert response.concentration.top_10_weight == concentration.top_10_weight
    assert [entry.ticker for entry in response.concentration.top_holdings] == [
        ticker for ticker, _ in concentration.top_holdings
    ]
    assert response.top_overlaps[0].fund_a == "SPY"
    assert response.top_overlaps[0].fund_b == "QQQ"
    assert response.data_quality[0].symbol == "SPY"
    assert response.disclaimer == DISCLAIMER
    assert response.timestamp


@pytest.mark.asyncio
async def test_analysis_workflow_execution():
    request = AnalyseRequest(existing_funds=["SPY", "QQQ"])

    response = await analysis_workflows.execute_analysis_workflow(request)

    assert response.overlap_matrix.funds == ["SPY", "QQQ"]
    assert len(response.top_overlaps) == 1
    assert response.disclaimer == DISCLAIMER


@pytest.mark.asyncio
async def test_recommendation_pipeline_direct():
    request = RecommendRequest(
        existing_funds=["SPY", "QQQ"],
        candidate_funds=["ARKK", "SCHD", "VXUS"],
    )

    response = await recommendation_workflows.run_recommendation_pipeline(request)

    existing_normalised = normalise_holdings(
        recommendation_workflows._get_fund_inputs(request.existing_funds)
    )
    candidate_normalised = normalise_holdings(
        recommendation_workflows._get_fund_inputs(request.candidate_funds)
    )

    assert set(response.recommendations) == {"SPY", "QQQ"}
    for existing in existing_normalised:
        expected = score_candidates(existing, candidate_normalised)
        actual = response.recommendations[existing.symbol]
        assert [candidate.symbol for candidate in actual] == [
            candidate.symbol for candidate in expected
        ]
        assert [candidate.total_score for candidate in actual] == [
            round(candidate.total_score, 2) for candidate in expected
        ]
    assert response.disclaimer == DISCLAIMER
    assert response.timestamp


@pytest.mark.asyncio
async def test_recommendation_workflow_execution():
    request = RecommendRequest(existing_funds=["SPY"], candidate_funds=["ARKK", "SCHD"])

    response = await recommendation_workflows.execute_recommendation_workflow(request)

    assert list(response.recommendations) == ["SPY"]
    assert len(response.recommendations["SPY"]) == 2
    assert response.disclaimer == DISCLAIMER


@pytest.mark.asyncio
async def test_analyse_route_falls_back_when_workflow_fails(monkeypatch):
    monkeypatch.setattr(
        analyse_route.settings,
        "execution_mode",
        ExecutionMode.WORKFLOW,
    )

    async def fail_workflow(_request):
        raise RuntimeError("workflow unavailable")

    monkeypatch.setattr(
        analyse_route.analysis_workflows,
        "execute_analysis_workflow",
        fail_workflow,
    )

    response = await analyse_route.analyse(AnalyseRequest(existing_funds=["SPY", "QQQ"]))

    assert response.overlap_matrix.funds == ["SPY", "QQQ"]
    assert response.disclaimer == DISCLAIMER


@pytest.mark.asyncio
async def test_recommend_route_falls_back_when_workflow_fails(monkeypatch):
    monkeypatch.setattr(
        recommend_route.settings,
        "execution_mode",
        ExecutionMode.WORKFLOW,
    )

    async def fail_workflow(_request):
        raise RuntimeError("workflow unavailable")

    monkeypatch.setattr(
        recommend_route.recommendation_workflows,
        "execute_recommendation_workflow",
        fail_workflow,
    )

    response = await recommend_route.recommend(
        RecommendRequest(existing_funds=["SPY"], candidate_funds=["ARKK", "SCHD"])
    )

    assert list(response.recommendations) == ["SPY"]
    assert response.disclaimer == DISCLAIMER


def test_settings_default_execution_mode(monkeypatch):
    monkeypatch.delenv("EXECUTION_MODE", raising=False)
    monkeypatch.delenv("USE_WORKFLOWS", raising=False)

    settings = Settings()

    assert settings.execution_mode == ExecutionMode.DIRECT
    assert settings.is_direct is True
    assert settings.is_workflow is False


def test_settings_execution_mode_uses_explicit_env(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "agent_local")
    monkeypatch.setenv("USE_WORKFLOWS", "true")

    settings = Settings()

    assert settings.execution_mode == ExecutionMode.AGENT_LOCAL
    assert settings.is_agent_local is True
    assert settings.is_workflow is False


def test_settings_execution_mode_uses_legacy_workflow_flag(monkeypatch):
    monkeypatch.delenv("EXECUTION_MODE", raising=False)
    monkeypatch.setenv("USE_WORKFLOWS", "true")

    settings = Settings()

    assert settings.execution_mode == ExecutionMode.WORKFLOW
    assert settings.is_workflow is True
