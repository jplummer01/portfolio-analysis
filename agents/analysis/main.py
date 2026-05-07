"""Foundry Hosted Agent entrypoint for existing portfolio analysis."""

from __future__ import annotations

import logging
import os

from fastapi.encoders import jsonable_encoder
from starlette.requests import Request
from starlette.responses import JSONResponse

from azure.ai.agentserver.invocations import InvocationAgentServerHost

from src.agents.executors import AnalysisExecutor

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
)
logger = logging.getLogger(__name__)

app = InvocationAgentServerHost(log_level=os.environ.get("LOG_LEVEL", "INFO"))
executor = AnalysisExecutor()


async def _load_payload(request: Request) -> dict:
    try:
        payload = await request.json()
    except Exception as exc:  # pragma: no cover - framework parsing
        raise ValueError("Request body must be a valid JSON object.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")

    return payload


@app.invoke_handler
async def handle_invoke(request: Request):
    """Handle POST /invocations requests for analysis payloads."""
    try:
        payload = await _load_payload(request)
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
        logger.exception("Analysis invocation failed")
        return JSONResponse(
            {"error": "internal_error", "message": str(exc)},
            status_code=500,
        )


if __name__ == "__main__":
    app.run()
