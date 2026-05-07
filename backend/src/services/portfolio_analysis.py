"""Shared portfolio analysis service layer."""

from __future__ import annotations

from datetime import datetime, timezone

from src.api.models.analysis import (
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


def get_fund_inputs(symbols: list[str]) -> list[FundInput]:
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


def normalise_funds(symbols: list[str]) -> list[NormalisedFund]:
    """Parse stub holdings and normalise them for downstream analysis."""
    return normalise_holdings(get_fund_inputs(symbols))


def check_data_quality(symbols: list[str]) -> list[DataQualityEntry]:
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
                data_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
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


def build_overlap_summary(
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


def build_concentration_summary(
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


def build_asset_allocation_summary(
    funds: list[NormalisedFund],
    allocations: list[float] | None,
) -> AssetAllocationResponseModel:
    """Compute portfolio asset allocation metrics."""
    asset_alloc = compute_asset_allocation(funds, allocations)
    return AssetAllocationResponseModel(
        portfolio=[
            AssetAllocationEntry(asset_class=asset_class, weight=round(weight, 4))
            for asset_class, weight in asset_alloc.allocation.items()
        ],
        per_fund={
            fund: [
                AssetAllocationEntry(asset_class=asset_class, weight=round(weight, 4))
                for asset_class, weight in allocations_by_fund.items()
            ]
            for fund, allocations_by_fund in asset_alloc.per_fund.items()
        },
    )


def build_sector_exposure_summary(
    funds: list[NormalisedFund],
    allocations: list[float] | None,
) -> SectorExposureResponseModel:
    """Compute portfolio sector exposure metrics."""
    sector_exp = compute_sector_exposure(funds, allocations)
    return SectorExposureResponseModel(
        portfolio=[
            SectorExposureEntry(sector=sector, weight=round(weight, 4))
            for sector, weight in sector_exp.exposure.items()
        ],
        per_fund={
            fund: [
                SectorExposureEntry(sector=sector, weight=round(weight, 4))
                for sector, weight in sectors.items()
            ]
            for fund, sectors in sector_exp.per_fund.items()
        },
    )


def build_fee_analysis_summary(
    funds: list[NormalisedFund],
    allocations: list[float] | None,
) -> FeeAnalysisResponseModel:
    """Compute portfolio fee analysis metrics."""
    fee_result = compute_fee_analysis(funds, allocations)
    return FeeAnalysisResponseModel(
        per_fund=[
            FeeAnalysisEntry(
                symbol=symbol,
                expense_ratio=expense_ratio,
                expense_ratio_pct=f'{expense_ratio*100:.2f}%' if expense_ratio is not None else None,
            )
            for symbol, expense_ratio in fee_result.per_fund.items()
        ],
        portfolio_weighted_er=fee_result.portfolio_weighted_er,
        portfolio_weighted_er_pct=f'{fee_result.portfolio_weighted_er*100:.4f}%',
        estimated_annual_cost_per_10k=fee_result.estimated_annual_cost_per_10k,
    )


async def analyse_portfolio(
    existing_funds: list[str],
    allocations: list[float] | None = None,
) -> AnalysisResponse:
    """Canonical analysis pipeline — all execution modes call this."""
    normalised = normalise_funds(existing_funds)
    overlap_matrix, top_overlaps = build_overlap_summary(normalised)

    return AnalysisResponse(
        overlap_matrix=overlap_matrix,
        concentration=build_concentration_summary(normalised, allocations),
        top_overlaps=top_overlaps,
        data_quality=check_data_quality(existing_funds),
        asset_allocation=build_asset_allocation_summary(normalised, allocations),
        sector_exposure=build_sector_exposure_summary(normalised, allocations),
        fee_analysis=build_fee_analysis_summary(normalised, allocations),
        disclaimer=DISCLAIMER,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


_get_fund_inputs = get_fund_inputs
_check_data_quality = check_data_quality
