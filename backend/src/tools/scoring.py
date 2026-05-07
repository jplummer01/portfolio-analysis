"""Candidate scoring tools."""

from datetime import datetime, timezone

from src.data.stub_holdings import STUB_DATA_TIMESTAMPS, STUB_PERFORMANCE
from src.tools.fees import get_expense_ratio
from src.tools.normalise import NormalisedFund
from src.tools.overlap import compute_overlap


class ScoreBreakdown:
    """Component breakdown of a candidate's score."""

    def __init__(
        self,
        overlap_reduction: float,
        performance: float,
        data_quality_penalty: float,
        cost_penalty: float,
    ) -> None:
        self.overlap_reduction = overlap_reduction
        self.performance = performance
        self.data_quality_penalty = data_quality_penalty
        self.cost_penalty = cost_penalty

    @property
    def total(self) -> float:
        return (
            self.overlap_reduction
            + self.performance
            + self.data_quality_penalty
            + self.cost_penalty
        )


class ScoredCandidate:
    """A scored candidate fund with explanation."""

    def __init__(
        self,
        symbol: str,
        breakdown: ScoreBreakdown,
        explanation: str,
    ) -> None:
        self.symbol = symbol
        self.breakdown = breakdown
        self.explanation = explanation

    @property
    def total_score(self) -> float:
        return max(0.0, self.breakdown.total)


def _compute_overlap_reduction_score(
    existing: NormalisedFund, candidate: NormalisedFund
) -> float:
    """Score 0–50: how much the candidate reduces overlap with existing fund.

    Lower overlap = higher score.
    """
    result = compute_overlap(existing, candidate)
    # Invert: 0 overlap -> 50, 1.0 overlap -> 0
    return round((1.0 - result.weighted) * 50.0, 2)


def _compute_performance_score(symbol: str) -> float:
    """Score 0–40 based on historical performance data.

    Uses a blend of 1y (40%), 3y (35%), 5y (25%) returns.
    """
    perf = STUB_PERFORMANCE.get(symbol)
    if not perf:
        return 0.0

    r1y = perf.get("1y")
    r3y = perf.get("3y")
    r5y = perf.get("5y")

    if r1y is None and r3y is None and r5y is None:
        return 0.0

    # Normalize returns to a 0-1 scale (assume -0.3 to +0.3 range)
    def normalize_return(r: float | None) -> float:
        if r is None:
            return 0.5  # neutral
        return min(1.0, max(0.0, (r + 0.3) / 0.6))

    blended = (
        normalize_return(r1y) * 0.40
        + normalize_return(r3y) * 0.35
        + normalize_return(r5y) * 0.25
    )

    return round(blended * 40.0, 2)


def _compute_cost_penalty(symbol: str) -> float:
    """Penalty 0 to -10 based on expense ratio.

    Scale: 0% → 0 penalty, 1%+ → -10 penalty (linear).
    """
    er = get_expense_ratio(symbol)
    if er is None:
        return -5.0  # Unknown cost = moderate penalty
    # Linear scale: 0 → 0, 0.01 (1%) → -10
    penalty = min(10.0, er / 0.01 * 10.0)
    return round(-penalty, 2)


def _compute_data_quality_penalty(symbol: str) -> float:
    """Penalty 0 to -20 based on data staleness.

    Data older than 90 days incurs a penalty.
    """
    timestamp_str = STUB_DATA_TIMESTAMPS.get(symbol)
    if not timestamp_str:
        return -20.0  # No data timestamp = maximum penalty

    try:
        data_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_days = (now - data_time).days

        if age_days <= 90:
            return 0.0
        elif age_days <= 180:
            # Linear penalty from 0 to -20 between 90 and 180 days
            return round(-20.0 * (age_days - 90) / 90.0, 2)
        else:
            return -20.0
    except (ValueError, TypeError):
        return -20.0


def score_candidates(
    existing: NormalisedFund,
    candidates: list[NormalisedFund],
) -> list[ScoredCandidate]:
    """Score candidate funds against an existing fund.

    Scoring (0–100):
    - OverlapReduction: 0–50
    - Performance: 0–40
    - DataQualityPenalty: 0 to -20
    - CostPenalty: 0 to -10 (currently unused, placeholder)

    Returns scored candidates sorted by total score descending.
    """
    scored: list[ScoredCandidate] = []

    for candidate in candidates:
        overlap_score = _compute_overlap_reduction_score(existing, candidate)
        performance_score = _compute_performance_score(candidate.symbol)
        data_penalty = _compute_data_quality_penalty(candidate.symbol)
        cost_penalty = _compute_cost_penalty(candidate.symbol)

        breakdown = ScoreBreakdown(
            overlap_reduction=overlap_score,
            performance=performance_score,
            data_quality_penalty=data_penalty,
            cost_penalty=cost_penalty,
        )

        # Generate explanation
        parts: list[str] = []
        parts.append(
            f"{candidate.symbol} scores {breakdown.total:.1f}/100 as a candidate."
        )
        parts.append(
            f"Overlap reduction: {overlap_score:.1f}/50 (lower overlap with {existing.symbol} is better)."
        )
        parts.append(f"Performance: {performance_score:.1f}/40.")

        if data_penalty < 0:
            parts.append(
                f"Data quality penalty: {data_penalty:.1f} (data may be stale)."
            )

        if cost_penalty < 0:
            er = get_expense_ratio(candidate.symbol)
            er_str = f"{er*100:.2f}%" if er is not None else "unknown"
            parts.append(
                f"Cost penalty: {cost_penalty:.1f} (expense ratio: {er_str})."
            )

        explanation = " ".join(parts)

        scored.append(
            ScoredCandidate(
                symbol=candidate.symbol,
                breakdown=breakdown,
                explanation=explanation,
            )
        )

    # Sort by total score descending
    scored.sort(key=lambda x: x.total_score, reverse=True)
    return scored
