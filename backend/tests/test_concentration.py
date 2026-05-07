"""Tests for concentration computation."""

import pytest

from src.tools.concentration import compute_concentration
from src.tools.normalise import NormalisedFund


class TestComputeConcentration:
    def test_single_fund_equal_alloc(self):
        fund = NormalisedFund("TEST", {"AAPL": 0.5, "MSFT": 0.3, "GOOGL": 0.2})
        result = compute_concentration([fund])
        assert result.total_tickers == 3
        # With single fund, portfolio weights = fund weights
        assert result.top_holdings[0] == ("AAPL", 0.5)
        assert result.top_holdings[1] == ("MSFT", 0.3)
        assert result.top_holdings[2] == ("GOOGL", 0.2)

    def test_two_funds_equal_alloc(self):
        fund_a = NormalisedFund("A", {"AAPL": 0.6, "MSFT": 0.4})
        fund_b = NormalisedFund("B", {"GOOGL": 0.5, "AMZN": 0.5})
        result = compute_concentration([fund_a, fund_b])
        # Equal alloc: each fund gets 50%
        # AAPL: 0.5 * 0.6 = 0.3, MSFT: 0.5 * 0.4 = 0.2
        # GOOGL: 0.5 * 0.5 = 0.25, AMZN: 0.5 * 0.5 = 0.25
        assert result.total_tickers == 4
        weights = dict(result.top_holdings)
        assert abs(weights["AAPL"] - 0.3) < 1e-10
        assert abs(weights["MSFT"] - 0.2) < 1e-10
        assert abs(weights["GOOGL"] - 0.25) < 1e-10
        assert abs(weights["AMZN"] - 0.25) < 1e-10

    def test_custom_allocations(self):
        fund_a = NormalisedFund("A", {"AAPL": 1.0})
        fund_b = NormalisedFund("B", {"MSFT": 1.0})
        result = compute_concentration([fund_a, fund_b], allocations=[0.8, 0.2])
        weights = dict(result.top_holdings)
        assert abs(weights["AAPL"] - 0.8) < 1e-10
        assert abs(weights["MSFT"] - 0.2) < 1e-10

    def test_overlapping_holdings(self):
        fund_a = NormalisedFund("A", {"AAPL": 0.6, "MSFT": 0.4})
        fund_b = NormalisedFund("B", {"AAPL": 0.4, "GOOGL": 0.6})
        result = compute_concentration([fund_a, fund_b])
        # AAPL: 0.5*0.6 + 0.5*0.4 = 0.5
        weights = dict(result.top_holdings)
        assert abs(weights["AAPL"] - 0.5) < 1e-10
        assert result.total_tickers == 3

    def test_empty_funds(self):
        result = compute_concentration([])
        assert result.total_tickers == 0
        assert result.top_10_weight == 0.0

    def test_top_10_weight(self):
        # Create a fund with 15 holdings
        holdings = {f"TICK{i}": 1.0 / 15 for i in range(15)}
        fund = NormalisedFund("BIG", holdings)
        result = compute_concentration([fund])
        assert result.total_tickers == 15
        # Top 10 should hold 10/15 of weight
        assert abs(result.top_10_weight - 10.0 / 15) < 0.01

    def test_allocations_normalised(self):
        """Allocations that don't sum to 1 should be normalised."""
        fund_a = NormalisedFund("A", {"AAPL": 1.0})
        fund_b = NormalisedFund("B", {"MSFT": 1.0})
        result = compute_concentration([fund_a, fund_b], allocations=[60, 40])
        weights = dict(result.top_holdings)
        assert abs(weights["AAPL"] - 0.6) < 1e-10
        assert abs(weights["MSFT"] - 0.4) < 1e-10
