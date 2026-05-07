"""Tests for asset allocation computation."""

from src.tools.asset_allocation import compute_asset_allocation
from src.tools.normalise import NormalisedFund


class TestComputeAssetAllocation:
    def test_single_equity_fund(self):
        fund = NormalisedFund("SPY", {"AAPL": 0.5, "MSFT": 0.5})
        result = compute_asset_allocation([fund])
        assert "Equity" in result.allocation
        assert result.allocation["Equity"] > 0.9

    def test_portfolio_level_weights_sum_to_one(self):
        fund = NormalisedFund("SPY", {"AAPL": 0.5, "MSFT": 0.5})
        result = compute_asset_allocation([fund])
        total = sum(result.allocation.values())
        assert abs(total - 1.0) < 0.01

    def test_per_fund_breakdown(self):
        fund_a = NormalisedFund("SPY", {"AAPL": 0.5, "MSFT": 0.5})
        fund_b = NormalisedFund("QQQ", {"GOOGL": 0.5, "AMZN": 0.5})
        result = compute_asset_allocation([fund_a, fund_b])
        assert "SPY" in result.per_fund
        assert "QQQ" in result.per_fund

    def test_custom_allocations(self):
        fund_a = NormalisedFund("SPY", {"AAPL": 1.0})
        fund_b = NormalisedFund("QQQ", {"MSFT": 1.0})
        result = compute_asset_allocation([fund_a, fund_b], allocations=[0.8, 0.2])
        assert "Equity" in result.allocation

    def test_empty_funds(self):
        result = compute_asset_allocation([])
        assert result.allocation == {}
        assert result.per_fund == {}

    def test_unknown_holdings_classified(self):
        fund = NormalisedFund("MYSTERY", {"ZZZZ": 0.5, "YYYY": 0.5})
        result = compute_asset_allocation([fund])
        # Unknown holdings should still be classified (as Other or via fund metadata)
        assert len(result.allocation) > 0
