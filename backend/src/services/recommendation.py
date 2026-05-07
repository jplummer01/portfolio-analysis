"""Shared recommendation service layer."""

from __future__ import annotations

from datetime import datetime, timezone

from src.api.models.recommendation import (
    RecommendResponse,
    ScoreBreakdown as ScoreBreakdownModel,
    ScoredCandidate as ScoredCandidateModel,
)
from src.core.disclaimer import DISCLAIMER
from src.services.portfolio_analysis import get_fund_inputs
from src.tools.normalise import NormalisedFund, normalise_holdings
from src.tools.scoring import score_candidates


def build_scored_candidates(
    existing: NormalisedFund,
    candidates: list[NormalisedFund],
) -> list[ScoredCandidateModel]:
    """Score every candidate against a single existing fund."""
    scored = score_candidates(existing, candidates)
    return [
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
    ]


def build_recommendations(
    existing_funds: list[NormalisedFund],
    candidate_funds: list[NormalisedFund],
) -> dict[str, list[ScoredCandidateModel]]:
    """Build scored candidate lists for each existing fund."""
    return {
        existing.symbol: build_scored_candidates(existing, candidate_funds)
        for existing in existing_funds
    }


async def recommend_candidates(
    existing_funds: list[str],
    candidate_funds: list[str],
) -> RecommendResponse:
    """Canonical recommendation pipeline — all execution modes call this."""
    existing_normalised = normalise_holdings(get_fund_inputs(existing_funds))
    candidate_normalised = normalise_holdings(get_fund_inputs(candidate_funds))

    return RecommendResponse(
        recommendations=build_recommendations(existing_normalised, candidate_normalised),
        disclaimer=DISCLAIMER,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
