"""Recommendation routes."""

import logging

from fastapi import APIRouter, HTTPException

from src.api.models.recommendation import RecommendRequest, RecommendResponse
from src.core.config import ExecutionMode, settings
from src.services.recommendation import recommend_candidates
import src.workflows.recommendation_workflow as recommendation_workflows

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post('/api/recommend', response_model=RecommendResponse)
async def recommend(request: RecommendRequest) -> RecommendResponse:
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

    if mode == ExecutionMode.WORKFLOW:
        try:
            return await recommendation_workflows.execute_recommendation_workflow(
                request
            )
        except Exception as exc:
            logger.warning(
                'Recommendation workflow failed; falling back to direct tools: %s',
                exc,
            )

    elif mode == ExecutionMode.AGENT_LOCAL:
        from src.agents.orchestrator import PortfolioOrchestratorAgent

        orchestrator = PortfolioOrchestratorAgent()
        return await orchestrator.run_recommendation(
            request.existing_funds, request.candidate_funds,
        )

    elif mode == ExecutionMode.AGENT_DISTRIBUTED:
        from src.agents.distributed import DistributedOrchestratorAgent

        orchestrator = DistributedOrchestratorAgent()
        return await orchestrator.run_recommendation(
            request.existing_funds, request.candidate_funds,
        )

    return await recommend_candidates(request.existing_funds, request.candidate_funds)
