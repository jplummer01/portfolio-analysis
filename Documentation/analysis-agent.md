# Analysis Agent

> For informational purposes only; not financial advice.

## Overview

The **analysis-agent** is a Foundry hosted agent that performs existing portfolio analysis. Given a list of fund symbols (and optional allocation weights), it computes overlap matrices, portfolio concentration, data quality assessments, asset allocation breakdowns, sector exposure, and fee analysis. All computations are **deterministic** — no LLM reasoning is involved.

The agent runs as a standalone container behind the [Invocations protocol](https://github.com/microsoft/AgentSchema) and is deployed to Microsoft Foundry Agent Service via `azd up`.

## Configuration — `agent.yaml`

```yaml
kind: hosted
name: analysis-agent
protocols:
  - protocol: invocations
    version: "1.0.0"
resources:
  cpu: "0.5"
  memory: 1Gi
environment_variables:
  - name: SERVICE_ROLE
    value: analysis
tools: []
```

| Field | Value | Description |
|-------|-------|-------------|
| `kind` | `hosted` | Runs as a Foundry hosted agent |
| `name` | `analysis-agent` | Deployment name used in `azure.yaml` |
| `protocol` | `invocations` v1.0.0 | Accepts `POST /invocations` payloads |
| `resources` | 0.5 CPU / 1 GiB RAM | Container resource limits |
| `SERVICE_ROLE` | `analysis` | Identifies this container's role at runtime |
| `tools` | `[]` | No external tools — all logic is deterministic |

## Entrypoint — `main.py`

The entrypoint creates an `InvocationAgentServerHost` (from `azure-ai-agentserver-invocations`) and registers a single `@app.invoke_handler`:

1. Parse the incoming JSON request body.
2. Pass the payload to `AnalysisExecutor.run()`.
3. Return the result as a JSON response.

Error handling returns structured error responses:

| Error type | HTTP status | Meaning |
|------------|-------------|---------|
| `ValueError` | 400 | Invalid request body (not JSON, not an object) |
| `KeyError` | 400 | Missing required field (e.g. `existing_funds`) |
| Unexpected | 500 | Internal error (logged, returned as `internal_error`) |

## Executor — `AnalysisExecutor`

**Source:** `backend/src/agents/executors.py`
**Runtime name:** `ExistingPortfolioAnalysisAgent`

The executor inherits from `_BasePortfolioExecutor` and delegates all computation to the shared service layer in `backend/src/services/portfolio_analysis.py`.

### Input contract

```json
{
  "existing_funds": ["SPY", "QQQ", "VTI"],
  "allocations": [0.5, 0.3, 0.2]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `existing_funds` | `list[str]` | Yes | Fund symbols to analyse |
| `allocations` | `list[float]` | No | Portfolio weight per fund (equal-weight if omitted) |

### Output contract

```json
{
  "overlap_matrix": { ... },
  "concentration": { ... },
  "top_overlaps": [ ... ],
  "data_quality": [ ... ],
  "asset_allocation": { ... },
  "sector_exposure": { ... },
  "fee_analysis": { ... }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `overlap_matrix` | `OverlapMatrix` | Unweighted and weighted pairwise overlap between funds |
| `concentration` | `ConcentrationResult` | Portfolio-level concentration metrics |
| `top_overlaps` | `list[OverlapPair]` | Highest-overlap fund pairs ranked descending |
| `data_quality` | `list[DataQualityEntry]` | Freshness and staleness flags per fund (>90 days = stale) |
| `asset_allocation` | `AssetAllocationResult` | Equity / Fixed Income / Cash breakdown per fund and portfolio-wide |
| `sector_exposure` | `SectorExposureResult` | Morningstar-compatible sector weights (Technology, Healthcare, etc.) |
| `fee_analysis` | `FeeAnalysisResult` | Expense ratios per fund and portfolio-weighted average |

### Service functions called

| Function | Purpose |
|----------|---------|
| `normalise_funds(symbols)` | Look up holdings and normalise weights to sum to 1.0 |
| `build_overlap_summary(normalised)` | Compute pairwise overlap matrix and top overlapping pairs |
| `build_concentration_summary(normalised, allocations)` | Compute portfolio-level concentration |
| `check_data_quality(symbols)` | Assess freshness of holdings data |
| `build_asset_allocation_summary(normalised, allocations)` | Equity/Fixed Income/Cash breakdown |
| `build_sector_exposure_summary(normalised, allocations)` | Sector weights |
| `build_fee_analysis_summary(normalised, allocations)` | Fee analysis |

## Container image — `Dockerfile`

```dockerfile
FROM public.ecr.aws/docker/library/python:3.14-slim
WORKDIR /app
COPY agents/requirements.txt agents/requirements.txt
RUN pip install --no-cache-dir -r agents/requirements.txt
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/src/ src/
COPY agents/analysis/main.py main.py
ENV PYTHONPATH=/app
EXPOSE 8088
CMD ["python", "main.py"]
```

Key points:

- **Build context** is the repository root (`docker build -f agents/analysis/Dockerfile .`).
- Installs both agent-level dependencies (`azure-ai-agentserver-invocations`) and backend service dependencies.
- Copies the full `backend/src/` tree so the executor can import shared services.
- Exposes port **8088** (Foundry default for invocation agents).

## Deployment — `azure.yaml`

```yaml
analysis-agent:
  project: ./agents/analysis
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

The analysis agent participates in the system's multi-mode orchestration:

| Mode | Role |
|------|------|
| `agent_local` | `AnalysisExecutor` runs in-process, called by `PortfolioOrchestratorAgent` |
| `agent_distributed` | `RemoteAnalysisProxy` sends invocations to this Foundry-hosted agent |
| `direct` | Not used — shared services are called directly |
| `workflow` | Not used — legacy MAF workflow layer handles analysis |

In the **recommendation flow**, the analysis agent runs **concurrently** with the candidate agent (via `asyncio.gather`) before the recommendation agent performs the final sequential scoring step.

## Related documentation

- [Agent Orchestration Architecture](agent-orchestration.md) — full orchestration deep-dive
- [Backend Architecture](backend.md) — shared service layer details
- [Azure Deployment Guide](azd-deployment.md) — deployment and verification steps
