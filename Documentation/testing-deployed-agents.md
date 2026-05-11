# Testing Deployed Agents After `azd up`

> For informational purposes only; not financial advice.

## Overview

After running `azd up`, the project deploys five services to Azure. This guide shows how to test each agent through three interfaces:

1. **CLI via `curl`** — direct HTTP requests from your terminal
2. **Foundry Playground** — interactive testing in the Azure AI Foundry portal
3. **Web frontend** — the deployed Rust/Leptos app

| Agent | Protocol | How to test |
|-------|----------|-------------|
| `analysis-agent` | Invocations | curl, Web frontend |
| `candidate-agent` | Invocations | curl, Web frontend |
| `recommendation-agent` | Invocations | curl, Web frontend |
| `portfolio-assistant` | Responses | curl, Foundry Playground |
| Backend API (`backend-api`) | HTTP | curl, Web frontend |

---

## Prerequisites

Before testing, gather the deployment outputs:

```bash
# Get all environment values
azd env get-values

# Key values you need:
# FRONTEND_URI                    — public frontend URL
# AZURE_AI_PROJECT_ENDPOINT       — Foundry project endpoint (for direct agent calls)
# AZURE_AI_MODEL_DEPLOYMENT_NAME  — LLM model deployment (required for portfolio-assistant)
```

> **Important:** If `AZURE_AI_MODEL_DEPLOYMENT_NAME` was not set before `azd up`, the portfolio-assistant agent will be in a failed state. Set it and redeploy:
> ```bash
> azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME <model-deployment-name>
> azd deploy portfolio-assistant
> ```

For direct agent calls via curl, you also need an access token:

```bash
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)
```

Available stub funds for all tests: `SPY`, `QQQ`, `VTI`, `ARKK`, `SCHD`, `VUG`, `VXUS`

---

## 1. Testing via CLI (`curl`)

### 1.1 Health check (via frontend proxy)

```bash
curl https://<FRONTEND_URI>/api/health
```

Expected response:

```json
{"status": "healthy"}
```

### 1.2 Analysis (via frontend → backend → agents)

This tests the full request path: frontend proxy → backend → distributed agents (if `EXECUTION_MODE=agent_distributed`).

```bash
# Basic analysis
curl -sS -X POST https://<FRONTEND_URI>/api/analyse \
  -H "Content-Type: application/json" \
  -d '{"existing_funds": ["SPY", "QQQ", "VTI"]}' | jq .

# With debug info to see which agents were called
curl -sS -X POST "https://<FRONTEND_URI>/api/analyse?debug=true" \
  -H "Content-Type: application/json" \
  -d '{"existing_funds": ["SPY", "QQQ", "VTI"]}' | jq .
```

The debug response includes `debug_info` with `execution_mode`, `agents_called`, `fallback_used`, and `total_latency_ms`.

### 1.3 Recommendations (via frontend → backend → agents)

```bash
curl -sS -X POST https://<FRONTEND_URI>/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"existing_funds": ["SPY", "QQQ"], "candidate_funds": ["ARKK", "SCHD", "VXUS"]}' | jq .

# With debug info
curl -sS -X POST "https://<FRONTEND_URI>/api/recommend?debug=true" \
  -H "Content-Type: application/json" \
  -d '{"existing_funds": ["SPY"], "candidate_funds": ["ARKK", "SCHD", "VXUS"]}' | jq .
```

### 1.4 Direct Invocations agent calls (bypassing frontend/backend)

Call the hosted agents directly via the Foundry project endpoint. This is useful for isolating agent issues from the frontend/backend layer.

