"""Remote agent proxies for Foundry hosted agent invocation."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from src.api.models.debug import AgentCallRecord

logger = logging.getLogger(__name__)

# Foundry platform API version and preview feature flag
FOUNDRY_API_VERSION = os.environ.get("FOUNDRY_API_VERSION", "v1")
FOUNDRY_FEATURES = os.environ.get(
    "FOUNDRY_FEATURES", "HostedAgents=V1Preview"
)
# Token scope for Foundry hosted agent endpoints
FOUNDRY_TOKEN_SCOPE = os.environ.get(
    "FOUNDRY_TOKEN_SCOPE", "https://ai.azure.com/.default"
)


class RemoteAgentError(Exception):
    """Raised when a remote Foundry agent invocation fails.

    Carries the ``AgentCallRecord`` so callers can include it in debug info
    even when the call did not succeed.
    """

    def __init__(self, message: str, record: AgentCallRecord) -> None:
        super().__init__(message)
        self.record = record


class RemoteAgentProxy:
    """Base class for remote Foundry agent invocation via invocations protocol."""

    def __init__(self, agent_endpoint: str, agent_name: str) -> None:
        self.agent_endpoint = agent_endpoint.rstrip("/")
        self.agent_name = agent_name

    def _build_url(self) -> str:
        """Build the invocations protocol URL with required api-version."""
        return (
            f"{self.agent_endpoint}/agents/{self.agent_name}"
            f"/endpoint/protocols/invocations?api-version={FOUNDRY_API_VERSION}"
        )

    async def invoke(
        self, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], AgentCallRecord]:
        """Invoke the remote agent and return (result, call_record)."""
        url = self._build_url()
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Foundry-Features": FOUNDRY_FEATURES,
        }
        credential: Any | None = None

        try:
            from azure.identity.aio import DefaultAzureCredential

            credential = DefaultAzureCredential()
            token = await credential.get_token(FOUNDRY_TOKEN_SCOPE)
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

        start = time.monotonic()
        status_code: int | None = None
        error_msg: str | None = None
        response_body: dict[str, Any] | str | None = None
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                status_code = response.status_code
                try:
                    response_body = response.json()
                except Exception:
                    response_body = response.text
                response.raise_for_status()
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            error_msg = str(exc)
            logger.debug(
                "Agent %s call to %s failed (%s) in %.0fms: %s",
                self.agent_name, url, status_code, elapsed, error_msg,
            )
            record = AgentCallRecord(
                agent_name=self.agent_name,
                url=url,
                status_code=status_code,
                latency_ms=round(elapsed, 1),
                error=error_msg,
                request_payload=payload,
                response_body=response_body,
            )
            raise RemoteAgentError(str(exc), record) from exc
        else:
            elapsed = (time.monotonic() - start) * 1000
            logger.debug(
                "Agent %s call to %s returned %s in %.0fms",
                self.agent_name, url, status_code, elapsed,
            )
            record = AgentCallRecord(
                agent_name=self.agent_name,
                url=url,
                status_code=status_code,
                latency_ms=round(elapsed, 1),
                request_payload=payload,
                response_body=response_body,
            )
            return response_body, record  # type: ignore[return-value]


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


class RemotePortfolioAssistantProxy:
    """Proxy for a remotely hosted portfolio-assistant using the Responses protocol.

    Unlike the Invocations-based proxies, this uses the OpenAI-compatible
    Responses endpoint which accepts natural language input and returns
    conversational output.
    """

    def __init__(self, agent_endpoint: str, agent_name: str = "portfolio-assistant") -> None:
        self.agent_endpoint = agent_endpoint.rstrip("/")
        self.agent_name = agent_name

    def _build_url(self) -> str:
        """Build the Responses protocol URL with required api-version."""
        return (
            f"{self.agent_endpoint}/agents/{self.agent_name}"
            f"/endpoint/protocols/openai/v1/responses?api-version={FOUNDRY_API_VERSION}"
        )

    async def invoke(
        self, input_text: str, *, stream: bool = False
    ) -> tuple[dict[str, Any], AgentCallRecord]:
        """Invoke the portfolio-assistant via the Responses protocol."""
        url = self._build_url()
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        credential: Any | None = None

        try:
            from azure.identity.aio import DefaultAzureCredential

            credential = DefaultAzureCredential()
            token = await credential.get_token(FOUNDRY_TOKEN_SCOPE)
            headers["Authorization"] = f"Bearer {token.token}"
        except ImportError:
            logger.warning(
                "azure-identity not installed; sending request without auth."
            )
        except Exception as exc:
            logger.warning("Failed to acquire Azure credential: %s", exc)
        finally:
            if credential is not None:
                await credential.close()

        payload = {"input": input_text, "stream": stream}
        start = time.monotonic()
        status_code: int | None = None
        error_msg: str | None = None
        response_body: dict[str, Any] | str | None = None
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                status_code = response.status_code
                try:
                    response_body = response.json()
                except Exception:
                    response_body = response.text
                response.raise_for_status()
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            error_msg = str(exc)
            record = AgentCallRecord(
                agent_name=self.agent_name,
                url=url,
                status_code=status_code,
                latency_ms=round(elapsed, 1),
                error=error_msg,
                request_payload=payload,
                response_body=response_body,
            )
            raise RemoteAgentError(str(exc), record) from exc
        else:
            elapsed = (time.monotonic() - start) * 1000
            record = AgentCallRecord(
                agent_name=self.agent_name,
                url=url,
                status_code=status_code,
                latency_ms=round(elapsed, 1),
                request_payload=payload,
                response_body=response_body,
            )
            return response_body, record  # type: ignore[return-value]
