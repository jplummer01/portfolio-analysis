"""Foundry Hosted Agent entrypoint for deterministic recommendation scoring."""

from __future__ import annotations

import logging
import os

from fastapi.encoders import jsonable_encoder
from starlette.requests import Request
from starlette.responses import JSONResponse

from azure.ai.agentserver.invocations import InvocationAgentServerHost

from src.agents.executors import RecommendationExecutor
from src.services.portfolio_analysis import normalise_funds

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
)
logger = logging.getLogger(__name__)

app = InvocationAgentServerHost(log_level=os.environ.get("LOG_LEVEL", "INFO"))
executor = RecommendationExecutor()


async def _load_payload(request: Request) -> dict:
    try:
        payload = await request.json()
    except Exception as exc:  # pragma: no cover - framework parsing
        raise ValueError("Request body must be a valid JSON object.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")

    return payload


def _prepare_payload(payload: dict) -> dict:
    if "existing_normalised" in payload and "candidate_normalised" in payload:
        return payload

    if "existing_funds" in payload and "candidate_funds" in payload:
        return {
            "existing_normalised": normalise_funds(payload["existing_funds"]),
            "candidate_normalised": normalise_funds(payload["candidate_funds"]),
        }

    raise ValueError(
        "Recommendation requests must include either existing_normalised and "
        "candidate_normalised, or existing_funds and candidate_funds."
    )


@app.invoke_handler
async def handle_invoke(request: Request):
    """Handle POST /invocations requests for recommendation payloads."""
    try:
        payload = _prepare_payload(await _load_payload(request))
        result = await executor.run(payload)
        return JSONResponse(jsonable_encoder(result))
    except ValueError as exc:
        return JSONResponse(
            {"error": "invalid_request", "message": str(exc)},
            status_code=400,
        )
    except KeyError as exc:
        return JSONResponse(
            {
                "error": "invalid_request",
                "message": f"Missing required field: {exc.args[0]}",
            },
            status_code=400,
        )
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        logger.exception("Recommendation invocation failed")
        return JSONResponse(
            {"error": "internal_error", "message": str(exc)},
            status_code=500,
        )


if __name__ == "__main__":
    app.run()
