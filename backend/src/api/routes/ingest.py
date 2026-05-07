"""Ingestion routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, File, UploadFile

from src.api.models.ingest import FundInput, IngestResponse, PasteRequest, SymbolsRequest
from src.core.disclaimer import DISCLAIMER
from src.tools.parsing import parse_csv, parse_json, parse_paste, parse_symbols

router = APIRouter(prefix="/api/ingest")


@router.post("/symbols", response_model=IngestResponse)
async def ingest_symbols(request: SymbolsRequest) -> IngestResponse:
    """Ingest funds by symbol."""
    funds, warnings = parse_symbols(request.symbols)
    return IngestResponse(
        funds=funds,
        warnings=warnings,
        disclaimer=DISCLAIMER,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/paste", response_model=IngestResponse)
async def ingest_paste(request: PasteRequest) -> IngestResponse:
    """Ingest funds from pasted text."""
    funds, warnings = parse_paste(request.text)
    return IngestResponse(
        funds=funds,
        warnings=warnings,
        disclaimer=DISCLAIMER,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/upload", response_model=IngestResponse)
async def ingest_upload(file: UploadFile = File(...)) -> IngestResponse:
    """Ingest funds from uploaded CSV or JSON file."""
    content = await file.read()
    warnings: list[str] = []
    funds: list[FundInput] = []

    filename = (file.filename or "").lower()

    if filename.endswith(".json"):
        funds, warnings = parse_json(content)
    elif filename.endswith(".csv"):
        funds, warnings = parse_csv(content)
    else:
        # Try to detect format
        try:
            funds, warnings = parse_json(content)
        except (ValueError, KeyError):
            try:
                funds, warnings = parse_csv(content)
            except Exception:
                warnings.append(
                    "Could not determine file format. Please use .csv or .json extension."
                )

    return IngestResponse(
        funds=funds,
        warnings=warnings,
        disclaimer=DISCLAIMER,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
