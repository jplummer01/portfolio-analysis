"""Recommendation routes."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from src.api.models.ingest import FundInput, Holding
from src.api.models.recommendation import (
    RecommendRequest,
    RecommendResponse,
    ScoreBreakdown as ScoreBreakdownModel,
    ScoredCandidate as ScoredCandidateModel,
)
from src.core.disclaimer import DISCLAIMER
from src.core.config import settings
from src.data.stub_holdings import STUB_HOLDINGS
from src.tools.normalise import normalise_holdings
from src.tools.scoring import score_candidates
import src.workflows.recommendation_workflow as recommendation_workflows

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_fund_inputs(symbols: list[str]) -> list[FundInput]:
    """Get FundInput objects for given symbols from stub data."""
    funds: list[FundInput] = []
    for symbol in symbols:
        clean = symbol.strip().upper()
        if clean in STUB_HOLDINGS:
            holdings = [
                Holding(ticker=t, weight=w) for t, w in STUB_HOLDINGS[clean].items()
            ]
            funds.append(FundInput(symbol=clean, holdings=holdings))
        else:
            funds.append(FundInput(symbol=clean, holdings=[]))
    return funds


def _build_recommendation_response(request: RecommendRequest) -> RecommendResponse:
    """Build recommendations directly from deterministic tools."""
    # Get and normalise fund data
    existing_inputs = _get_fund_inputs(request.existing_funds)
    candidate_inputs = _get_fund_inputs(request.candidate_funds)

    existing_normalised = normalise_holdings(existing_inputs)
    candidate_normalised = normalise_holdings(candidate_inputs)

    # Score candidates for each existing fund
    recommendations: dict[str, list[ScoredCandidateModel]] = {}

    for existing in existing_normalised:
        scored = score_candidates(existing, candidate_normalised)
        recommendations[existing.symbol] = [
            ScoredCandidateModel(
                symbol=s.symbol,
                total_score=round(s.total_score, 2),
                breakdown=ScoreBreakdownModel(
                    overlap_reduction=s.breakdown.overlap_reduction,
                    performance=s.breakdown.performance,
                    data_quality_penalty=s.breakdown.data_quality_penalty,
                    cost_penalty=s.breakdown.cost_penalty,
                ),
                explanation=s.explanation,
            )
            for s in scored
        ]

    return RecommendResponse(
        recommendations=recommendations,
        disclaimer=DISCLAIMER,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/api/recommend", response_model=RecommendResponse)
async def recommend(request: RecommendRequest) -> RecommendResponse:
    """Generate candidate recommendations for each existing fund."""
    if not request.existing_funds:
        raise HTTPException(
            status_code=400, detail="At least one existing fund is required"
        )
    if not request.candidate_funds:
        raise HTTPException(
            status_code=400, detail="At least one candidate fund is required"
        )

    if settings.use_workflows:
        try:
            return await recommendation_workflows.execute_recommendation_workflow(request)
        except Exception as exc:
            logger.warning(
                "Recommendation workflow failed; falling back to direct tools: %s",
                exc,
            )

    return _build_recommendation_response(request)
