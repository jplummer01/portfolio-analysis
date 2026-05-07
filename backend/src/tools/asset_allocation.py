"""Asset allocation computation."""

from src.data.stub_holdings import STUB_FUND_METADATA, STUB_HOLDING_METADATA
from src.tools.normalise import NormalisedFund


class AssetAllocationResult:
    """Portfolio-level asset allocation breakdown."""

    def __init__(self, allocation: dict[str, float], per_fund: dict[str, dict[str, float]]) -> None:
        self.allocation = allocation  # asset_class -> weight
        self.per_fund = per_fund  # fund_symbol -> {asset_class -> weight}


def compute_asset_allocation(
    funds: list[NormalisedFund],
    allocations: list[float] | None = None,
) -> AssetAllocationResult:
    """Compute portfolio-level asset allocation from fund holdings.

    Uses fund-level asset_class_mix from stub data when available,
    falls back to per-holding metadata.
    """
    n = len(funds)
    if not funds:
        return AssetAllocationResult(allocation={}, per_fund={})

    if allocations is None or len(allocations) != n:
        alloc = [1.0 / n] * n
    else:
        total = sum(allocations)
        alloc = [a / total for a in allocations] if total > 0 else [1.0 / n] * n

    per_fund: dict[str, dict[str, float]] = {}
    portfolio_allocation: dict[str, float] = {}

    for i, fund in enumerate(funds):
        fund_meta = STUB_FUND_METADATA.get(fund.symbol)

        if fund_meta and "asset_class_mix" in fund_meta:
            # Use fund-level asset class mix
            fund_alloc = dict(fund_meta["asset_class_mix"])
        else:
            # Derive from per-holding metadata
            fund_alloc: dict[str, float] = {}
            classified_weight = 0.0
            for ticker, weight in fund.holdings.items():
                meta = STUB_HOLDING_METADATA.get(ticker, {})
                asset_class = meta.get("asset_class", "Other")
                fund_alloc[asset_class] = fund_alloc.get(asset_class, 0.0) + weight
                classified_weight += weight
            # Assign unclassified remainder to "Other"
            if classified_weight < 1.0:
                fund_alloc["Other"] = fund_alloc.get("Other", 0.0) + (1.0 - classified_weight)

        per_fund[fund.symbol] = fund_alloc

        # Accumulate to portfolio level
        for asset_class, weight in fund_alloc.items():
            portfolio_allocation[asset_class] = (
                portfolio_allocation.get(asset_class, 0.0) + alloc[i] * weight
            )

    # Sort by weight descending
    sorted_alloc = dict(
        sorted(portfolio_allocation.items(), key=lambda x: x[1], reverse=True)
    )

    return AssetAllocationResult(allocation=sorted_alloc, per_fund=per_fund)
