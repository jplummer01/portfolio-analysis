"""Remote agent proxies for Foundry hosted agent invocation."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RemoteAgentProxy:
    """Base class for remote Foundry agent invocation via invocations protocol."""

    def __init__(self, agent_endpoint: str, agent_name: str) -> None:
        self.agent_endpoint = agent_endpoint.rstrip("/")
        self.agent_name = agent_name

    def _build_url(self) -> str:
        """Build the invocations protocol URL."""
        return (
            f"{self.agent_endpoint}/agents/{self.agent_name}"
            "/endpoint/protocols/invocations"
        )

    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Invoke the remote agent via the Foundry invocations protocol."""
        url = self._build_url()
        headers = {"Content-Type": "application/json"}
        credential: Any | None = None

        try:
            from azure.identity.aio import DefaultAzureCredential

            credential = DefaultAzureCredential()
            token = await credential.get_token(
                "https://cognitiveservices.azure.com/.default"
            )
            headers["Authorization"] = f"Bearer {token.token}"
        except ImportError:
            logger.warning(
                "azure-identity not installed; sending request without auth. "
                "Install azure-identity for production use."
            )
        except Exception as exc:
            logger.warning("Failed to acquire Azure credential: %s", exc)
        finally:
            if credential is not None:
                await credential.close()

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()


class RemoteAnalysisProxy(RemoteAgentProxy):
    """Proxy for a remotely hosted ExistingPortfolioAnalysisAgent."""

    def __init__(self, endpoint: str) -> None:
        super().__init__(endpoint, "analysis-agent")


class RemoteCandidateProxy(RemoteAgentProxy):
    """Proxy for a remotely hosted CandidateUniverseAnalysisAgent."""

    def __init__(self, endpoint: str) -> None:
        super().__init__(endpoint, "candidate-agent")


class RemoteRecommendationProxy(RemoteAgentProxy):
    """Proxy for a remotely hosted RecommendationAgent."""

    def __init__(self, endpoint: str) -> None:
        super().__init__(endpoint, "recommendation-agent")
