"""Fee analysis computation."""

from src.data.stub_holdings import STUB_FUND_METADATA
from src.tools.normalise import NormalisedFund


class FeeAnalysisResult:
    """Portfolio-level fee analysis."""

    def __init__(
        self,
        per_fund: dict[str, float | None],
        portfolio_weighted_er: float,
        estimated_annual_cost_per_10k: float,
    ) -> None:
        self.per_fund = per_fund  # fund_symbol -> expense_ratio (or None)
        self.portfolio_weighted_er = portfolio_weighted_er
        self.estimated_annual_cost_per_10k = estimated_annual_cost_per_10k


def compute_fee_analysis(
    funds: list[NormalisedFund],
    allocations: list[float] | None = None,
) -> FeeAnalysisResult:
    """Compute portfolio-level fee analysis from fund expense ratios.

    Returns per-fund expense ratios, portfolio-weighted average,
    and estimated annual cost per $10,000 invested.
    """
    n = len(funds)
    if not funds:
        return FeeAnalysisResult(per_fund={}, portfolio_weighted_er=0.0, estimated_annual_cost_per_10k=0.0)

    if allocations is None or len(allocations) != n:
        alloc = [1.0 / n] * n
    else:
        total = sum(allocations)
        alloc = [a / total for a in allocations] if total > 0 else [1.0 / n] * n

    per_fund: dict[str, float | None] = {}
    weighted_er = 0.0

    for i, fund in enumerate(funds):
        meta = STUB_FUND_METADATA.get(fund.symbol)
        if meta and "expense_ratio" in meta:
            er = meta["expense_ratio"]
            per_fund[fund.symbol] = er
            weighted_er += alloc[i] * er
        else:
            per_fund[fund.symbol] = None

    cost_per_10k = round(weighted_er * 10000, 2)

    return FeeAnalysisResult(
        per_fund=per_fund,
        portfolio_weighted_er=round(weighted_er, 6),
        estimated_annual_cost_per_10k=cost_per_10k,
    )


def get_expense_ratio(symbol: str) -> float | None:
    """Get expense ratio for a fund symbol. Used by scoring."""
    meta = STUB_FUND_METADATA.get(symbol)
    if meta and "expense_ratio" in meta:
        return meta["expense_ratio"]
    return None
