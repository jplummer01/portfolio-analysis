"""Tests for sector exposure computation."""

from src.tools.normalise import NormalisedFund
from src.tools.sector_exposure import compute_sector_exposure


class TestComputeSectorExposure:
    def test_tech_heavy_fund(self):
        fund = NormalisedFund("QQQ", {"AAPL": 0.3, "MSFT": 0.3, "NVDA": 0.2, "AMZN": 0.2})
        result = compute_sector_exposure([fund])
        assert "Technology" in result.exposure
        assert result.exposure["Technology"] > 0.5

    def test_diversified_sectors(self):
        fund = NormalisedFund("SPY", {
            "AAPL": 0.25,  # Technology
            "JPM": 0.25,   # Financial Services
            "JNJ": 0.25,   # Healthcare
            "XOM": 0.25,   # Energy
        })
        result = compute_sector_exposure([fund])
        assert len(result.exposure) == 4
        for weight in result.exposure.values():
            assert abs(weight - 0.25) < 0.01

    def test_portfolio_weights_sum_correctly(self):
        fund = NormalisedFund("TEST", {"AAPL": 0.4, "MSFT": 0.3, "JPM": 0.3})
        result = compute_sector_exposure([fund])
        total = sum(result.exposure.values())
        assert abs(total - 1.0) < 0.01

    def test_per_fund_breakdown(self):
        fund_a = NormalisedFund("A", {"AAPL": 1.0})
        fund_b = NormalisedFund("B", {"JPM": 1.0})
        result = compute_sector_exposure([fund_a, fund_b])
        assert "A" in result.per_fund
        assert "B" in result.per_fund
        assert "Technology" in result.per_fund["A"]
        assert "Financial Services" in result.per_fund["B"]

    def test_unknown_tickers_labelled(self):
        fund = NormalisedFund("X", {"ZZZZ": 1.0})
        result = compute_sector_exposure([fund])
        assert "Unknown" in result.exposure

    def test_empty_funds(self):
        result = compute_sector_exposure([])
        assert result.exposure == {}

    def test_custom_allocations(self):
        fund_a = NormalisedFund("A", {"AAPL": 1.0})  # Tech
        fund_b = NormalisedFund("B", {"XOM": 1.0})   # Energy
        result = compute_sector_exposure([fund_a, fund_b], allocations=[0.7, 0.3])
        assert abs(result.exposure["Technology"] - 0.7) < 0.01
        assert abs(result.exposure["Energy"] - 0.3) < 0.01
