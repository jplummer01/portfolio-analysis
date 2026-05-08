# Portfolio Overlap & Fund Switch Candidate Analyzer

A web application that analyzes mutual fund/ETF portfolio overlap and recommends switch candidates based on overlap reduction, performance, and data quality.

> **For informational purposes only; not financial advice.**

**In this quickstart, you:**

- Deploy the application to Azure (Container Apps + Foundry hosted agents)
- Analyse portfolio overlap and concentration
- Score switch candidates with explainable breakdowns
- Interact with the web UI or call the API directly

## Prerequisites

Before you begin, you need:

- An [Azure subscription](https://azure.microsoft.com/pricing/purchase-options/azure-account) with Contributor access
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) (`azd`) version 1.24.0 or later
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) (`az`)
- [Python 3.11+](https://www.python.org/downloads/) (tested with 3.14)
- [Rust](https://rustup.rs/) (stable toolchain, for the frontend)

## Step 1: Deploy to Azure

Install the `ai agent` extension and deploy all services in one command:

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
| Azure Container Registry | Container images |
| AI Foundry Project | Hosted agent runtime |

> **Tip:** Run `azd down` when finished to delete resources and stop incurring charges.

## Step 2: Verify the deployment

After `azd up` completes, check that the frontend is responding:

```bash
curl https://<your-frontend-url>/api/health
```

You should see:

```json
{"status": "healthy"}
```

Open the frontend URL in your browser to access the web UI.

## Step 3: Use the application

The web UI has three tabs:

### Ingest — Add fund symbols

Enter fund symbols to load holdings data.

Available stub funds: `SPY`, `QQQ`, `VTI`, `ARKK`, `SCHD`, `VUG`, `VXUS`

### Analyse — Inspect portfolio overlap

Enter existing funds and click **Analyse portfolio** to see:
- Overlap matrices (unweighted + weighted)
- Portfolio concentration
- Asset allocation and sector exposure
- Fee analysis and data quality

```bash
curl -X POST https://<your-frontend-url>/api/analyse \
  -H "Content-Type: application/json" \
  -d '{"existing_funds": ["SPY", "QQQ", "VTI"]}'
```

### Recommend — Score switch candidates

Enter existing funds and candidates, then click **Score candidates** to see:
- Ranked candidates per fund (scored 0–100)
- Component-level breakdowns
- Human-readable explanations
- Data quality penalties

```bash
curl -X POST https://<your-frontend-url>/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"existing_funds": ["SPY"], "candidate_funds": ["ARKK", "SCHD", "VXUS"]}'
```

## Run locally (development)

### Start the backend

```bash
cd backend
pip install -r requirements.txt
python3 -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```

### Start the frontend

```bash
cd frontend
export BACKEND_BASE_URL=http://127.0.0.1:8000
cargo run
```

App available at: http://127.0.0.1:3000

### Run tests

```bash
cd backend
python3 -m pytest tests/ -v
```

## Architecture

```
Browser → Frontend (Axum :3000) → /api/* proxy → Backend (FastAPI :8000)
                                                       ↓
                                           Foundry Hosted Agents
                                    (analysis / candidate / recommendation)
```

Single-origin design — the browser only talks to the frontend. All `/api/*` requests are reverse-proxied to the backend, which can optionally delegate to Foundry hosted agents.

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

## Clean up resources

To delete all deployed resources:

```bash
azd down
```

## License

This project is for demonstration purposes.

