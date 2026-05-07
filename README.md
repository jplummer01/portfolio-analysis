# Portfolio Overlap & Fund Switch Candidate Analyzer

A web application that analyzes mutual fund/ETF portfolio overlap and recommends switch candidates based on overlap reduction, performance, and data quality.

> **For informational purposes only; not financial advice.**

## Architecture

```
┌─────────────────────────────────────────────┐
│  Browser → http://127.0.0.1:3000            │
├─────────────────────────────────────────────┤
│  Frontend (Rust / Leptos SSR / Axum)        │
│  - Serves HTML pages                        │
│  - Proxies /api/* → Backend                 │
├─────────────────────────────────────────────┤
│  Backend (Python / FastAPI / MAF)           │
│  - Deterministic tools (overlap, scoring)   │
│  - Agent Framework workflows (optional)     │
│  - Stub holdings data                       │
└─────────────────────────────────────────────┘
```

Single-origin design — the browser only talks to the frontend server. All `/api/*` requests are reverse-proxied to the backend.

## Features

- **Fund Ingestion** — Enter symbols manually, paste lists, or upload CSV/JSON files
- **Overlap Analysis** — Unweighted and weighted overlap matrices, portfolio concentration
- **Candidate Recommendations** — Scored 0–100 with breakdown (overlap reduction, performance, data quality, cost)
- **Data Quality** — Stale data detection (>90 days), freshness indicators
- **MAF Workflows** — Optional Microsoft Agent Framework orchestration with `@workflow`/`@step`

## Prerequisites

- **Python 3.11+** (tested with 3.14)
- **Rust** (stable toolchain, for the frontend)
- **pip** (Python package manager)

## Quick Start

### 1. Start the Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Set environment variables (or use defaults)
export BACKEND_HOST=127.0.0.1
export BACKEND_PORT=8000
export LOG_LEVEL=INFO
export DATA_DIR=./data

# Optional: enable MAF workflow orchestration
# export USE_WORKFLOWS=true

# Run the server
python3 -m uvicorn src.api.main:app --host ${BACKEND_HOST} --port ${BACKEND_PORT} --reload
```

Backend API available at: http://127.0.0.1:8000/api/health

### 2. Start the Frontend

```bash
cd frontend

# Set environment variables (or use defaults)
export FRONTEND_HOST=127.0.0.1
export FRONTEND_PORT=3000
export BACKEND_BASE_URL=http://127.0.0.1:8000

# Build and run
cargo run
```

App available at: http://127.0.0.1:3000

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_HOST` | 127.0.0.1 | Backend listen address |
| `BACKEND_PORT` | 8000 | Backend listen port |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `DATA_DIR` | ./data | Data directory path |
| `USE_WORKFLOWS` | false | Enable MAF workflow orchestration |
| `FRONTEND_HOST` | 127.0.0.1 | Frontend listen address |
| `FRONTEND_PORT` | 3000 | Frontend listen port |
| `BACKEND_BASE_URL` | http://127.0.0.1:8000 | Backend URL for reverse proxy |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/ingest/symbols` | Ingest funds by symbol |
| POST | `/api/ingest/paste` | Ingest from pasted text |
| POST | `/api/ingest/upload` | Ingest from CSV/JSON file |
| POST | `/api/analyse` | Overlap + concentration analysis |
| POST | `/api/recommend` | Candidate scoring + recommendations |

### Example: Analyse Overlap

```bash
curl -X POST http://127.0.0.1:3000/api/analyse \
  -H "Content-Type: application/json" \
  -d '{"existing_funds": ["SPY", "QQQ", "VTI"]}'
```

### Example: Get Recommendations

```bash
curl -X POST http://127.0.0.1:3000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"existing_funds": ["SPY"], "candidate_funds": ["ARKK", "SCHD", "VXUS"]}'
```

## Available Stub Funds

| Symbol | Description | Overlap Profile |
|--------|-------------|-----------------|
| SPY | S&P 500 ETF | Broad US large-cap |
| QQQ | Nasdaq 100 | Heavy tech, high overlap with SPY |
| VTI | Total US Market | Moderate overlap with SPY |
| ARKK | ARK Innovation | Low overlap, high-growth |
| SCHD | Schwab Dividend | Low overlap, dividend-focused |
| VUG | Vanguard Growth | Moderate overlap with QQQ |
| VXUS | International | Minimal US overlap (stale data) |

## Running Tests

### Backend

```bash
cd backend
python3 -m pytest tests/ -v
```

77 tests covering:
- Parsing (symbols, paste, CSV, JSON)
- Normalisation (weights, deduplication)
- Overlap computation (unweighted, weighted, matrix)
- Concentration (portfolio-level, allocations)
- Scoring (all components, ranking)
- API integration (all endpoints)
- MAF workflows (orchestration, fallback)

## Scoring Algorithm

Candidates are scored 0–100:

| Component | Range | Description |
|-----------|-------|-------------|
| Overlap Reduction | 0–50 | Lower overlap with existing fund = higher score |
| Performance | 0–40 | Blended 1y/3y/5y returns |
| Data Quality Penalty | 0 to -20 | Penalty for stale data (>90 days) |
| Cost Penalty | 0 to -10 | Expense ratio (placeholder) |

## Project Structure

```
portfolio-analysis/
├── backend/
│   ├── src/
│   │   ├── api/          # FastAPI app, routes, Pydantic models
│   │   ├── core/         # Config, disclaimer
│   │   ├── data/         # Stub holdings data
│   │   ├── tools/        # Deterministic computation functions
│   │   └── workflows/    # MAF workflow orchestration
│   ├── tests/            # pytest test suite
│   └── requirements.txt
├── frontend/
│   ├── src/              # Rust/Leptos/Axum application
│   └── Cargo.toml
├── AGENTS.md             # System configuration spec
└── README.md
```

## License

This project is for demonstration purposes.
