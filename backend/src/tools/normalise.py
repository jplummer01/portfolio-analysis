"""Normalisation tools for fund holdings data."""

from src.api.models.ingest import FundInput, Holding


class NormalisedFund:
    """A fund with normalised holdings (weights sum to 1.0, tickers uppercase, deduped)."""

    def __init__(self, symbol: str, holdings: dict[str, float]) -> None:
        self.symbol = symbol
        self.holdings = holdings  # ticker -> normalised weight

    @property
    def tickers(self) -> set[str]:
        return set(self.holdings.keys())

    def __repr__(self) -> str:
        return f"NormalisedFund({self.symbol}, {len(self.holdings)} holdings)"


def normalise_holdings(funds: list[FundInput]) -> list[NormalisedFund]:
    """Normalise fund holdings.

    - Uppercase ticker symbols
    - Deduplicate tickers (sum weights for duplicates)
    - Normalise weights to sum to 1.0
    """
    result: list[NormalisedFund] = []

    for fund in funds:
        if not fund.holdings:
            result.append(NormalisedFund(symbol=fund.symbol, holdings={}))
            continue

        # Deduplicate: sum weights for same ticker
        merged: dict[str, float] = {}
        for holding in fund.holdings:
            ticker = holding.ticker.strip().upper()
            if ticker:
                merged[ticker] = merged.get(ticker, 0.0) + holding.weight

        # Normalise weights to sum to 1.0
        total_weight = sum(merged.values())
        if total_weight > 0:
            normalised = {
                ticker: weight / total_weight for ticker, weight in merged.items()
            }
        else:
            normalised = merged

        result.append(NormalisedFund(symbol=fund.symbol, holdings=normalised))

    return result
