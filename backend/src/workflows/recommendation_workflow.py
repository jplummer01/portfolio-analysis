"""MAF orchestration for recommendations."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar

from src.api.models.recommendation import (
    RecommendRequest,
    RecommendResponse,
    ScoredCandidate as ScoredCandidateModel,
)
from src.services.portfolio_analysis import get_fund_inputs as _get_fund_inputs
from src.services.recommendation import build_scored_candidates, recommend_candidates
from src.tools.normalise import NormalisedFund, normalise_holdings

DecoratorFunction = TypeVar('DecoratorFunction', bound=Callable[..., Awaitable[Any]])

try:
    from agent_framework import step, workflow

    AGENT_FRAMEWORK_AVAILABLE = True
except Exception:  # pragma: no cover - exercised via fallback path
    AGENT_FRAMEWORK_AVAILABLE = False

    def step(func: DecoratorFunction) -> DecoratorFunction:
        return func

    def workflow(func: DecoratorFunction) -> DecoratorFunction:
        return func


@step
async def parse_and_normalise_existing_funds(symbols: list[str]) -> list[NormalisedFund]:
    """Parse and normalise the existing portfolio funds."""
    return normalise_holdings(_get_fund_inputs(symbols))


@step
async def parse_and_normalise_candidate_funds(symbols: list[str]) -> list[NormalisedFund]:
    """Parse and normalise the candidate fund universe."""
    return normalise_holdings(_get_fund_inputs(symbols))


@step
async def score_candidates_for_existing_fund(
    existing: NormalisedFund,
    candidates: list[NormalisedFund],
) -> tuple[str, list[ScoredCandidateModel]]:
    """Score every candidate against a single existing fund."""
    return existing.symbol, build_scored_candidates(existing, candidates)


async def run_recommendation_pipeline(request: RecommendRequest) -> RecommendResponse:
    """Run the recommendation pipeline as a plain async function."""
    return await recommend_candidates(request.existing_funds, request.candidate_funds)


@workflow
async def recommendation_workflow(request: RecommendRequest) -> RecommendResponse:
    """MAF workflow wrapper for the recommendation pipeline."""
    return await run_recommendation_pipeline(request)


async def execute_recommendation_workflow(request: RecommendRequest) -> RecommendResponse:
    """Execute the recommendation workflow via MAF when available."""
    if hasattr(recommendation_workflow, 'run'):
        result = await recommendation_workflow.run(request)
        outputs = result.get_outputs()
        if outputs:
            return outputs[-1]
        raise RuntimeError('Recommendation workflow completed without an output')

    return await recommendation_workflow(request)
