# Recommendation Agent

> For informational purposes only; not financial advice.

## Overview

The **recommendation-agent** is a Foundry hosted agent that performs deterministic candidate ranking. Given normalised existing funds and normalised candidate funds, it scores each candidate on overlap reduction, performance, data quality, and cost, producing a ranked list of switch candidates per existing fund. All computations are **deterministic** — no LLM reasoning is involved.

The agent runs as a standalone container behind the [Invocations protocol](https://github.com/microsoft/AgentSchema) and is deployed to Microsoft Foundry Agent Service via `azd up`.

## Configuration — `agent.yaml`

```yaml
kind: hosted
name: recommendation-agent
protocols:
  - protocol: invocations
    version: "1.0.0"
resources:
  cpu: "0.5"
  memory: 1Gi
environment_variables:
  - name: SERVICE_ROLE
    value: recommendation
tools: []
```

| Field | Value | Description |
|-------|-------|-------------|
| `kind` | `hosted` | Runs as a Foundry hosted agent |
| `name` | `recommendation-agent` | Deployment name used in `azure.yaml` |
| `protocol` | `invocations` v1.0.0 | Accepts `POST /invocations` payloads |
| `resources` | 0.5 CPU / 1 GiB RAM | Container resource limits |
| `SERVICE_ROLE` | `recommendation` | Identifies this container's role at runtime |
| `tools` | `[]` | No external tools — all logic is deterministic |

## Entrypoint — `main.py`

The entrypoint creates an `InvocationAgentServerHost` (from `azure-ai-agentserver-invocations`) and registers a single `@app.invoke_handler`.

### Payload preparation — `_prepare_payload`

Unlike the other two agents, the recommendation agent includes a **payload normalisation step** before executing:

1. If the request already contains `existing_normalised` and `candidate_normalised`, use them directly.
2. If the request contains raw `existing_funds` and `candidate_funds` symbols, call `normalise_funds()` on each to produce normalised data.
3. If neither format is present, return a 400 error.

This flexibility allows the agent to be called both from the orchestrator (which pre-normalises data) and directly (with raw fund symbols).

### Request flow

1. Parse the incoming JSON request body.
2. Run `_prepare_payload()` to normalise the input format.
3. Pass the prepared payload to `RecommendationExecutor.run()`.
4. Return the result as a JSON response.

Error handling returns structured error responses:

| Error type | HTTP status | Meaning |
|------------|-------------|---------|
| `ValueError` | 400 | Invalid request body or missing required fields |
| `KeyError` | 400 | Missing required field |
| Unexpected | 500 | Internal error (logged, returned as `internal_error`) |

## Executor — `RecommendationExecutor`

**Source:** `backend/src/agents/executors.py`
**Runtime name:** `RecommendationAgent`

The executor inherits from `_BasePortfolioExecutor` and delegates all computation to the shared service layer in `backend/src/services/recommendation.py`.

### Input contract

```json
{
  "existing_normalised": [ ... ],
  "candidate_normalised": [ ... ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `existing_normalised` | `list[NormalisedFund]` | Yes | Existing portfolio funds with normalised holdings |
| `candidate_normalised` | `list[NormalisedFund]` | Yes | Candidate funds with normalised holdings |

Alternatively, raw symbols can be provided (normalised automatically by `_prepare_payload`):

```json
{
  "existing_funds": ["SPY", "QQQ"],
  "candidate_funds": ["ARKK", "SCHD", "VXUS"]
}
```

### Output contract

```json
{
  "recommendations": {
    "SPY": [
      {
        "candidate": "ARKK",
        "total_score": 72.5,
        "overlap_reduction_score": 45.0,
        "performance_score": 32.0,
        "data_quality_penalty": -4.5,
        "cost_penalty": 0.0,
        "explanation": "..."
      }
    ]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `recommendations` | `dict[str, list[ScoredCandidate]]` | Ranked candidates per existing fund, scored 0–100 |

### Scoring algorithm (0–100)

| Component | Range | Description |
|-----------|-------|-------------|
| Overlap Reduction | 0–50 | Lower overlap with existing fund = higher score |
| Performance | 0–40 | Blended 1y/3y/5y returns |
| Data Quality Penalty | 0 to -20 | Penalty for stale data (>90 days) |
| Cost Penalty | 0 to -10 | Expense ratio (0% = no penalty, 1%+ = -10) |

Each scored candidate includes a component breakdown and a human-readable explanation.

### Service functions called

| Function | Purpose |
|----------|---------|
| `build_recommendations(existing_funds, candidate_funds)` | Score all candidates against all existing funds and return ranked results |

## Container image — `Dockerfile`

```dockerfile
FROM public.ecr.aws/docker/library/python:3.14-slim
WORKDIR /app
COPY agents/requirements.txt agents/requirements.txt
RUN pip install --no-cache-dir -r agents/requirements.txt
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/src/ src/
COPY agents/recommendation/main.py main.py
ENV PYTHONPATH=/app
EXPOSE 8088
CMD ["python", "main.py"]
```

Key points:

- **Build context** is the repository root (`docker build -f agents/recommendation/Dockerfile .`).
- Installs both agent-level dependencies (`azure-ai-agentserver-invocations`) and backend service dependencies.
- Copies the full `backend/src/` tree so the executor can import shared services.
- Exposes port **8088** (Foundry default for invocation agents).

## Deployment — `azure.yaml`

```yaml
recommendation-agent:
  project: ./agents/recommendation
  host: azure.ai.agent
  language: docker
  docker:
    path: ./Dockerfile
    context: ../..
    remoteBuild: true
  config:
    container:
      resources:
        cpu: "0.5"
        memory: 1Gi
    startupCommand: python main.py
```

The agent is deployed as a Foundry hosted agent via `azd up`. The Bicep infrastructure under `infra/` provisions the agent runtime alongside the frontend and backend Container Apps.

## Orchestration role

The recommendation agent participates in the system's multi-mode orchestration:

| Mode | Role |
|------|------|
| `agent_local` | `RecommendationExecutor` runs in-process, called by `PortfolioOrchestratorAgent` after analysis and candidate preparation complete |
| `agent_distributed` | `RemoteRecommendationProxy` sends invocations to this Foundry-hosted agent |
| `direct` | Not used — shared services are called directly |
| `workflow` | Not used — legacy MAF workflow layer handles recommendations |

In the **recommendation flow**, this agent is the **sequential fan-in stage**: it always runs **after** the analysis and candidate agents complete their concurrent preparation work. It receives the normalised data from both and produces the final scored results.

## Related documentation

- [Agent Orchestration Architecture](agent-orchestration.md) — full orchestration deep-dive
- [Backend Architecture](backend.md) — shared service layer details
- [Azure Deployment Guide](azd-deployment.md) — deployment and verification steps
