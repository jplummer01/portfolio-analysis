# Portfolio Overlap & Fund Switch Candidate Analyzer

A web application that analyzes mutual fund/ETF portfolio overlap and recommends switch candidates based on overlap reduction, performance, and data quality.

> **For informational purposes only; not financial advice.**

**In this quickstart, you:**

- Set up the project and install dependencies
- Test the application locally
- Deploy to Azure (Container Apps + Foundry hosted agents)
- Verify your deployment and interact with the app

## Prerequisites

Before you begin, you need:

- An [Azure subscription](https://azure.microsoft.com/pricing/purchase-options/azure-account) with Contributor access
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) (`azd`) version 1.24.0 or later
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) (`az`)
- [Python 3.11+](https://www.python.org/downloads/) (tested with 3.14)
- [Rust](https://rustup.rs/) (stable toolchain, for the frontend)

## Step 1: Set up the project

Clone the repository and install backend dependencies:

```bash
git clone https://github.com/your-org/portfolio-analysis.git
cd portfolio-analysis/backend
pip install -r requirements.txt
```

## Step 2: Test locally

Before deploying, verify the application works on your machine.

### Start the backend

```bash
cd backend
python3 -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```

### Start the frontend (separate terminal)

```bash
cd frontend
export BACKEND_BASE_URL=http://127.0.0.1:8000
cargo run
```

App available at: http://127.0.0.1:3000

### Verify locally

```bash
# Health check
curl http://127.0.0.1:3000/api/health

# Analyse portfolio overlap
curl -X POST http://127.0.0.1:3000/api/analyse \
  -H "Content-Type: application/json" \
  -d '{"existing_funds": ["SPY", "QQQ", "VTI"]}'

# Score switch candidates
curl -X POST http://127.0.0.1:3000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"existing_funds": ["SPY"], "candidate_funds": ["ARKK", "SCHD", "VXUS"]}'
```

You can also open http://127.0.0.1:3000 in your browser and use the web UI to **Ingest**, **Analyse**, and **Recommend**.

Available stub funds: `SPY`, `QQQ`, `VTI`, `ARKK`, `SCHD`, `VUG`, `VXUS`

### Debug mode

Add `?debug=true` to any analyse or recommend request to see execution diagnostics (which mode ran, which agents were called, latency, fallback status):

```bash
# Debug analyse
curl -X POST http://127.0.0.1:3000/api/analyse?debug=true \
  -H "Content-Type: application/json" \
  -d '{"existing_funds": ["SPY", "QQQ"]}'

# Debug recommend
curl -X POST http://127.0.0.1:3000/api/recommend?debug=true \
  -H "Content-Type: application/json" \
  -d '{"existing_funds": ["SPY"], "candidate_funds": ["ARKK", "SCHD"]}'
```

The response includes a `debug_info` object with `execution_mode`, `agents_called`, `fallback_used`, and `total_latency_ms`. In the web UI, check the **Debug mode** checkbox on the Analyse or Recommend page.

### Run tests

```bash
cd backend
python3 -m pytest tests/ -v
```

## Step 3: Deploy to Azure

Install the `ai agent` extension and deploy all services:

```bash
az login
azd auth login
azd ext install azure.ai.agents
azd up
```

This provisions:

| Resource | Purpose |
|----------|---------|
| Frontend Container App | Public entrypoint (Rust/Leptos SSR on port 3000) |
| Backend Container App | Internal API (Python/FastAPI on port 8000) |
| Analysis Agent | Overlap, concentration, asset allocation, sectors, fees |
| Candidate Agent | Candidate universe normalisation and data quality |
| Recommendation Agent | Deterministic scoring (0–100) with explanations |
| Portfolio Assistant | Conversational agent (Responses protocol) for Teams/M365 Copilot Studio |
| Azure Container Registry | Container images |
| AI Foundry Project | Hosted agent runtime |

> **Tip:** Run `azd down` when finished to delete resources and stop incurring charges.

## Step 4: Verify the deployment

After `azd up` completes, check that the frontend is responding:

```bash
curl https://<your-frontend-url>/api/health
```

You should see:

```json
{"status": "healthy"}
```

Open the frontend URL in your browser. The web UI has three tabs:

| Tab | Action | What you see |
|-----|--------|--------------|
| **Ingest** | Enter fund symbols | Holdings loaded from stub data |
| **Analyse** | Click "Analyse portfolio" | Overlap matrices, concentration, asset allocation, sectors, fees |
| **Recommend** | Click "Score candidates" | Ranked candidates (0–100), breakdowns, explanations |

Test the API directly against the deployed app:

```bash
curl -X POST https://<your-frontend-url>/api/analyse \
  -H "Content-Type: application/json" \
  -d '{"existing_funds": ["SPY", "QQQ", "VTI"]}'

curl -X POST https://<your-frontend-url>/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"existing_funds": ["SPY"], "candidate_funds": ["ARKK", "SCHD", "VXUS"]}'
```

## Architecture

```
Browser → Frontend (Axum :3000) → /api/* proxy → Backend (FastAPI :8000)
                                                       ↓
                                           Foundry Hosted Agents
                                    (analysis / candidate / recommendation)

Teams / M365 Copilot Studio → Foundry Responses Protocol → Portfolio Assistant Agent
                                                                    ↓
                                                          Deterministic Executors
                                                   (analysis / candidate / recommendation)
```

Single-origin design — the browser only talks to the frontend. All `/api/*` requests are reverse-proxied to the backend, which can optionally delegate to Foundry hosted agents.

The portfolio-assistant agent uses the Responses protocol and can be published to Teams and M365 Copilot Studio for a conversational experience.

## Documentation

| Document | Description |
|----------|-------------|
| [Backend Architecture](Documentation/backend.md) | FastAPI server, API endpoints, deterministic tools, Pydantic models |
| [Frontend Architecture](Documentation/frontend.md) | Rust/Leptos SSR, Axum server, reverse proxy, page descriptions |
| [Multi-Agent Orchestration](Documentation/multi-agent-orchestration.md) | MAF @workflow/@step, analysis pipelines, fallback strategy |
| [Agent Orchestration Architecture](Documentation/agent-orchestration.md) | Orchestrator/sub-agent pattern, execution modes, shared services |
| [Azure Deployment Guide](Documentation/azd-deployment.md) | Full deployment flow, environment variables, troubleshooting |
| [Analysis Agent](Documentation/analysis-agent.md) | Overlap, concentration, asset allocation, sector exposure, fees |
| [Candidate Agent](Documentation/candidate-agent.md) | Holdings normalisation and data quality checks |
| [Recommendation Agent](Documentation/recommendation-agent.md) | 0–100 scoring with component breakdowns |
| [Portfolio Assistant](Documentation/portfolio-assistant.md) | Conversational agent for Teams/M365 Copilot Studio (Responses protocol) |
| [Testing Deployed Agents](Documentation/testing-deployed-agents.md) | How to test all agents after `azd up`: CLI, Foundry Playground, web frontend |

## Clean up resources

To delete all deployed resources:

```bash
azd down
```

## License

This project is for demonstration purposes.

