"""Remote agent proxies for Foundry hosted agent invocation."""

from __future__ import annotations

from typing import Any


class RemoteAgentProxy:
    """Base class for remote Foundry agent invocation via invocations protocol."""

    def __init__(self, agent_endpoint: str, agent_name: str) -> None:
        self.agent_endpoint = agent_endpoint
        self.agent_name = agent_name

    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Invoke the remote agent via the Foundry invocations protocol."""
        raise NotImplementedError(
            f"Remote invocation for {self.agent_name} requires Foundry Agent Service. "
            "Use EXECUTION_MODE=agent_local for local development."
        )


class RemoteAnalysisProxy(RemoteAgentProxy):
    """Proxy for a remotely hosted ExistingPortfolioAnalysisAgent."""

    def __init__(self, endpoint: str) -> None:
        super().__init__(endpoint, "ExistingPortfolioAnalysisAgent")


class RemoteCandidateProxy(RemoteAgentProxy):
    """Proxy for a remotely hosted CandidateUniverseAnalysisAgent."""

    def __init__(self, endpoint: str) -> None:
        super().__init__(endpoint, "CandidateUniverseAnalysisAgent")


class RemoteRecommendationProxy(RemoteAgentProxy):
    """Proxy for a remotely hosted RecommendationAgent."""

    def __init__(self, endpoint: str) -> None:
        super().__init__(endpoint, "RecommendationAgent")
