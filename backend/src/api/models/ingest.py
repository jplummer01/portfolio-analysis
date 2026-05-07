from pydantic import BaseModel, Field


class Holding(BaseModel):
    """A single holding within a fund."""

    ticker: str
    weight: float = Field(ge=0.0, le=1.0)


class FundInput(BaseModel):
    """Raw fund input before normalization."""

    symbol: str
    holdings: list[Holding] = Field(default_factory=list)


class SymbolsRequest(BaseModel):
    """Request to ingest funds by symbol."""

    symbols: list[str] = Field(min_length=1)


class PasteRequest(BaseModel):
    """Request to ingest funds from pasted text."""

    text: str = Field(min_length=1)


class IngestResponse(BaseModel):
    """Response from any ingestion endpoint."""

    funds: list[FundInput]
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str
    timestamp: str
