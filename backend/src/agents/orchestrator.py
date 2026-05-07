"""Portfolio Orchestrator Agent — coordinates sub-agents via MAF v1.0 orchestrations."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from src.agents.executors import (
    AnalysisExecutor,
    CandidateExecutor,
    RecommendationExecutor,
)
from src.api.models.analysis import AnalysisResponse
from src.api.models.recommendation import RecommendResponse
from src.core.disclaimer import DISCLAIMER
from src.services.portfolio_analysis import normalise_funds

try:
    from agent_framework.orchestrations import ConcurrentBuilder

    MAF_ORCHESTRATIONS_AVAILABLE = True
except Exception:  # pragma: no cover - depends on optional MAF install
    ConcurrentBuilder = None
    MAF_ORCHESTRATIONS_AVAILABLE = False


class PortfolioOrchestratorAgent:
    """Orchestrate portfolio analysis and recommendation flows."""

    def __init__(self) -> None:
        self.analysis_executor = AnalysisExecutor()
        self.candidate_executor = CandidateExecutor()
        self.recommendation_executor = RecommendationExecutor()

    def _build_concurrent_workflow(self) -> Any | None:
        """Build a concurrent workflow when MAF orchestration APIs are present."""
        if not MAF_ORCHESTRATIONS_AVAILABLE or ConcurrentBuilder is None:
            return None

        try:
            return ConcurrentBuilder(
                participants=[self.analysis_executor, self.candidate_executor]
            ).build()
        except Exception:  # pragma: no cover - optional API compatibility
            return None

    async def run_analysis(
        self,
        existing_funds: list[str],
        allocations: list[float] | None = None,
    ) -> AnalysisResponse:
        """Run existing-portfolio analysis through the local executor."""
        result = await self.analysis_executor.run(
            {"existing_funds": existing_funds, "allocations": allocations}
        )

        return AnalysisResponse(
            overlap_matrix=result["overlap_matrix"],
            concentration=result["concentration"],
            top_overlaps=result["top_overlaps"],
            data_quality=result["data_quality"],
            asset_allocation=result["asset_allocation"],
            sector_exposure=result["sector_exposure"],
            fee_analysis=result["fee_analysis"],
            disclaimer=DISCLAIMER,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def run_recommendation(
        self,
        existing_funds: list[str],
        candidate_funds: list[str],
    ) -> RecommendResponse:
        """Run recommendation with concurrent fan-out and sequential scoring."""
        self._build_concurrent_workflow()

        _, candidate_result = await asyncio.gather(
            self.analysis_executor.run({"existing_funds": existing_funds}),
            self.candidate_executor.run({"candidate_funds": candidate_funds}),
        )

        rec_result = await self.recommendation_executor.run(
            {
                "existing_normalised": normalise_funds(existing_funds),
                "candidate_normalised": candidate_result["normalised_candidates"],
            }
        )

        return RecommendResponse(
            recommendations=rec_result["recommendations"],
            disclaimer=DISCLAIMER,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
