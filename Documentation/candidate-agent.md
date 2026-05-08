# Candidate Agent

> For informational purposes only; not financial advice.

## Overview

The **candidate-agent** is a Foundry hosted agent that evaluates the candidate fund universe. Given a list of candidate fund symbols, it normalises their holdings and performs data quality checks. This produces the prepared candidate data that the recommendation agent needs for scoring. All computations are **deterministic** — no LLM reasoning is involved.

The agent runs as a standalone container behind the [Invocations protocol](https://github.com/microsoft/AgentSchema) and is deployed to Microsoft Foundry Agent Service via `azd up`.

## Configuration — `agent.yaml`

```yaml
kind: hosted
name: candidate-agent
protocols:
  - protocol: invocations
    version: "1.0.0"
resources:
  cpu: "0.5"
  memory: 1Gi
environment_variables:
  - name: SERVICE_ROLE
    value: candidate
tools: []
```

| Field | Value | Description |
|-------|-------|-------------|
| `kind` | `hosted` | Runs as a Foundry hosted agent |
| `name` | `candidate-agent` | Deployment name used in `azure.yaml` |
| `protocol` | `invocations` v1.0.0 | Accepts `POST /invocations` payloads |
| `resources` | 0.5 CPU / 1 GiB RAM | Container resource limits |
| `SERVICE_ROLE` | `candidate` | Identifies this container's role at runtime |
| `tools` | `[]` | No external tools — all logic is deterministic |

## Entrypoint — `main.py`

The entrypoint creates an `InvocationAgentServerHost` (from `azure-ai-agentserver-invocations`) and registers a single `@app.invoke_handler`:

1. Parse the incoming JSON request body.
2. Pass the payload to `CandidateExecutor.run()`.
3. Return the result as a JSON response.

Error handling returns structured error responses:

| Error type | HTTP status | Meaning |
|------------|-------------|---------|
| `ValueError` | 400 | Invalid request body (not JSON, not an object) |
| `KeyError` | 400 | Missing required field (e.g. `candidate_funds`) |
| Unexpected | 500 | Internal error (logged, returned as `internal_error`) |

## Executor — `CandidateExecutor`

**Source:** `backend/src/agents/executors.py`
**Runtime name:** `CandidateUniverseAnalysisAgent`

The executor inherits from `_BasePortfolioExecutor` and delegates all computation to the shared service layer in `backend/src/services/portfolio_analysis.py`.

### Input contract

```json
{
  "candidate_funds": ["ARKK", "SCHD", "VXUS"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `candidate_funds` | `list[str]` | Yes | Fund symbols to evaluate as potential switch candidates |

### Output contract

```json
{
  "normalised_candidates": [ ... ],
  "candidate_data_quality": [ ... ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `normalised_candidates` | `list[NormalisedFund]` | Holdings data with weights normalised to sum to 1.0 |
| `candidate_data_quality` | `list[DataQualityEntry]` | Freshness and staleness flags per candidate fund (>90 days = stale) |

### Service functions called

| Function | Purpose |
|----------|---------|
| `normalise_funds(candidate_symbols)` | Look up holdings for each candidate and normalise weights |
| `check_data_quality(candidate_symbols)` | Assess freshness of holdings data, flagging stale entries |

## Container image — `Dockerfile`

```dockerfile
FROM public.ecr.aws/docker/library/python:3.14-slim
WORKDIR /app
COPY agents/requirements.txt agents/requirements.txt
RUN pip install --no-cache-dir -r agents/requirements.txt
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/src/ src/
COPY agents/candidate/main.py main.py
ENV PYTHONPATH=/app
EXPOSE 8088
CMD ["python", "main.py"]
```

Key points:

- **Build context** is the repository root (`docker build -f agents/candidate/Dockerfile .`).
- Installs both agent-level dependencies (`azure-ai-agentserver-invocations`) and backend service dependencies.
- Copies the full `backend/src/` tree so the executor can import shared services.
- Exposes port **8088** (Foundry default for invocation agents).

## Deployment — `azure.yaml`

```yaml
candidate-agent:
  project: ./agents/candidate
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

The candidate agent participates in the system's multi-mode orchestration:

| Mode | Role |
|------|------|
| `agent_local` | `CandidateExecutor` runs in-process, called by `PortfolioOrchestratorAgent` |
| `agent_distributed` | `RemoteCandidateProxy` sends invocations to this Foundry-hosted agent |
| `direct` | Not used — shared services are called directly |
| `workflow` | Not used — legacy MAF workflow layer handles candidate evaluation |

In the **recommendation flow**, the candidate agent runs **concurrently** with the analysis agent (via `asyncio.gather`). Its output — `normalised_candidates` — is passed to the recommendation agent for the final sequential scoring step.

## Related documentation

- [Agent Orchestration Architecture](agent-orchestration.md) — full orchestration deep-dive
- [Backend Architecture](backend.md) — shared service layer details
- [Azure Deployment Guide](azd-deployment.md) — deployment and verification steps
