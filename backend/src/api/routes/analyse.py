"""Analysis routes."""

import logging

from fastapi import APIRouter, HTTPException

from src.api.models.analysis import AnalyseRequest, AnalysisResponse
from src.core.config import ExecutionMode, settings
from src.services.portfolio_analysis import analyse_portfolio
import src.workflows.analysis_workflow as analysis_workflows

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post('/api/analyse', response_model=AnalysisResponse)
async def analyse(request: AnalyseRequest) -> AnalysisResponse:
    """Analyse existing portfolio for overlap and concentration."""
    if not request.existing_funds:
        raise HTTPException(status_code=400, detail='At least one fund is required')

    mode = settings.execution_mode

    if mode == ExecutionMode.WORKFLOW:
        try:
            return await analysis_workflows.execute_analysis_workflow(request)
        except Exception as exc:
            logger.warning(
                'Analysis workflow failed; falling back to direct tools: %s',
                exc,
            )

    elif mode == ExecutionMode.AGENT_LOCAL:
        from src.agents.orchestrator import PortfolioOrchestratorAgent

        orchestrator = PortfolioOrchestratorAgent()
        return await orchestrator.run_analysis(
            request.existing_funds, request.allocations,
        )

    elif mode == ExecutionMode.AGENT_DISTRIBUTED:
        from src.agents.distributed import DistributedOrchestratorAgent

        orchestrator = DistributedOrchestratorAgent()
        return await orchestrator.run_analysis(
            request.existing_funds, request.allocations,
        )

    return await analyse_portfolio(request.existing_funds, request.allocations)
