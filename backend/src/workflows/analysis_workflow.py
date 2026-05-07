"""MAF orchestration for portfolio analysis."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar

from src.api.models.analysis import (
    AnalyseRequest,
    AnalysisResponse,
    ConcentrationResult as ConcentrationResponseModel,
    DataQualityEntry,
    OverlapMatrix,
    OverlapPair,
)
from src.services.portfolio_analysis import (
    analyse_portfolio,
    build_concentration_summary,
    build_overlap_summary,
    check_data_quality as _check_data_quality,
    get_fund_inputs as _get_fund_inputs,
    normalise_funds,
)
from src.tools.normalise import NormalisedFund

DecoratorFunction = TypeVar('DecoratorFunction', bound=Callable[..., Awaitable[Any]])

try:
    from agent_framework import step, workflow

    AGENT_FRAMEWORK_AVAILABLE = True
except Exception:  # pragma: no cover - exercised via fallback path
    AGENT_FRAMEWORK_AVAILABLE = False

    def step(func: DecoratorFunction) -> DecoratorFunction:
        return func

    def workflow(func: DecoratorFunction) -> DecoratorFunction:
        return func


@step
async def parse_and_normalise_funds(symbols: list[str]) -> list[NormalisedFund]:
    """Parse stub holdings and normalise them for downstream analysis."""
    return normalise_funds(symbols)


@step
async def compute_overlap_summary(
    funds: list[NormalisedFund],
) -> tuple[OverlapMatrix, list[OverlapPair]]:
    """Compute overlap matrix and ranked overlap pairs."""
    return build_overlap_summary(funds)


@step
async def compute_concentration_summary(
    funds: list[NormalisedFund],
    allocations: list[float] | None,
) -> ConcentrationResponseModel:
    """Compute portfolio concentration metrics."""
    return build_concentration_summary(funds, allocations)


@step
async def compute_data_quality_summary(symbols: list[str]) -> list[DataQualityEntry]:
    """Summarise holdings freshness for all requested funds."""
    return _check_data_quality(symbols)


async def run_analysis_pipeline(request: AnalyseRequest) -> AnalysisResponse:
    """Run the analysis pipeline as a plain async function."""
    return await analyse_portfolio(request.existing_funds, request.allocations)


@workflow
async def analysis_workflow(request: AnalyseRequest) -> AnalysisResponse:
    """MAF workflow wrapper for the analysis pipeline."""
    return await run_analysis_pipeline(request)


async def execute_analysis_workflow(request: AnalyseRequest) -> AnalysisResponse:
    """Execute the analysis workflow via MAF when available."""
    if hasattr(analysis_workflow, 'run'):
        result = await analysis_workflow.run(request)
        outputs = result.get_outputs()
        if outputs:
            return outputs[-1]
        raise RuntimeError('Analysis workflow completed without an output')

    return await analysis_workflow(request)
