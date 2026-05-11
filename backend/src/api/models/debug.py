"""Debug information models for API responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AgentCallRecord(BaseModel):
    """Record of a single remote agent invocation."""

    agent_name: str
    url: str
    status_code: int | None = None
    latency_ms: float | None = None
    error: str | None = None
    request_payload: dict[str, Any] | None = None
    response_body: dict[str, Any] | str | None = None


class DebugInfo(BaseModel):
    """Execution debug information returned when ?debug=true."""

    execution_mode: str
    agents_called: list[AgentCallRecord] = []
    fallback_used: bool = False
    fallback_reason: str | None = None
    total_latency_ms: float | None = None
