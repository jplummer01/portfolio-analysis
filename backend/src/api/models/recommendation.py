from __future__ import annotations

from pydantic import BaseModel, Field

from src.api.models.debug import DebugInfo


class ScoreBreakdown(BaseModel):
    """Component breakdown of a candidate's score."""

    overlap_reduction: float = Field(ge=0.0, le=50.0)
    performance: float = Field(ge=0.0, le=40.0)
    data_quality_penalty: float = Field(ge=-20.0, le=0.0)
    cost_penalty: float = Field(ge=-10.0, le=0.0)


class ScoredCandidate(BaseModel):
    """A scored candidate fund."""

    symbol: str
    total_score: float
    breakdown: ScoreBreakdown
    explanation: str


class RecommendRequest(BaseModel):
    """Request for candidate recommendations."""

    existing_funds: list[str] = Field(min_length=1)
    candidate_funds: list[str] = Field(min_length=1)
    allocations: list[float] | None = None


class RecommendResponse(BaseModel):
    """Recommendation results."""

    recommendations: dict[str, list[ScoredCandidate]]
    disclaimer: str
    timestamp: str
    debug_info: DebugInfo | None = None
