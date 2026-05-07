"""Foundry hosted agent entrypoint — runs a single executor based on AGENT_ROLE."""

import asyncio
import json
import os
from typing import Any

AGENT_ROLE = os.environ.get("AGENT_ROLE", "analysis")


def get_executor():
    """Return the executor for the configured role."""
    if AGENT_ROLE == "analysis":
        from src.agents.executors import AnalysisExecutor

        return AnalysisExecutor()
    if AGENT_ROLE == "candidate":
        from src.agents.executors import CandidateExecutor

        return CandidateExecutor()
    if AGENT_ROLE == "recommendation":
        from src.agents.executors import RecommendationExecutor

        return RecommendationExecutor()
    raise ValueError(f"Unknown AGENT_ROLE: {AGENT_ROLE}")


async def handle_invocation(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle an invocations protocol request."""
    executor = get_executor()
    return await executor.run(payload)


if __name__ == "__main__":
    print(f"Foundry Hosted Agent starting with role: {AGENT_ROLE}")

    import sys

    if not sys.stdin.isatty():
        payload = json.load(sys.stdin)
        result = asyncio.run(handle_invocation(payload))
        print(json.dumps(result, default=str))
    else:
        print("Ready. Pass JSON payload via stdin for local testing.")
