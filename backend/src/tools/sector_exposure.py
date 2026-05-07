"""Sector exposure computation."""

from src.data.stub_holdings import STUB_HOLDING_METADATA
from src.tools.normalise import NormalisedFund


class SectorExposureResult:
    """Portfolio-level sector exposure breakdown."""

    def __init__(self, exposure: dict[str, float], per_fund: dict[str, dict[str, float]]) -> None:
        self.exposure = exposure  # sector -> weight
        self.per_fund = per_fund  # fund_symbol -> {sector -> weight}


def compute_sector_exposure(
    funds: list[NormalisedFund],
    allocations: list[float] | None = None,
) -> SectorExposureResult:
    """Compute portfolio-level sector exposure from per-holding metadata.

    Each holding's sector is looked up from STUB_HOLDING_METADATA.
    Holdings without metadata are classified as "Unknown".
    """
    n = len(funds)
    if not funds:
        return SectorExposureResult(exposure={}, per_fund={})

    if allocations is None or len(allocations) != n:
        alloc = [1.0 / n] * n
    else:
        total = sum(allocations)
        alloc = [a / total for a in allocations] if total > 0 else [1.0 / n] * n

    per_fund: dict[str, dict[str, float]] = {}
    portfolio_exposure: dict[str, float] = {}

    for i, fund in enumerate(funds):
        fund_sectors: dict[str, float] = {}
        for ticker, weight in fund.holdings.items():
            meta = STUB_HOLDING_METADATA.get(ticker, {})
            sector = meta.get("sector", "Unknown")
            fund_sectors[sector] = fund_sectors.get(sector, 0.0) + weight

        per_fund[fund.symbol] = dict(
            sorted(fund_sectors.items(), key=lambda x: x[1], reverse=True)
        )

        for sector, weight in fund_sectors.items():
            portfolio_exposure[sector] = (
                portfolio_exposure.get(sector, 0.0) + alloc[i] * weight
            )

    sorted_exposure = dict(
        sorted(portfolio_exposure.items(), key=lambda x: x[1], reverse=True)
    )

    return SectorExposureResult(exposure=sorted_exposure, per_fund=per_fund)
