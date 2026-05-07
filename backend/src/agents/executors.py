"""Custom executors for local MAF v1.0 orchestration."""

from __future__ import annotations

import json
from typing import Any, Never

try:
    from agent_framework import AgentResponse, Message
    from agent_framework._workflows._agent_executor import (
        AgentExecutorRequest,
        AgentExecutorResponse,
    )
    from agent_framework._workflows._executor import Executor, handler
    from agent_framework._workflows._workflow_context import WorkflowContext

    AGENT_FRAMEWORK_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    AGENT_FRAMEWORK_AVAILABLE = False

    class Executor:
        """Fallback executor stub used when agent_framework is unavailable."""

        def __init__(self, id: str, **_: Any) -> None:
            self.id = id
            self.type = self.__class__.__name__
            self.type_ = self.type

    def handler(func: Any) -> Any:
        return func

    class Message:
        """Fallback message type for local imports without MAF installed."""

        def __init__(self, role: str, contents: list[str]) -> None:
            self.role = role
            self.contents = contents

    class AgentResponse:
        """Fallback response type for local imports without MAF installed."""

        def __init__(self, *, messages: list[Message] | None = None) -> None:
            self.messages = messages or []

    class AgentExecutorRequest:
        """Fallback request payload for local imports without MAF installed."""

        def __init__(self, messages: list[Message], should_respond: bool = True) -> None:
            self.messages = messages
            self.should_respond = should_respond

    class AgentExecutorResponse:
        """Fallback response payload for local imports without MAF installed."""

        def __init__(
            self,
            executor_id: str,
            agent_response: AgentResponse,
            full_conversation: list[Message],
        ) -> None:
            self.executor_id = executor_id
            self.agent_response = agent_response
            self.full_conversation = full_conversation

    class WorkflowContext:
        """Fallback workflow context."""

        async def send_message(self, message: Any) -> None:
            return None


def _serialise_for_message(value: Any) -> Any:
    """Convert executor results into JSON-friendly structures for MAF messages."""
    if isinstance(value, dict):
        return {key: _serialise_for_message(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialise_for_message(item) for item in value]
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "__dict__"):
        return {
            key: _serialise_for_message(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return value


class _BasePortfolioExecutor(Executor):
    """Shared behaviour for local direct calls and MAF executor compatibility."""

    name: str

    def __init__(self) -> None:
        super().__init__(id=self.name)

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run deterministic business logic directly."""
        raise NotImplementedError

    def _build_agent_response(
        self,
        request: AgentExecutorRequest,
        result: dict[str, Any],
    ) -> AgentExecutorResponse:
        message_payload = json.dumps(
            {
                "executor": self.name,
                "result": _serialise_for_message(result),
            },
            default=str,
        )
        response_message = Message("assistant", [message_payload])
        agent_response = AgentResponse(messages=[response_message])

        return AgentExecutorResponse(
            executor_id=self.id,
            agent_response=agent_response,
            full_conversation=[*request.messages, response_message],
        )

    @handler
    async def handle_request(
        self,
        request: AgentExecutorRequest,
        ctx: WorkflowContext[AgentExecutorResponse, Never],
    ) -> None:
        """Support ConcurrentBuilder participation when MAF is installed."""
        if not getattr(request, "should_respond", True):
            return

        payload = {}
        if getattr(request, "messages", None):
            last_message = request.messages[-1]
            contents = getattr(last_message, "contents", None) or []
            if contents and isinstance(contents[0], str):
                try:
                    payload = json.loads(contents[0])
                except json.JSONDecodeError:
                    payload = {}

        result = await self.run(payload)
        await ctx.send_message(self._build_agent_response(request, result))


class AnalysisExecutor(_BasePortfolioExecutor):
    """Wrap the portfolio analysis service for in-process orchestration."""

    name: str = "ExistingPortfolioAnalysisAgent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run analysis using the shared service layer."""
        from src.services.portfolio_analysis import (
            build_asset_allocation_summary,
            build_concentration_summary,
            build_fee_analysis_summary,
            build_overlap_summary,
            build_sector_exposure_summary,
            check_data_quality,
            normalise_funds,
        )

        symbols = input_data["existing_funds"]
        allocations = input_data.get("allocations")
        normalised = normalise_funds(symbols)
        overlap_matrix, top_overlaps = build_overlap_summary(normalised)

        return {
            "overlap_matrix": overlap_matrix,
            "concentration": build_concentration_summary(normalised, allocations),
            "top_overlaps": top_overlaps,
            "data_quality": check_data_quality(symbols),
            "asset_allocation": build_asset_allocation_summary(normalised, allocations),
            "sector_exposure": build_sector_exposure_summary(normalised, allocations),
            "fee_analysis": build_fee_analysis_summary(normalised, allocations),
        }


class CandidateExecutor(_BasePortfolioExecutor):
    """Wrap candidate universe analysis for in-process orchestration."""

    name: str = "CandidateUniverseAnalysisAgent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Evaluate candidate funds with the shared service layer."""
        from src.services.portfolio_analysis import check_data_quality, normalise_funds

        candidate_symbols = input_data["candidate_funds"]
        normalised = normalise_funds(candidate_symbols)

        return {
            "normalised_candidates": normalised,
            "candidate_data_quality": check_data_quality(candidate_symbols),
        }


class RecommendationExecutor(_BasePortfolioExecutor):
    """Wrap recommendation scoring for in-process orchestration."""

    name: str = "RecommendationAgent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Score candidates against existing funds."""
        from src.services.recommendation import build_recommendations

        existing_funds = input_data["existing_normalised"]
        candidate_funds = input_data["candidate_normalised"]

        return {
            "recommendations": build_recommendations(existing_funds, candidate_funds)
        }