```bash
# Set your project endpoint and token
ENDPOINT="https://<account>.services.ai.azure.com/api/projects/<project>"
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)

# Analysis agent
curl -sS -X POST \
  "$ENDPOINT/agents/analysis-agent/endpoint/protocols/invocations?api-version=v1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Foundry-Features: HostedAgents=V1Preview" \
  -d '{
    "existing_funds": ["SPY", "QQQ", "VTI"],
    "allocations": null
  }' | jq .

# Candidate agent
curl -sS -X POST \
  "$ENDPOINT/agents/candidate-agent/endpoint/protocols/invocations?api-version=v1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Foundry-Features: HostedAgents=V1Preview" \
  -d '{
    "candidate_funds": ["ARKK", "SCHD", "VXUS"]
  }' | jq .

# Recommendation agent
curl -sS -X POST \
  "$ENDPOINT/agents/recommendation-agent/endpoint/protocols/invocations?api-version=v1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Foundry-Features: HostedAgents=V1Preview" \
  -d '{
    "existing_funds": ["SPY"],
    "candidate_funds": ["ARKK", "SCHD"]
  }' | jq .
```

### 1.5 Portfolio Assistant (Responses protocol)

The portfolio-assistant uses the Responses protocol, so the request format differs from the Invocations agents:

```bash
ENDPOINT="https://<account>.services.ai.azure.com/api/projects/<project>"
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)

# Non-streaming request
curl -sS -X POST \
  "$ENDPOINT/agents/portfolio-assistant/endpoint/protocols/openai/v1/responses?api-version=v1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Analyse my portfolio with SPY, QQQ, and VTI",
    "stream": false
  }' | jq .

# Streaming request (server-sent events)
curl -sS -N -X POST \
  "$ENDPOINT/agents/portfolio-assistant/endpoint/protocols/openai/v1/responses?api-version=v1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "What is the overlap between SPY and QQQ?",
    "stream": true
  }'
```

Example natural language queries to try:

```bash
# Portfolio analysis
"Analyse my portfolio with SPY, QQQ, and VTI"
"What is the overlap between SPY and VTI?"
"Show me the sector exposure for QQQ and VUG"

# Candidate evaluation
"Evaluate ARKK, SCHD, and VXUS as potential funds"

# Recommendations
"I hold SPY and QQQ. Recommend replacements from ARKK, SCHD, and VXUS"
"Score VXUS as a replacement for VTI in my portfolio"

# Multi-step workflow
"Analyse SPY and QQQ, then recommend which of ARKK, SCHD, VXUS would reduce overlap"
```

---

## 2. Testing via Foundry Playground

The Azure AI Foundry portal provides a built-in playground for testing agents interactively.

### 2.1 Navigate to the Playground

