"""Distributed orchestrator — invokes Foundry hosted agents via invocations protocol."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from src.agents.remote import (
    RemoteAgentError,
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


class DistributedOrchestrationError(Exception):
    """Raised when the distributed orchestration fails.

    Carries any ``AgentCallRecord`` objects collected before the failure so
    that callers (route handlers) can include them in debug responses.
    """

    def __init__(self, message: str, records: list[AgentCallRecord]) -> None:
        super().__init__(message)
        self.records = records


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

        try:
            result, record = await self.analysis_proxy.invoke(
                {"existing_funds": existing_funds, "allocations": allocations}
            )
            records.append(record)
        except RemoteAgentError as exc:
            records.append(exc.record)
            raise DistributedOrchestrationError(str(exc), records) from exc

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

        # Fan-out: analysis + candidate in parallel
        analysis_task = asyncio.ensure_future(
            self.analysis_proxy.invoke({"existing_funds": existing_funds})
        )
        candidate_task = asyncio.ensure_future(
            self.candidate_proxy.invoke({"candidate_funds": candidate_funds})
        )

        try:
            results = await asyncio.gather(
                analysis_task, candidate_task, return_exceptions=True
            )
        except Exception as exc:
            # Collect any records from tasks that completed with RemoteAgentError
            for task in (analysis_task, candidate_task):
                if task.done() and task.exception():
                    task_exc = task.exception()
                    if isinstance(task_exc, RemoteAgentError):
                        records.append(task_exc.record)
            raise DistributedOrchestrationError(str(exc), records) from exc

        # Process gather results (may include exceptions)
        for r in results:
            if isinstance(r, RemoteAgentError):
                records.append(r.record)
            elif isinstance(r, Exception):
                pass  # non-agent error; no record to capture
            else:
                _, record = r
                records.append(record)

        # If any result was an exception, raise with collected records
        errors = [r for r in results if isinstance(r, Exception)]
        if errors:
            raise DistributedOrchestrationError(
                str(errors[0]), records
            ) from errors[0]

        analysis_result, analysis_record = results[0]
        candidate_result, candidate_record = results[1]

        logger.debug(
            "Remote pre-processing complete for %d existing funds and %d candidates",
            len(analysis_result.get("data_quality", [])),
            len(candidate_result.get("normalised_candidates", [])),
        )

        # Sequential: recommendation scoring
        try:
            result, rec_record = await self.recommendation_proxy.invoke(
                {"existing_funds": existing_funds, "candidate_funds": candidate_funds}
            )
            records.append(rec_record)
        except RemoteAgentError as exc:
            records.append(exc.record)
            raise DistributedOrchestrationError(str(exc), records) from exc

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
