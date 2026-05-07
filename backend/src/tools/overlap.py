"""Overlap computation tools."""

from src.tools.normalise import NormalisedFund


class OverlapResult:
    """Result of overlap computation between two funds."""

    def __init__(
        self,
        fund_a: str,
        fund_b: str,
        unweighted: float,
        weighted: float,
        shared_tickers: list[str],
    ) -> None:
        self.fund_a = fund_a
        self.fund_b = fund_b
        self.unweighted = unweighted
        self.weighted = weighted
        self.shared_tickers = shared_tickers


def compute_overlap(fund_a: NormalisedFund, fund_b: NormalisedFund) -> OverlapResult:
    """Compute overlap between two funds.

    Unweighted: len(shared) / min(len(A), len(B))
    Weighted: sum(min(wA[t], wB[t]) for t in shared)
    """
    shared = fund_a.tickers & fund_b.tickers

    # Unweighted overlap
    min_size = min(len(fund_a.holdings), len(fund_b.holdings))
    if min_size == 0:
        unweighted = 0.0
    else:
        unweighted = len(shared) / min_size

    # Weighted overlap
    weighted = sum(
        min(fund_a.holdings[ticker], fund_b.holdings[ticker]) for ticker in shared
    )

    return OverlapResult(
        fund_a=fund_a.symbol,
        fund_b=fund_b.symbol,
        unweighted=round(unweighted, 4),
        weighted=round(weighted, 4),
        shared_tickers=sorted(shared),
    )


def compute_overlap_matrix(
    funds: list[NormalisedFund],
) -> tuple[list[str], list[list[float]], list[list[float]]]:
    """Compute full overlap matrix for a list of funds.

    Returns:
        Tuple of (fund_symbols, unweighted_matrix, weighted_matrix)
    """
    n = len(funds)
    symbols = [f.symbol for f in funds]
    unweighted = [[0.0] * n for _ in range(n)]
    weighted = [[0.0] * n for _ in range(n)]

    for i in range(n):
        unweighted[i][i] = 1.0
        weighted[i][i] = 1.0
        for j in range(i + 1, n):
            result = compute_overlap(funds[i], funds[j])
            unweighted[i][j] = result.unweighted
            unweighted[j][i] = result.unweighted
            weighted[i][j] = result.weighted
            weighted[j][i] = result.weighted

    return symbols, unweighted, weighted
