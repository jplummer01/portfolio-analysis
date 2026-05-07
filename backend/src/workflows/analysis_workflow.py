"""MAF orchestration for portfolio analysis."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, TypeVar

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
from src.data.stub_holdings import STUB_DATA_TIMESTAMPS, STUB_HOLDINGS
from src.tools.asset_allocation import compute_asset_allocation
from src.tools.concentration import compute_concentration
from src.tools.fees import compute_fee_analysis
from src.tools.normalise import NormalisedFund, normalise_holdings
from src.tools.overlap import compute_overlap, compute_overlap_matrix
from src.tools.sector_exposure import compute_sector_exposure

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
                data_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
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


@step
async def parse_and_normalise_funds(symbols: list[str]) -> list[NormalisedFund]:
    """Parse stub holdings and normalise them for downstream analysis."""
    return normalise_holdings(_get_fund_inputs(symbols))


@step
async def compute_overlap_summary(
    funds: list[NormalisedFund],
) -> tuple[OverlapMatrix, list[OverlapPair]]:
    """Compute overlap matrix and ranked overlap pairs."""
    symbols, unweighted, weighted = compute_overlap_matrix(funds)

    top_overlaps: list[OverlapPair] = []
    for i in range(len(funds)):
        for j in range(i + 1, len(funds)):
            result = compute_overlap(funds[i], funds[j])
            top_overlaps.append(
                OverlapPair(
                    fund_a=result.fund_a,
                    fund_b=result.fund_b,
                    unweighted=result.unweighted,
                    weighted=result.weighted,
                    shared_tickers=result.shared_tickers,
                )
            )

    top_overlaps.sort(key=lambda overlap: overlap.weighted, reverse=True)

    return (
        OverlapMatrix(funds=symbols, unweighted=unweighted, weighted=weighted),
        top_overlaps[:10],
    )


@step
async def compute_concentration_summary(
    funds: list[NormalisedFund],
    allocations: list[float] | None,
) -> ConcentrationResponseModel:
    """Compute portfolio concentration metrics."""
    concentration = compute_concentration(funds, allocations)
    return ConcentrationResponseModel(
        top_holdings=[
            ConcentrationEntry(ticker=ticker, weight=round(weight, 6))
            for ticker, weight in concentration.top_holdings
        ],
        total_tickers=concentration.total_tickers,
        top_10_weight=concentration.top_10_weight,
    )


@step
async def compute_data_quality_summary(symbols: list[str]) -> list[DataQualityEntry]:
    """Summarise holdings freshness for all requested funds."""
    return _check_data_quality(symbols)


async def run_analysis_pipeline(request: AnalyseRequest) -> AnalysisResponse:
    """Run the analysis pipeline as a plain async function."""
    normalised = await parse_and_normalise_funds(request.existing_funds)
    overlap_result, concentration_result = await asyncio.gather(
        compute_overlap_summary(normalised),
        compute_concentration_summary(normalised, request.allocations),
    )
    overlap_matrix, top_overlaps = overlap_result
    data_quality = await compute_data_quality_summary(request.existing_funds)

    # Asset allocation
    asset_alloc = compute_asset_allocation(normalised, request.allocations)

    # Sector exposure
    sector_exp = compute_sector_exposure(normalised, request.allocations)

    # Fee analysis
    fee_result = compute_fee_analysis(normalised, request.allocations)

    return AnalysisResponse(
        overlap_matrix=overlap_matrix,
        concentration=concentration_result,
        top_overlaps=top_overlaps,
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


@workflow
async def analysis_workflow(request: AnalyseRequest) -> AnalysisResponse:
    """MAF workflow wrapper for the analysis pipeline."""
    return await run_analysis_pipeline(request)


async def execute_analysis_workflow(request: AnalyseRequest) -> AnalysisResponse:
    """Execute the analysis workflow via MAF when available."""
    if hasattr(analysis_workflow, "run"):
        result = await analysis_workflow.run(request)
        outputs = result.get_outputs()
        if outputs:
            return outputs[-1]
        raise RuntimeError("Analysis workflow completed without an output")

    return await analysis_workflow(request)
