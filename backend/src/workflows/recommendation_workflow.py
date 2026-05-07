"""MAF orchestration for recommendations."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, TypeVar

from src.api.models.ingest import FundInput, Holding
from src.api.models.recommendation import (
    RecommendRequest,
    RecommendResponse,
    ScoreBreakdown as ScoreBreakdownModel,
    ScoredCandidate as ScoredCandidateModel,
)
from src.core.disclaimer import DISCLAIMER
from src.data.stub_holdings import STUB_HOLDINGS
from src.tools.normalise import NormalisedFund, normalise_holdings
from src.tools.scoring import score_candidates

DecoratorFunction = TypeVar("DecoratorFunction", bound=Callable[..., Awaitable[Any]])

try:
    from agent_framework import step, workflow

    AGENT_FRAMEWORK_AVAILABLE = True
except Exception:  # pragma: no cover - exercised via fallback path
    AGENT_FRAMEWORK_AVAILABLE = False

    def step(func: DecoratorFunction) -> DecoratorFunction:
        return func

    def workflow(func: DecoratorFunction) -> DecoratorFunction:
        return func


def _get_fund_inputs(symbols: list[str]) -> list[FundInput]:
    """Get FundInput objects for given symbols from stub data."""
    funds: list[FundInput] = []
    for symbol in symbols:
        clean = symbol.strip().upper()
        if clean in STUB_HOLDINGS:
            holdings = [Holding(ticker=t, weight=w) for t, w in STUB_HOLDINGS[clean].items()]
            funds.append(FundInput(symbol=clean, holdings=holdings))
        else:
            funds.append(FundInput(symbol=clean, holdings=[]))
    return funds


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
    scored = score_candidates(existing, candidates)
    return (
        existing.symbol,
        [
            ScoredCandidateModel(
                symbol=candidate.symbol,
                total_score=round(candidate.total_score, 2),
                breakdown=ScoreBreakdownModel(
                    overlap_reduction=candidate.breakdown.overlap_reduction,
                    performance=candidate.breakdown.performance,
                    data_quality_penalty=candidate.breakdown.data_quality_penalty,
                    cost_penalty=candidate.breakdown.cost_penalty,
                ),
                explanation=candidate.explanation,
            )
            for candidate in scored
        ],
    )


async def run_recommendation_pipeline(request: RecommendRequest) -> RecommendResponse:
    """Run the recommendation pipeline as a plain async function."""
    existing_funds, candidate_funds = await asyncio.gather(
        parse_and_normalise_existing_funds(request.existing_funds),
        parse_and_normalise_candidate_funds(request.candidate_funds),
    )

    scored_results = await asyncio.gather(
        *(
            score_candidates_for_existing_fund(existing_fund, candidate_funds)
            for existing_fund in existing_funds
        )
    )

    return RecommendResponse(
        recommendations={symbol: scored for symbol, scored in scored_results},
        disclaimer=DISCLAIMER,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@workflow
async def recommendation_workflow(request: RecommendRequest) -> RecommendResponse:
    """MAF workflow wrapper for the recommendation pipeline."""
    return await run_recommendation_pipeline(request)


async def execute_recommendation_workflow(request: RecommendRequest) -> RecommendResponse:
    """Execute the recommendation workflow via MAF when available."""
    if hasattr(recommendation_workflow, "run"):
        result = await recommendation_workflow.run(request)
        outputs = result.get_outputs()
        if outputs:
            return outputs[-1]
        raise RuntimeError("Recommendation workflow completed without an output")

    return await recommendation_workflow(request)
