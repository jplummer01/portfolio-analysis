from pydantic import BaseModel, Field


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
    disclaimer: str
    timestamp: str
