"""Portfolio concentration computation."""

from src.tools.normalise import NormalisedFund


class ConcentrationResult:
    """Result of portfolio concentration analysis."""

    def __init__(
        self,
        top_holdings: list[tuple[str, float]],
        total_tickers: int,
        top_10_weight: float,
    ) -> None:
        self.top_holdings = top_holdings  # (ticker, portfolio_weight)
        self.total_tickers = total_tickers
        self.top_10_weight = top_10_weight


def compute_concentration(
    funds: list[NormalisedFund],
    allocations: list[float] | None = None,
) -> ConcentrationResult:
    """Compute portfolio-level concentration.

    Portfolio concentration = sum(allocation_i * holding_weight_ij) per ticker.

    If allocations not provided, equal-weight across funds.
    """
    n = len(funds)
    if not funds:
        return ConcentrationResult(top_holdings=[], total_tickers=0, top_10_weight=0.0)

    # Default to equal allocation
    if allocations is None or len(allocations) != n:
        alloc = [1.0 / n] * n
    else:
        # Normalise allocations to sum to 1.0
        total = sum(allocations)
        if total > 0:
            alloc = [a / total for a in allocations]
        else:
            alloc = [1.0 / n] * n

    # Compute portfolio-level weight for each ticker
    portfolio_weights: dict[str, float] = {}
    for i, fund in enumerate(funds):
        for ticker, weight in fund.holdings.items():
            portfolio_weights[ticker] = (
                portfolio_weights.get(ticker, 0.0) + alloc[i] * weight
            )

    # Sort by weight descending
    sorted_holdings = sorted(portfolio_weights.items(), key=lambda x: x[1], reverse=True)
    total_tickers = len(sorted_holdings)
    top_10 = sorted_holdings[:10]
    top_10_weight = sum(w for _, w in top_10)

    return ConcentrationResult(
        top_holdings=sorted_holdings[:25],
        total_tickers=total_tickers,
        top_10_weight=round(top_10_weight, 4),
    )
