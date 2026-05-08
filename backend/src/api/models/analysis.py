from __future__ import annotations

from pydantic import BaseModel, Field

from src.api.models.debug import DebugInfo


class OverlapPair(BaseModel):
    """Overlap between two specific funds."""

    fund_a: str
    fund_b: str
    unweighted: float = Field(ge=0.0, le=1.0)
    weighted: float = Field(ge=0.0, le=1.0)
    shared_tickers: list[str]


class OverlapMatrix(BaseModel):
    """Full overlap matrix for a set of funds."""

    funds: list[str]
    unweighted: list[list[float]]
    weighted: list[list[float]]


class ConcentrationEntry(BaseModel):
    """A single ticker's concentration in the portfolio."""

    ticker: str
    weight: float


class ConcentrationResult(BaseModel):
    """Portfolio concentration analysis."""

    top_holdings: list[ConcentrationEntry]
    total_tickers: int
    top_10_weight: float


class DataQualityEntry(BaseModel):
    """Data quality assessment for a single fund."""

    symbol: str
    last_updated: str | None = None
    is_stale: bool = False
    holdings_count: int = 0


class AssetAllocationEntry(BaseModel):
    """A single asset class allocation."""

    asset_class: str
    weight: float


class AssetAllocationResult(BaseModel):
    """Portfolio-level asset allocation."""

    portfolio: list[AssetAllocationEntry]
    per_fund: dict[str, list[AssetAllocationEntry]]


class SectorExposureEntry(BaseModel):
    """A single sector exposure."""

    sector: str
    weight: float


class SectorExposureResult(BaseModel):
    """Portfolio-level sector exposure."""

    portfolio: list[SectorExposureEntry]
    per_fund: dict[str, list[SectorExposureEntry]]


class FeeAnalysisEntry(BaseModel):
    """Fee analysis for a single fund."""

    symbol: str
    expense_ratio: float | None = None
    expense_ratio_pct: str | None = None


class FeeAnalysisResult(BaseModel):
    """Portfolio-level fee analysis."""

    per_fund: list[FeeAnalysisEntry]
    portfolio_weighted_er: float
    portfolio_weighted_er_pct: str
    estimated_annual_cost_per_10k: float


class AnalyseRequest(BaseModel):
    """Request to analyse existing portfolio."""

    existing_funds: list[str] = Field(min_length=1)
    allocations: list[float] | None = None


class AnalysisResponse(BaseModel):
    """Full analysis response."""

    overlap_matrix: OverlapMatrix
    concentration: ConcentrationResult
    top_overlaps: list[OverlapPair]
    data_quality: list[DataQualityEntry]
    asset_allocation: AssetAllocationResult
    sector_exposure: SectorExposureResult
    fee_analysis: FeeAnalysisResult
    disclaimer: str
    timestamp: str
    debug_info: DebugInfo | None = None
