"""Tests for normalisation tools."""

import pytest

from src.api.models.ingest import FundInput, Holding
from src.tools.normalise import normalise_holdings


class TestNormaliseHoldings:
    def test_weights_sum_to_one(self):
        fund = FundInput(
            symbol="TEST",
            holdings=[
                Holding(ticker="AAPL", weight=0.3),
                Holding(ticker="MSFT", weight=0.2),
                Holding(ticker="GOOGL", weight=0.1),
            ],
        )
        result = normalise_holdings([fund])
        assert len(result) == 1
        total = sum(result[0].holdings.values())
        assert abs(total - 1.0) < 1e-10

    def test_already_normalised(self):
        fund = FundInput(
            symbol="TEST",
            holdings=[
                Holding(ticker="AAPL", weight=0.5),
                Holding(ticker="MSFT", weight=0.5),
            ],
        )
        result = normalise_holdings([fund])
        assert abs(result[0].holdings["AAPL"] - 0.5) < 1e-10
        assert abs(result[0].holdings["MSFT"] - 0.5) < 1e-10

    def test_uppercase_tickers(self):
        fund = FundInput(
            symbol="TEST",
            holdings=[
                Holding(ticker="aapl", weight=0.5),
                Holding(ticker="Msft", weight=0.5),
            ],
        )
        result = normalise_holdings([fund])
        assert "AAPL" in result[0].holdings
        assert "MSFT" in result[0].holdings

    def test_deduplication(self):
        fund = FundInput(
            symbol="TEST",
            holdings=[
                Holding(ticker="AAPL", weight=0.3),
                Holding(ticker="AAPL", weight=0.2),
                Holding(ticker="MSFT", weight=0.5),
            ],
        )
        result = normalise_holdings([fund])
        assert len(result[0].holdings) == 2
        # AAPL weight should be 0.3 + 0.2 = 0.5, normalised = 0.5
        assert abs(result[0].holdings["AAPL"] - 0.5) < 1e-10

    def test_empty_holdings(self):
        fund = FundInput(symbol="TEST", holdings=[])
        result = normalise_holdings([fund])
        assert len(result) == 1
        assert len(result[0].holdings) == 0

    def test_multiple_funds(self):
        funds = [
            FundInput(
                symbol="FUND1",
                holdings=[Holding(ticker="AAPL", weight=1.0)],
            ),
            FundInput(
                symbol="FUND2",
                holdings=[Holding(ticker="MSFT", weight=1.0)],
            ),
        ]
        result = normalise_holdings(funds)
        assert len(result) == 2
        assert result[0].symbol == "FUND1"
        assert result[1].symbol == "FUND2"

    def test_whitespace_in_tickers(self):
        fund = FundInput(
            symbol="TEST",
            holdings=[Holding(ticker="  AAPL  ", weight=1.0)],
        )
        result = normalise_holdings([fund])
        assert "AAPL" in result[0].holdings
