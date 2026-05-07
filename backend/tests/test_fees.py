"""Tests for fee analysis computation."""

from src.tools.fees import compute_fee_analysis, get_expense_ratio
from src.tools.normalise import NormalisedFund


class TestComputeFeeAnalysis:
    def test_single_known_fund(self):
        fund = NormalisedFund("SPY", {"AAPL": 0.5, "MSFT": 0.5})
        result = compute_fee_analysis([fund])
        assert result.per_fund["SPY"] == 0.0003
        assert result.portfolio_weighted_er == 0.0003
        assert result.estimated_annual_cost_per_10k == 3.0

    def test_two_funds_equal_alloc(self):
        fund_a = NormalisedFund("SPY", {"AAPL": 1.0})  # 0.03%
        fund_b = NormalisedFund("ARKK", {"TSLA": 1.0})  # 0.75%
        result = compute_fee_analysis([fund_a, fund_b])
        # Weighted: (0.0003 + 0.0075) / 2 = 0.0039
        assert abs(result.portfolio_weighted_er - 0.0039) < 0.0001
        assert result.estimated_annual_cost_per_10k == 39.0

    def test_custom_allocations(self):
        fund_a = NormalisedFund("SPY", {"AAPL": 1.0})  # 0.03%
        fund_b = NormalisedFund("ARKK", {"TSLA": 1.0})  # 0.75%
        result = compute_fee_analysis([fund_a, fund_b], allocations=[0.9, 0.1])
        # Weighted: 0.9 * 0.0003 + 0.1 * 0.0075 = 0.00027 + 0.00075 = 0.00102
        assert abs(result.portfolio_weighted_er - 0.00102) < 0.0001

    def test_unknown_fund_none_er(self):
        fund = NormalisedFund("UNKNOWN_XYZ", {"AAPL": 1.0})
        result = compute_fee_analysis([fund])
        assert result.per_fund["UNKNOWN_XYZ"] is None

    def test_empty_funds(self):
        result = compute_fee_analysis([])
        assert result.portfolio_weighted_er == 0.0
        assert result.estimated_annual_cost_per_10k == 0.0

    def test_arkk_most_expensive(self):
        """ARKK (0.75%) should be the most expensive of our stub funds."""
        funds = [
            NormalisedFund("SPY", {"AAPL": 1.0}),
            NormalisedFund("QQQ", {"MSFT": 1.0}),
            NormalisedFund("ARKK", {"TSLA": 1.0}),
        ]
        result = compute_fee_analysis(funds)
        assert result.per_fund["ARKK"] > result.per_fund["SPY"]
        assert result.per_fund["ARKK"] > result.per_fund["QQQ"]


class TestGetExpenseRatio:
    def test_known_fund(self):
        assert get_expense_ratio("SPY") == 0.0003

    def test_unknown_fund(self):
        assert get_expense_ratio("UNKNOWN_XYZ") is None
