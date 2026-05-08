"""Distributed orchestrator — invokes Foundry hosted agents via invocations protocol."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from src.agents.remote import (
    RemoteAnalysisProxy,
    RemoteCandidateProxy,
    RemoteRecommendationProxy,
)
from src.api.models.analysis import AnalysisResponse
from src.api.models.debug import AgentCallRecord, DebugInfo
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
        debug: bool = False,
    ) -> AnalysisResponse:
        """Run analysis by invoking the remote analysis agent."""
        start = time.monotonic()
        records: list[AgentCallRecord] = []

        result, record = await self.analysis_proxy.invoke(
            {"existing_funds": existing_funds, "allocations": allocations}
        )
        records.append(record)

        total_ms = round((time.monotonic() - start) * 1000, 1)

        response = AnalysisResponse(
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

        if debug:
            response.debug_info = DebugInfo(
                execution_mode="agent_distributed",
                agents_called=records,
                fallback_used=False,
                total_latency_ms=total_ms,
            )

        return response

    async def run_recommendation(
        self,
        existing_funds: list[str],
        candidate_funds: list[str],
        debug: bool = False,
    ) -> RecommendResponse:
        """Run recommendation with concurrent fan-out and sequential scoring."""
        start = time.monotonic()
        records: list[AgentCallRecord] = []

        analysis_result_record, candidate_result_record = await asyncio.gather(
            self.analysis_proxy.invoke({"existing_funds": existing_funds}),
            self.candidate_proxy.invoke({"candidate_funds": candidate_funds}),
        )
        analysis_result, analysis_record = analysis_result_record
        candidate_result, candidate_record = candidate_result_record
        records.extend([analysis_record, candidate_record])

        logger.debug(
            "Remote pre-processing complete for %d existing funds and %d candidates",
            len(analysis_result.get("data_quality", [])),
            len(candidate_result.get("normalised_candidates", [])),
        )

        result, rec_record = await self.recommendation_proxy.invoke(
            {"existing_funds": existing_funds, "candidate_funds": candidate_funds}
        )
        records.append(rec_record)

        total_ms = round((time.monotonic() - start) * 1000, 1)

        response = RecommendResponse(
            recommendations=result["recommendations"],
            disclaimer=DISCLAIMER,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        if debug:
            response.debug_info = DebugInfo(
                execution_mode="agent_distributed",
                agents_called=records,
                fallback_used=False,
                total_latency_ms=total_ms,
            )

        return response
