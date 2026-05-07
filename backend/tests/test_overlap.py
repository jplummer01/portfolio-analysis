"""Tests for overlap computation."""

import pytest

from src.api.models.ingest import FundInput, Holding
from src.tools.normalise import NormalisedFund, normalise_holdings
from src.tools.overlap import compute_overlap, compute_overlap_matrix


class TestComputeOverlap:
    def test_identical_funds(self):
        fund = NormalisedFund("TEST", {"AAPL": 0.5, "MSFT": 0.5})
        result = compute_overlap(fund, fund)
        assert result.unweighted == 1.0
        assert result.weighted == 1.0
        assert set(result.shared_tickers) == {"AAPL", "MSFT"}

    def test_no_overlap(self):
        fund_a = NormalisedFund("A", {"AAPL": 0.5, "MSFT": 0.5})
        fund_b = NormalisedFund("B", {"GOOGL": 0.5, "AMZN": 0.5})
        result = compute_overlap(fund_a, fund_b)
        assert result.unweighted == 0.0
        assert result.weighted == 0.0
        assert result.shared_tickers == []

    def test_partial_overlap(self):
        fund_a = NormalisedFund("A", {"AAPL": 0.5, "MSFT": 0.3, "GOOGL": 0.2})
        fund_b = NormalisedFund("B", {"AAPL": 0.4, "AMZN": 0.6})
        result = compute_overlap(fund_a, fund_b)
        # unweighted: 1 shared / min(3, 2) = 0.5
        assert result.unweighted == 0.5
        # weighted: min(0.5, 0.4) = 0.4
        assert result.weighted == 0.4
        assert result.shared_tickers == ["AAPL"]

    def test_different_weights_same_tickers(self):
        fund_a = NormalisedFund("A", {"AAPL": 0.7, "MSFT": 0.3})
        fund_b = NormalisedFund("B", {"AAPL": 0.3, "MSFT": 0.7})
        result = compute_overlap(fund_a, fund_b)
        assert result.unweighted == 1.0
        # weighted: min(0.7, 0.3) + min(0.3, 0.7) = 0.3 + 0.3 = 0.6
        assert result.weighted == 0.6

    def test_empty_fund(self):
        fund_a = NormalisedFund("A", {"AAPL": 1.0})
        fund_b = NormalisedFund("B", {})
        result = compute_overlap(fund_a, fund_b)
        assert result.unweighted == 0.0
        assert result.weighted == 0.0

    def test_symmetry(self):
        fund_a = NormalisedFund("A", {"AAPL": 0.6, "MSFT": 0.4})
        fund_b = NormalisedFund("B", {"AAPL": 0.3, "GOOGL": 0.7})
        result_ab = compute_overlap(fund_a, fund_b)
        result_ba = compute_overlap(fund_b, fund_a)
        assert result_ab.unweighted == result_ba.unweighted
        assert result_ab.weighted == result_ba.weighted


class TestComputeOverlapMatrix:
    def test_single_fund(self):
        fund = NormalisedFund("SPY", {"AAPL": 0.5, "MSFT": 0.5})
        symbols, unweighted, weighted = compute_overlap_matrix([fund])
        assert symbols == ["SPY"]
        assert unweighted == [[1.0]]
        assert weighted == [[1.0]]

    def test_two_funds(self):
        fund_a = NormalisedFund("A", {"AAPL": 0.5, "MSFT": 0.5})
        fund_b = NormalisedFund("B", {"AAPL": 0.3, "GOOGL": 0.7})
        symbols, unweighted, weighted = compute_overlap_matrix([fund_a, fund_b])
        assert symbols == ["A", "B"]
        assert unweighted[0][0] == 1.0
        assert unweighted[1][1] == 1.0
        # Symmetric
        assert unweighted[0][1] == unweighted[1][0]
        assert weighted[0][1] == weighted[1][0]

    def test_matrix_with_stub_data(self):
        """Test with actual stub fund data."""
        funds_input = [
            FundInput(symbol="SPY", holdings=[Holding(ticker=t, weight=w) for t, w in [("AAPL", 0.07), ("MSFT", 0.065)]]),
            FundInput(symbol="QQQ", holdings=[Holding(ticker=t, weight=w) for t, w in [("AAPL", 0.12), ("MSFT", 0.10)]]),
        ]
        normalised = normalise_holdings(funds_input)
        symbols, unweighted, weighted = compute_overlap_matrix(normalised)
        assert len(symbols) == 2
        # Both funds share AAPL and MSFT so unweighted overlap should be 1.0
        assert unweighted[0][1] == 1.0
