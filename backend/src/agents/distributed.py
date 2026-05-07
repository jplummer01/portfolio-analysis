"""Distributed orchestrator — invokes Foundry hosted agents via invocations protocol."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from src.agents.remote import (
    RemoteAnalysisProxy,
    RemoteCandidateProxy,
    RemoteRecommendationProxy,
)
from src.api.models.analysis import AnalysisResponse
from src.api.models.recommendation import RecommendResponse
from src.core.config import settings
from src.core.disclaimer import DISCLAIMER

logger = logging.getLogger(__name__)


class DistributedOrchestratorAgent:
    """Orchestrate portfolio analysis via remote Foundry hosted agents."""

    def __init__(self) -> None:
        endpoint = settings.foundry_project_endpoint
        if not endpoint:
            raise RuntimeError(
                "FOUNDRY_PROJECT_ENDPOINT must be set for agent_distributed mode"
            )
        self.analysis_proxy = RemoteAnalysisProxy(endpoint)
        self.candidate_proxy = RemoteCandidateProxy(endpoint)
        self.recommendation_proxy = RemoteRecommendationProxy(endpoint)

    async def run_analysis(
        self,
        existing_funds: list[str],
        allocations: list[float] | None = None,
    ) -> AnalysisResponse:
        """Run analysis by invoking the remote analysis agent."""
        result = await self.analysis_proxy.invoke(
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
        analysis_result, candidate_result = await asyncio.gather(
            self.analysis_proxy.invoke({"existing_funds": existing_funds}),
            self.candidate_proxy.invoke({"candidate_funds": candidate_funds}),
        )

        logger.debug(
            "Remote pre-processing complete for %d existing funds and %d candidates",
            len(analysis_result.get("data_quality", [])),
            len(candidate_result.get("normalised_candidates", [])),
        )

        result = await self.recommendation_proxy.invoke(
            {"existing_funds": existing_funds, "candidate_funds": candidate_funds}
        )
        return RecommendResponse(
            recommendations=result["recommendations"],
            disclaimer=DISCLAIMER,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
