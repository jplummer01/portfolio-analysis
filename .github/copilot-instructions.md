# copilot-instructions.md

# Copilot Instructions — Fund Overlap + Switch Candidate Analyzer
# Frontend: Rust Leptos (SSR) + Axum
# Backend: Python FastAPI + Microsoft Agent Framework (MAF)
# Deployment Mode: Single origin (Axum is entrypoint, /api proxied)

You are an expert full-stack engineer. Build a web application with:

- Rust Leptos SSR app rendered via Axum
- Python FastAPI backend using Microsoft Agent Framework (MAF) for multi-agent orchestration
- Single-origin architecture (Axum proxies /api to backend)
- No authentication (yet), but architecture must allow adding it later

---

## SAFETY REQUIREMENTS (MANDATORY)
- Do NOT provide financial advice
- Do NOT use directive language (buy/sell/switch)
- Always include disclaimer:
  "For informational purposes only; not financial advice."
- Never fabricate data
- Always include explainable reasoning + data quality summary

---

## CORE FUNCTIONALITY

### Inputs
- existing_funds: list[str]
- available_funds: list[str]
- optional allocations
- ingestion via:
  1) manual symbols
  2) pasted data
  3) CSV/JSON upload
  4) provider interface (offline + stub)

---

## OUTPUTS

### Existing Portfolio Analysis
- overlap matrix (unweighted + weighted)
- portfolio concentration
- top overlapping tickers

### Candidate Universe Analysis
- holdings availability
- 1y / 3y / 5y performance availability
- stale data detection ( >90 days )

### Recommendation Results
- ranked candidates per existing fund
- scoring breakdown
- explanation per candidate
- optional portfolio-level replacement mode

---

## BACKEND (PYTHON + MAF)

### Agents

PortfolioOrchestratorAgent:
- coordinates workflow
- enforces rules

ExistingPortfolioAnalysisAgent:
- computes overlap + concentration

CandidateUniverseAnalysisAgent:
- evaluates candidates + data quality

RecommendationAgent:
- ranks candidates

---

### Orchestration

Use MAF workflow patterns:
- HandoffBuilder for orchestration
- ConcurrentBuilder for parallel analysis
- Sequential flow into Recommendation

---

### Tools (Deterministic ONLY)

- parse_symbols_tool
- parse_paste_tool
- parse_csv_tool
- parse_json_tool
- normalise_holdings_tool
- compute_overlap_tool
- compute_concentration_tool
- score_candidates_tool

All logic MUST exist in deterministic functions, not LLM reasoning.

---

## ALGORITHMS

### Overlap
shared = intersection(A, B)
unweighted = len(shared) / min(len(A), len(B))
weighted = sum(min(wA, wB))

### Portfolio concentration
sum(allocation * holding weight)

---

### Scoring (0–100)
- OverlapReduction: 0–50
- Performance: 0–40
- DataQualityPenalty: 0 to -20
- CostPenalty: 0 to -10 (optional)

Must include component breakdown.

---

## BACKEND API (FastAPI)

Routes:
- POST /api/ingest/symbols
- POST /api/ingest/paste
- POST /api/ingest/upload
- POST /api/analyse
- POST /api/recommend
- GET /api/health

---

## FRONTEND (LEPTOS + AXUM)

Pages:
- Ingest
- Analyse
- Recommend

UI MUST show:
- disclaimer
- timestamps
- data quality
- scoring breakdown

---

## AXUM SERVER REQUIREMENTS

- Serve SSR + WASM
- Reverse proxy /api/* → backend
- Same-origin (no CORS)

---

## ENVIRONMENT CONFIG ONLY (NO HARDCODING)

Use env vars for:
- ports
- API URLs
- config

---

## ENGINEERING RULES

- Use Pydantic models (backend)
- Use strong Rust typing (frontend)
- Keep logic modular
- Prefer clarity over complexity
- Never fabricate data
