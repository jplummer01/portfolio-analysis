"""Analysis routes."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from src.api.models.analysis import (
    AnalyseRequest,
    AnalysisResponse,
    AssetAllocationEntry,
    AssetAllocationResult as AssetAllocationResponseModel,
    ConcentrationEntry,
    ConcentrationResult as ConcentrationResponseModel,
    DataQualityEntry,
    FeeAnalysisEntry,
    FeeAnalysisResult as FeeAnalysisResponseModel,
    OverlapMatrix,
    OverlapPair,
    SectorExposureEntry,
    SectorExposureResult as SectorExposureResponseModel,
)
from src.api.models.ingest import FundInput, Holding
from src.core.disclaimer import DISCLAIMER
from src.core.config import settings
from src.data.stub_holdings import STUB_DATA_TIMESTAMPS, STUB_HOLDINGS
from src.tools.asset_allocation import compute_asset_allocation
from src.tools.concentration import compute_concentration
from src.tools.fees import compute_fee_analysis
from src.tools.normalise import normalise_holdings
from src.tools.overlap import compute_overlap, compute_overlap_matrix
from src.tools.sector_exposure import compute_sector_exposure
import src.workflows.analysis_workflow as analysis_workflows

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


def _check_data_quality(symbols: list[str]) -> list[DataQualityEntry]:
    """Check data quality for a list of fund symbols."""
    now = datetime.now(timezone.utc)
    entries: list[DataQualityEntry] = []

    for symbol in symbols:
        clean = symbol.strip().upper()
        timestamp_str = STUB_DATA_TIMESTAMPS.get(clean)
        holdings_count = len(STUB_HOLDINGS.get(clean, {}))

        is_stale = False
        if timestamp_str:
            try:
                data_time = datetime.fromisoformat(
                    timestamp_str.replace("Z", "+00:00")
                )
                age_days = (now - data_time).days
                is_stale = age_days > 90
            except ValueError:
                is_stale = True
        else:
            is_stale = True

        entries.append(
            DataQualityEntry(
                symbol=clean,
                last_updated=timestamp_str,
                is_stale=is_stale,
                holdings_count=holdings_count,
            )
        )

    return entries


def _build_analysis_response(request: AnalyseRequest) -> AnalysisResponse:
    """Build the analysis response directly from deterministic tools."""
    # Get fund data and normalise
    fund_inputs = _get_fund_inputs(request.existing_funds)
    normalised = normalise_holdings(fund_inputs)

    # Compute overlap matrix
    symbols, unweighted, weighted = compute_overlap_matrix(normalised)

    # Compute concentration
    concentration = compute_concentration(normalised, request.allocations)

    # Find top overlaps (pairs with highest overlap)
    top_overlaps: list[OverlapPair] = []
    n = len(normalised)
    for i in range(n):
        for j in range(i + 1, n):
            result = compute_overlap(normalised[i], normalised[j])
            top_overlaps.append(
                OverlapPair(
                    fund_a=result.fund_a,
                    fund_b=result.fund_b,
                    unweighted=result.unweighted,
                    weighted=result.weighted,
                    shared_tickers=result.shared_tickers,
                )
            )

    # Sort by weighted overlap descending
    top_overlaps.sort(key=lambda x: x.weighted, reverse=True)

    # Data quality
    data_quality = _check_data_quality(request.existing_funds)

    # Asset allocation
    asset_alloc = compute_asset_allocation(normalised, request.allocations)

    # Sector exposure
    sector_exp = compute_sector_exposure(normalised, request.allocations)

    # Fee analysis
    fee_result = compute_fee_analysis(normalised, request.allocations)

    return AnalysisResponse(
        overlap_matrix=OverlapMatrix(
            funds=symbols,
            unweighted=unweighted,
            weighted=weighted,
        ),
        concentration=ConcentrationResponseModel(
            top_holdings=[
                ConcentrationEntry(ticker=t, weight=round(w, 6))
                for t, w in concentration.top_holdings
            ],
            total_tickers=concentration.total_tickers,
            top_10_weight=concentration.top_10_weight,
        ),
        top_overlaps=top_overlaps[:10],
        data_quality=data_quality,
        asset_allocation=AssetAllocationResponseModel(
            portfolio=[
                AssetAllocationEntry(asset_class=ac, weight=round(w, 4))
                for ac, w in asset_alloc.allocation.items()
            ],
            per_fund={
                fund: [
                    AssetAllocationEntry(asset_class=ac, weight=round(w, 4))
                    for ac, w in allocs.items()
                ]
                for fund, allocs in asset_alloc.per_fund.items()
            },
        ),
        sector_exposure=SectorExposureResponseModel(
            portfolio=[
                SectorExposureEntry(sector=s, weight=round(w, 4))
                for s, w in sector_exp.exposure.items()
            ],
            per_fund={
                fund: [
                    SectorExposureEntry(sector=s, weight=round(w, 4))
                    for s, w in sectors.items()
                ]
                for fund, sectors in sector_exp.per_fund.items()
            },
        ),
        fee_analysis=FeeAnalysisResponseModel(
            per_fund=[
                FeeAnalysisEntry(
                    symbol=sym,
                    expense_ratio=er,
                    expense_ratio_pct=f"{er*100:.2f}%" if er is not None else None,
                )
                for sym, er in fee_result.per_fund.items()
            ],
            portfolio_weighted_er=fee_result.portfolio_weighted_er,
            portfolio_weighted_er_pct=f"{fee_result.portfolio_weighted_er*100:.4f}%",
            estimated_annual_cost_per_10k=fee_result.estimated_annual_cost_per_10k,
        ),
        disclaimer=DISCLAIMER,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/api/analyse", response_model=AnalysisResponse)
async def analyse(request: AnalyseRequest) -> AnalysisResponse:
    """Analyse existing portfolio for overlap and concentration."""
    if not request.existing_funds:
        raise HTTPException(status_code=400, detail="At least one fund is required")

    if settings.use_workflows:
        try:
            return await analysis_workflows.execute_analysis_workflow(request)
        except Exception as exc:
            logger.warning(
                "Analysis workflow failed; falling back to direct tools: %s",
                exc,
            )

    return _build_analysis_response(request)
