"""Foundry Hosted Agent entrypoint for portfolio analysis (Responses protocol).

This agent uses the Responses protocol to provide a conversational interface
for portfolio analysis, candidate evaluation, and recommendation scoring.
It can be published to Teams and M365 Copilot Studio.

The LLM handles natural language understanding and response formatting while
all financial calculations are performed by deterministic executor functions
exposed as @tool-decorated functions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from pydantic import Field
from typing_extensions import Annotated

from src.agents.executors import AnalysisExecutor, CandidateExecutor, RecommendationExecutor
from src.services.portfolio_analysis import normalise_funds

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
)
logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTIONS = """\
You are a portfolio analysis assistant. You help users understand fund overlap,
portfolio concentration, and potential switch candidates across mutual fund and
ETF portfolios.

MANDATORY RULES — you MUST follow these at all times:
1. Always include this disclaimer in every response that contains analysis results:
   "For informational purposes only; not financial advice."
2. NEVER provide financial advice or use directive language such as "buy", "sell",
   "switch to", or "you should invest in".
3. NEVER fabricate data. Only present results returned by the analysis tools.
4. Always include data quality information when presenting analysis results.
5. Always include explainable reasoning and score breakdowns for recommendations.
6. Present results in a clear, readable format using markdown tables where appropriate.

AVAILABLE TOOLS:
- analyse_portfolio: Computes overlap, concentration, asset allocation, sector exposure,
  and fees for a set of existing funds.
- evaluate_candidates: Evaluates candidate funds for data quality and normalisation.
- recommend_switches: Scores and ranks candidate funds as potential replacements for
  existing portfolio holdings.

When a user asks about their portfolio, use the appropriate tool(s). If they provide
fund symbols (like SPY, VTI, QQQ), pass them to the tools. If the request is unclear,
ask for clarification about which funds to analyse.

Available stub funds for demonstration: SPY, QQQ, VTI, ARKK, SCHD, VUG, VXUS
"""

_analysis_executor = AnalysisExecutor()
_candidate_executor = CandidateExecutor()
_recommendation_executor = RecommendationExecutor()


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from a sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


@tool(approval_mode="never_require")
def analyse_portfolio(
    existing_funds: Annotated[
        list[str],
        Field(description="List of fund symbols to analyse, e.g. ['SPY', 'QQQ', 'VTI']"),
    ],
    allocations: Annotated[
        dict[str, float] | None,
        Field(
            description="Optional allocation weights per fund, e.g. {'SPY': 0.5, 'QQQ': 0.3, 'VTI': 0.2}. "
            "If not provided, equal weighting is assumed.",
            default=None,
        ),
    ] = None,
) -> str:
    """Analyse overlap, concentration, asset allocation, sector exposure, and fees for existing funds.

    Returns a JSON object with overlap_matrix, concentration, top_overlaps,
    data_quality, asset_allocation, sector_exposure, and fee_analysis.
    """
    result = _run_async(
        _analysis_executor.run(
            {"existing_funds": existing_funds, "allocations": allocations}
        )
    )
    return json.dumps(result, indent=2, default=str)


@tool(approval_mode="never_require")
def evaluate_candidates(
    candidate_funds: Annotated[
        list[str],
        Field(description="List of candidate fund symbols to evaluate, e.g. ['ARKK', 'SCHD', 'VXUS']"),
    ],
) -> str:
    """Evaluate candidate funds for data quality and normalisation.

    Returns normalised candidate holdings and data quality assessments.
    """
    result = _run_async(
        _candidate_executor.run({"candidate_funds": candidate_funds})
    )
    return json.dumps(result, indent=2, default=str)


@tool(approval_mode="never_require")
def recommend_switches(
    existing_funds: Annotated[
        list[str],
        Field(description="List of existing fund symbols, e.g. ['SPY', 'QQQ']"),
    ],
    candidate_funds: Annotated[
        list[str],
        Field(description="List of candidate fund symbols to evaluate as replacements, e.g. ['ARKK', 'SCHD']"),
    ],
) -> str:
    """Score and rank candidate funds as potential replacements for existing portfolio holdings.

    Each candidate receives a score from 0 to 100 based on overlap reduction (0-50),
    performance (0-40), data quality penalty (0 to -20), and optional cost penalty (0 to -10).
    Returns ranked candidates with score breakdowns and explanations.
    """
    existing_normalised = normalise_funds(existing_funds)
    candidate_normalised = normalise_funds(candidate_funds)
    result = _run_async(
        _recommendation_executor.run(
            {
                "existing_normalised": existing_normalised,
                "candidate_normalised": candidate_normalised,
            }
        )
    )
    return json.dumps(result, indent=2, default=str)


def main() -> None:
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        raise EnvironmentError(
            "FOUNDRY_PROJECT_ENDPOINT environment variable is not set. "
            "Set it to your Foundry project endpoint, or use 'azd ai agent run' "
            "which sets it automatically."
        )

    model = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    if not model:
        raise EnvironmentError(
            "AZURE_AI_MODEL_DEPLOYMENT_NAME environment variable is not set. "
            "Set it to your model deployment name as declared in agent.yaml."
        )

    client = FoundryChatClient(
        project_endpoint=endpoint,
        model=model,
        credential=DefaultAzureCredential(),
    )

    agent = Agent(
        client=client,
        instructions=SYSTEM_INSTRUCTIONS,
        tools=[analyse_portfolio, evaluate_candidates, recommend_switches],
        default_options={"store": False},
    )

    server = ResponsesHostServer(agent)
    server.run()


if __name__ == "__main__":
    main()
