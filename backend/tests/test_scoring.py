"""Tests for scoring tools."""

import pytest

from src.tools.normalise import NormalisedFund
from src.tools.scoring import (
    ScoreBreakdown,
    _compute_data_quality_penalty,
    _compute_overlap_reduction_score,
    _compute_performance_score,
    score_candidates,
)


class TestOverlapReductionScore:
    def test_no_overlap_max_score(self):
        existing = NormalisedFund("A", {"AAPL": 0.5, "MSFT": 0.5})
        candidate = NormalisedFund("B", {"GOOGL": 0.5, "AMZN": 0.5})
        score = _compute_overlap_reduction_score(existing, candidate)
        assert score == 50.0

    def test_full_overlap_zero_score(self):
        existing = NormalisedFund("A", {"AAPL": 0.5, "MSFT": 0.5})
        candidate = NormalisedFund("B", {"AAPL": 0.5, "MSFT": 0.5})
        score = _compute_overlap_reduction_score(existing, candidate)
        # weighted overlap = 1.0, so score = (1 - 1.0) * 50 = 0
        assert score == 0.0

    def test_partial_overlap(self):
        existing = NormalisedFund("A", {"AAPL": 0.5, "MSFT": 0.5})
        candidate = NormalisedFund("B", {"AAPL": 0.3, "GOOGL": 0.7})
        score = _compute_overlap_reduction_score(existing, candidate)
        # weighted overlap = min(0.5, 0.3) = 0.3
        # score = (1 - 0.3) * 50 = 35.0
        assert score == 35.0


class TestPerformanceScore:
    def test_known_fund(self):
        score = _compute_performance_score("SPY")
        assert 0 <= score <= 40

    def test_unknown_fund(self):
        score = _compute_performance_score("UNKNOWN_XYZ")
        assert score == 0.0

    def test_good_performance(self):
        # SPY has positive returns
        spy_score = _compute_performance_score("SPY")
        # ARKK has negative returns
        arkk_score = _compute_performance_score("ARKK")
        assert spy_score > arkk_score


class TestDataQualityPenalty:
    def test_fresh_data_no_penalty(self):
        penalty = _compute_data_quality_penalty("SPY")
        assert penalty == 0.0

    def test_stale_data_penalty(self):
        # VXUS has intentionally stale data
        penalty = _compute_data_quality_penalty("VXUS")
        assert penalty < 0.0

    def test_unknown_fund_max_penalty(self):
        penalty = _compute_data_quality_penalty("UNKNOWN_XYZ")
        assert penalty == -20.0


class TestScoreCandidates:
    def test_candidates_ranked(self):
        existing = NormalisedFund("SPY", {"AAPL": 0.3, "MSFT": 0.3, "GOOGL": 0.4})
        candidates = [
            NormalisedFund("C1", {"AAPL": 0.5, "MSFT": 0.5}),  # high overlap
            NormalisedFund("C2", {"AMZN": 0.5, "TSLA": 0.5}),  # no overlap
        ]
        scored = score_candidates(existing, candidates)
        assert len(scored) == 2
        # C2 should rank higher (less overlap)
        assert scored[0].symbol == "C2"
        assert scored[1].symbol == "C1"

    def test_score_breakdown_present(self):
        existing = NormalisedFund("A", {"AAPL": 1.0})
        candidate = NormalisedFund("B", {"MSFT": 1.0})
        scored = score_candidates(existing, [candidate])
        assert len(scored) == 1
        assert scored[0].breakdown.overlap_reduction >= 0
        assert scored[0].breakdown.performance >= 0
        assert scored[0].breakdown.data_quality_penalty <= 0
        assert scored[0].breakdown.cost_penalty <= 0

    def test_explanation_present(self):
        existing = NormalisedFund("SPY", {"AAPL": 1.0})
        candidate = NormalisedFund("QQQ", {"MSFT": 1.0})
        scored = score_candidates(existing, [candidate])
        assert scored[0].explanation != ""
        assert "QQQ" in scored[0].explanation

    def test_total_score_non_negative(self):
        existing = NormalisedFund("A", {"AAPL": 1.0})
        candidates = [NormalisedFund("B", {"AAPL": 1.0})]
        scored = score_candidates(existing, candidates)
        assert scored[0].total_score >= 0.0

    def test_with_real_stub_funds(self):
        """Test scoring with stub fund data — ARKK should score well against SPY."""
        from src.api.models.ingest import FundInput, Holding
        from src.data.stub_holdings import STUB_HOLDINGS
        from src.tools.normalise import normalise_holdings

        spy_input = FundInput(
            symbol="SPY",
            holdings=[
                Holding(ticker=t, weight=w)
                for t, w in STUB_HOLDINGS["SPY"].items()
            ],
        )
        arkk_input = FundInput(
            symbol="ARKK",
            holdings=[
                Holding(ticker=t, weight=w)
                for t, w in STUB_HOLDINGS["ARKK"].items()
            ],
        )
        schd_input = FundInput(
            symbol="SCHD",
            holdings=[
                Holding(ticker=t, weight=w)
                for t, w in STUB_HOLDINGS["SCHD"].items()
            ],
        )

        normalised = normalise_holdings([spy_input, arkk_input, schd_input])
        spy = normalised[0]
        candidates = normalised[1:]

        scored = score_candidates(spy, candidates)
        assert len(scored) == 2
        # Both should have valid scores
        for s in scored:
            assert 0 <= s.total_score <= 100
