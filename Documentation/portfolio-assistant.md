# Portfolio Assistant Agent
> For informational purposes only; not financial advice.

## Overview

The portfolio-assistant is a conversational agent that uses the **Responses protocol** to provide a natural language interface for portfolio analysis. Unlike the three Invocations-based agents (analysis, candidate, recommendation), the portfolio-assistant is designed for human-to-agent interaction and can be published to **Teams** and **M365 Copilot Studio**.

## Architecture

```mermaid
flowchart TD
    A[Teams / M365 Copilot Studio] -->|Responses protocol| B[portfolio-assistant]
    B -->|LLM understands intent| C[Agent Framework]
    C -->|@tool| D[analyse_portfolio]
    C -->|@tool| E[evaluate_candidates]
    C -->|@tool| F[recommend_switches]
    D --> G[AnalysisExecutor]
    E --> H[CandidateExecutor]
    F --> I[RecommendationExecutor]
    G --> J[Shared deterministic services]
    H --> J
    I --> J
```

The agent uses an LLM (via `FoundryChatClient`) for natural language understanding and response formatting. All financial calculations are performed by deterministic executor functions exposed as `@tool`-decorated functions. The LLM orchestrates which tools to call — it never performs financial calculations itself.

## Protocol

| Property | Value |
|----------|-------|
| Protocol | Responses (OpenAI-compatible) |
| Endpoint | `/responses` |
| SDK | `agent-framework-foundry-hosting` with `ResponsesHostServer` |
| Port | `8088` |

### Responses vs Invocations

| Aspect | Invocations (existing agents) | Responses (portfolio-assistant) |
|--------|-------------------------------|--------------------------------|
| Input | Structured JSON | Natural language text |
| Output | Structured JSON | Conversational text (SSE) |
| Use case | Machine-to-machine (backend) | Human-to-agent (Teams, M365) |
| LLM required | No | Yes |
| Teams/M365 publishable | No | Yes |

## Tools

The portfolio-assistant exposes three deterministic tools to the LLM:

### `analyse_portfolio`

Wraps `AnalysisExecutor` to compute overlap, concentration, asset allocation, sector exposure, and fees for a set of existing funds.

**Parameters:**
- `existing_funds` (required): List of fund symbols, e.g. `["SPY", "QQQ", "VTI"]`
- `allocations` (optional): Allocation weights per fund, e.g. `{"SPY": 0.5, "QQQ": 0.3, "VTI": 0.2}`

### `evaluate_candidates`

Wraps `CandidateExecutor` to evaluate candidate funds for data quality and normalisation.

**Parameters:**
- `candidate_funds` (required): List of candidate fund symbols, e.g. `["ARKK", "SCHD", "VXUS"]`

### `recommend_switches`

Wraps `RecommendationExecutor` to score and rank candidate funds as potential replacements.

**Parameters:**
- `existing_funds` (required): List of existing fund symbols
- `candidate_funds` (required): List of candidate fund symbols

Each candidate receives a score from 0 to 100 based on:
- Overlap Reduction: 0–50 points
- Performance: 0–40 points
- Data Quality Penalty: 0 to −20 points
- Cost Penalty: 0 to −10 points (optional)

## System Instructions

The agent enforces mandatory safety rules via system instructions:

1. Always includes the disclaimer: "For informational purposes only; not financial advice."
2. Never provides financial advice or uses directive language
3. Never fabricates data — only presents tool output
4. Always includes data quality information
5. Always includes explainable reasoning and score breakdowns

## Environment Variables

| Variable | Required | Set by | Description |
|----------|----------|--------|-------------|
| `FOUNDRY_PROJECT_ENDPOINT` | Yes | Platform (auto-injected) | Foundry project endpoint — do NOT set manually |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | Yes | User (before `azd up`) | LLM model deployment name in your Foundry project |
| `LOG_LEVEL` | No | User (optional) | Logging level (default: `INFO`) |

### Pre-deployment setup

`AZURE_AI_MODEL_DEPLOYMENT_NAME` must be set in the azd environment **before** running `azd up`. The value in `agent.yaml` uses `${AZURE_AI_MODEL_DEPLOYMENT_NAME}` which is substituted at deploy time.

```bash
# Check available model deployments in your Foundry project
az cognitiveservices account deployment list \
  --name <ai-account-name> --resource-group <rg> --output table

# Set the model deployment name
azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME gpt-4.1-mini
```

If omitted, the agent container will crash at startup with:
```
OSError: AZURE_AI_MODEL_DEPLOYMENT_NAME environment variable is not set.
```

## Deployment

The portfolio-assistant is deployed as a Foundry hosted agent via `azd up`, alongside the existing three agents:

```yaml
# azure.yaml
portfolio-assistant:
    project: ./agents/portfolio-assistant
    host: azure.ai.agent
    language: docker
    docker:
        path: ./Dockerfile
        context: ../..
        remoteBuild: true
```

### Publishing to Teams / M365 Copilot Studio

After deployment with `azd up`, the portfolio-assistant can be published to Teams and Microsoft 365 Copilot. This requires the Responses protocol (which the agent already implements) and appropriate RBAC roles.

For the complete step-by-step publishing workflow, including prerequisites, scope options, admin approval, troubleshooting, and limitations, see:

**→ [Publishing to Teams & M365](publishing-teams-m365.md)**

The Responses protocol powers the agent logic; the Activity protocol for Teams channel integration is managed automatically by the Foundry platform.

## Local Testing

```bash
# Set required environment variables
export FOUNDRY_PROJECT_ENDPOINT="https://<account>.services.ai.azure.com/api/projects/<project>"
export AZURE_AI_MODEL_DEPLOYMENT_NAME="gpt-4.1-mini"

# Start the agent locally
cd agents/portfolio-assistant
python main.py

# Test the Responses endpoint
curl -sS -X POST http://localhost:8088/responses \
  -H "Content-Type: application/json" \
  -d '{"input": "Analyse my portfolio with SPY, QQQ, and VTI", "stream": false}' | jq .
```

## File Structure

```
agents/portfolio-assistant/
├── main.py           # Agent entrypoint with tools and ResponsesHostServer
├── agent.yaml        # Foundry agent manifest (responses protocol)
├── Dockerfile        # Container build definition
└── requirements.txt  # Python dependencies
```

## Relationship to Other Agents

| Agent | Protocol | Purpose | Audience |
|-------|----------|---------|----------|
| `analysis-agent` | Invocations | Overlap, concentration, sectors, fees | Backend (machine-to-machine) |
| `candidate-agent` | Invocations | Candidate normalisation, data quality | Backend (machine-to-machine) |
| `recommendation-agent` | Invocations | Scoring and ranking | Backend (machine-to-machine) |
| `portfolio-assistant` | **Responses** | Conversational portfolio analysis | **Teams, M365, humans** |

The portfolio-assistant and the three Invocations agents share the same deterministic business logic via the executor classes (`AnalysisExecutor`, `CandidateExecutor`, `RecommendationExecutor`) and the shared service layer in `backend/src/services/`.
