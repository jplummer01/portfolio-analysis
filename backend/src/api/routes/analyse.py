"""Analysis routes."""

import logging
import time

from fastapi import APIRouter, HTTPException, Query

from src.api.models.analysis import AnalyseRequest, AnalysisResponse
from src.api.models.debug import DebugInfo
from src.core.config import ExecutionMode, settings
from src.services.portfolio_analysis import analyse_portfolio
import src.workflows.analysis_workflow as analysis_workflows

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post('/api/analyse', response_model=AnalysisResponse)
async def analyse(
    request: AnalyseRequest,
    debug: bool = Query(False, description="Return execution debug info"),
) -> AnalysisResponse:
    """Analyse existing portfolio for overlap and concentration."""
    if not request.existing_funds:
        raise HTTPException(status_code=400, detail='At least one fund is required')

    mode = settings.execution_mode
    start = time.monotonic()
    fallback_used = False
    fallback_reason: str | None = None
    partial_records: list = []

    if mode == ExecutionMode.WORKFLOW:
        try:
            result = await analysis_workflows.execute_analysis_workflow(request)
            if debug:
                result.debug_info = DebugInfo(
                    execution_mode=mode.value,
                    fallback_used=False,
                    total_latency_ms=round((time.monotonic() - start) * 1000, 1),
                )
            return result
        except Exception as exc:
            logger.warning(
                'Analysis workflow failed; falling back to direct tools: %s',
                exc,
            )
            fallback_used = True
            fallback_reason = f"workflow error: {exc}"

    elif mode == ExecutionMode.AGENT_LOCAL:
        try:
            from src.agents.orchestrator import PortfolioOrchestratorAgent

            orchestrator = PortfolioOrchestratorAgent()
            result = await orchestrator.run_analysis(
                request.existing_funds, request.allocations,
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
                'Local agent analysis failed; falling back to direct tools: %s',
                exc,
            )
            fallback_used = True
            fallback_reason = f"agent_local error: {exc}"

    elif mode == ExecutionMode.AGENT_DISTRIBUTED:
        try:
            from src.agents.distributed import DistributedOrchestratorAgent

            orchestrator = DistributedOrchestratorAgent()
            return await orchestrator.run_analysis(
                request.existing_funds, request.allocations, debug=debug,
            )
        except Exception as exc:
            logger.warning(
                'Distributed agent analysis failed; falling back to direct tools: %s',
                exc,
            )
            fallback_used = True
            fallback_reason = f"agent_distributed error: {exc}"
            partial_records = getattr(exc, "records", [])

    result = await analyse_portfolio(request.existing_funds, request.allocations)
    if debug:
        result.debug_info = DebugInfo(
            execution_mode=mode.value,
            agents_called=partial_records if fallback_used else [],
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            total_latency_ms=round((time.monotonic() - start) * 1000, 1),
        )
    return result
