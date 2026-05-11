"""Recommendation routes."""

import logging
import time

from fastapi import APIRouter, HTTPException, Query

from src.api.models.debug import DebugInfo
from src.api.models.recommendation import RecommendRequest, RecommendResponse
from src.core.config import ExecutionMode, settings
from src.services.recommendation import recommend_candidates
import src.workflows.recommendation_workflow as recommendation_workflows

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post('/api/recommend', response_model=RecommendResponse)
async def recommend(
    request: RecommendRequest,
    debug: bool = Query(False, description="Return execution debug info"),
) -> RecommendResponse:
    """Generate candidate recommendations for each existing fund."""
    if not request.existing_funds:
        raise HTTPException(
            status_code=400, detail='At least one existing fund is required'
        )
    if not request.candidate_funds:
        raise HTTPException(
            status_code=400, detail='At least one candidate fund is required'
        )

    mode = settings.execution_mode
    start = time.monotonic()
    fallback_used = False
    fallback_reason: str | None = None
    partial_records: list = []

    if mode == ExecutionMode.WORKFLOW:
        try:
            result = await recommendation_workflows.execute_recommendation_workflow(
                request
            )
            if debug:
                result.debug_info = DebugInfo(
                    execution_mode=mode.value,
                    fallback_used=False,
                    total_latency_ms=round((time.monotonic() - start) * 1000, 1),
                )
            return result
        except Exception as exc:
            logger.warning(
                'Recommendation workflow failed; falling back to direct tools: %s',
                exc,
            )
            fallback_used = True
            fallback_reason = f"workflow error: {exc}"

    elif mode == ExecutionMode.AGENT_LOCAL:
        try:
            from src.agents.orchestrator import PortfolioOrchestratorAgent

            orchestrator = PortfolioOrchestratorAgent()
            result = await orchestrator.run_recommendation(
                request.existing_funds, request.candidate_funds,
            )
            if debug:
                result.debug_info = DebugInfo(
                    execution_mode=mode.value,
                    fallback_used=False,
                    total_latency_ms=round((time.monotonic() - start) * 1000, 1),
                )
            return result
        except Exception as exc:
            logger.warning(
                'Local agent recommendation failed; falling back to direct tools: %s',
                exc,
            )
            fallback_used = True
            fallback_reason = f"agent_local error: {exc}"

    elif mode == ExecutionMode.AGENT_DISTRIBUTED:
        try:
            from src.agents.distributed import DistributedOrchestratorAgent

            orchestrator = DistributedOrchestratorAgent()
            return await orchestrator.run_recommendation(
                request.existing_funds, request.candidate_funds, debug=debug,
            )
        except Exception as exc:
            logger.warning(
                'Distributed agent recommendation failed; falling back to direct tools: %s',
                exc,
            )
            fallback_used = True
            fallback_reason = f"agent_distributed error: {exc}"
            partial_records = getattr(exc, "records", [])

    result = await recommend_candidates(request.existing_funds, request.candidate_funds)
    if debug:
        result.debug_info = DebugInfo(
            execution_mode=mode.value,
            agents_called=partial_records if fallback_used else [],
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            total_latency_ms=round((time.monotonic() - start) * 1000, 1),
        )
    return result