1. Go to [Azure AI Foundry](https://ai.azure.com)
2. Select your project (e.g. `my-ai-project`)
3. In the left navigation, select **Agents**
4. You will see the deployed agents listed:
   - `analysis-agent` (Invocations)
   - `candidate-agent` (Invocations)
   - `recommendation-agent` (Invocations)
   - `portfolio-assistant` (Responses)

### 2.2 Test the Portfolio Assistant (Responses)

1. Click on **portfolio-assistant** in the agent list
2. Click **Try in Playground** (or **Open in Playground**)
3. The playground provides a chat-style interface
4. Type natural language queries directly:

| Try this | What happens |
|----------|-------------|
| "Analyse my portfolio with SPY, QQQ, and VTI" | Agent calls `analyse_portfolio` tool, returns overlap matrix, concentration, sectors, fees |
| "Evaluate ARKK and SCHD as candidates" | Agent calls `evaluate_candidates` tool, returns normalised holdings and data quality |
| "I hold SPY. Recommend replacements from ARKK, SCHD, VXUS" | Agent calls `recommend_switches` tool, returns ranked candidates with scores |
| "What is the overlap between SPY and QQQ?" | Agent analyses and explains the overlap in conversational format |

The playground shows:
- The agent's text responses
- Tool calls being made (you can expand to see the tool input/output)
- Conversation history across multiple turns

### 2.3 Test Invocations Agents

Invocations agents do not have a chat-style playground. To test them from the portal:

1. Click on an Invocations agent (e.g. `analysis-agent`)
2. Use the **Test** tab or **Endpoint** section
3. Send a raw JSON payload:

For `analysis-agent`:
```json
{
  "existing_funds": ["SPY", "QQQ", "VTI"],
  "allocations": null
}
```

For `candidate-agent`:
```json
{
  "candidate_funds": ["ARKK", "SCHD", "VXUS"]
}
```

For `recommendation-agent`:
```json
{
  "existing_funds": ["SPY"],
  "candidate_funds": ["ARKK", "SCHD"]
}
```

### 2.4 Check Agent Status

In the Agents list view, verify each agent shows:

| Agent | Status | Protocol |
|-------|--------|----------|
| `analysis-agent` | Active | Invocations |
| `candidate-agent` | Active | Invocations |
| `recommendation-agent` | Active | Invocations |
| `portfolio-assistant` | Active | Responses |

If an agent shows **Creating** or **Failed**, check the version details for error messages.

---

## 3. Testing via the Web Frontend

The deployed frontend provides a visual interface for testing the analysis and recommendation workflows.

### 3.1 Access the Frontend

Open the frontend URL in your browser:

```
https://<FRONTEND_URI>
```

The app has three main pages:

### 3.2 Ingest Page

1. Navigate to the **Ingest** tab
2. Enter fund symbols manually: `SPY, QQQ, VTI`
3. Or paste holdings data, or upload a CSV/JSON file
4. Click **Submit** to load the fund data

### 3.3 Analyse Page

1. Navigate to the **Analyse** tab
2. Enter existing fund symbols (e.g. `SPY, QQQ, VTI`)
3. Click **Analyse portfolio**
4. Results include:
   - Overlap matrix (unweighted and weighted)
   - Portfolio concentration summary
   - Top overlapping tickers
   - Asset allocation breakdown
   - Sector exposure chart
   - Fee analysis
   - Data quality indicators
   - Disclaimer and timestamps
5. Check **Debug mode** to see which execution mode was used and which agents were called

### 3.4 Recommend Page

1. Navigate to the **Recommend** tab
2. Enter existing funds (e.g. `SPY`)
3. Enter candidate funds (e.g. `ARKK, SCHD, VXUS`)
4. Click **Score candidates**
5. Results include:
   - Ranked candidates with composite scores (0–100)
   - Score breakdown per candidate (overlap reduction, performance, data quality, cost)
   - Explanation text for each recommendation
   - Data quality summary
   - Disclaimer
6. Check **Debug mode** to see agent call records with latency and status

### 3.5 What the Frontend Tests

The web frontend exercises the full end-to-end flow:

```
Browser → Frontend (Axum) → /api/* proxy → Backend (FastAPI) → Foundry Agents
```

If the frontend works correctly, it confirms:
- Axum reverse proxy is functioning
- Backend API is reachable internally
- Agent distributed mode is working (if `EXECUTION_MODE=agent_distributed`)
- Fallback to direct mode works if agents are unavailable

> **Note:** The portfolio-assistant (Responses protocol) is not currently integrated into the web frontend. It is accessed via the Foundry Playground or direct curl calls. A future `/api/chat` endpoint could enable frontend integration.

---

## Troubleshooting

### Common issues

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `curl` returns connection refused | Frontend not deployed or wrong URL | Check `azd env get-values` for `FRONTEND_URI` |
| 401 Unauthorized on direct agent calls | Token expired or wrong scope | Re-run `az account get-access-token --resource https://ai.azure.com` |
| 400 BadRequest on Invocations agent | Missing `api-version` or `Foundry-Features` header | Ensure `?api-version=v1` and `Foundry-Features: HostedAgents=V1Preview` |
| Agent shows "Creating" status | Still provisioning | Wait and poll: `azd ai agent show` |
| Debug info shows `fallback_used: true` | Distributed agents unreachable | Check agent status in Foundry portal; verify `FOUNDRY_PROJECT_ENDPOINT` |
| Portfolio assistant returns no tool calls | Model deployment not found | Verify `AZURE_AI_MODEL_DEPLOYMENT_NAME` is set and valid |

### Useful diagnostic commands

```bash
# Check deployed environment values
azd env get-values

# List container apps
az containerapp list --resource-group <rg> --output table

# Check agent status
azd ai agent show

# Get fresh token
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)

# Backend health check (direct, if internal ingress is accessible)
curl https://<BACKEND_URI>/api/health

# Frontend health check (via proxy)
curl https://<FRONTEND_URI>/api/health
```
