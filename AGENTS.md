# AGENTS.md — Portfolio Overlap & Fund Analyzer

## PURPOSE
Defines how the system is run, configured, and validated.

---

## ARCHITECTURE

Two services:

Frontend:
- Rust
- Leptos SSR
- Axum server
- Public entrypoint

Backend:
- Python
- FastAPI
- Microsoft Agent Framework

Browser sees one origin only.

---

## ENVIRONMENT VARIABLES ONLY (MANDATORY)

### Frontend

- FRONTEND_HOST (default: 127.0.0.1)
- FRONTEND_PORT (default: 3000)
- BACKEND_BASE_URL (default: http://127.0.0.1:8000)

### Backend

- BACKEND_HOST (default: 127.0.0.1)
- BACKEND_PORT (default: 8000)
- LOG_LEVEL (default: INFO)
- DATA_DIR (default: ./data)

Optional:
- AUTH_ENABLED
- CACHE_ENABLED

### Portfolio Assistant Agent

- AZURE_AI_MODEL_DEPLOYMENT_NAME (required for portfolio-assistant agent)
- FOUNDRY_PROJECT_ENDPOINT (auto-injected in hosted containers)

NO HARD-CODED VALUES ALLOWED

---

## LOCAL RUN INSTRUCTIONS

### Start Backend

cd backend

export BACKEND_HOST=127.0.0.1
export BACKEND_PORT=8000

pip install -r requirements.txt

uvicorn src.api.main:app \
  --host ${BACKEND_HOST} \
  --port ${BACKEND_PORT} \
  --reload

API:
http://127.0.0.1:8000/api

---

### Start Frontend

cd frontend

export FRONTEND_HOST=127.0.0.1
export FRONTEND_PORT=3000
export BACKEND_BASE_URL=http://127.0.0.1:8000

cargo run

App:
http://127.0.0.1:3000

---

## REVERSE PROXY REQUIREMENT (CRITICAL)

Axum MUST proxy:

/api/* → ${BACKEND_BASE_URL}/api/*

Must preserve:
- request method
- headers
- body

Must NOT:
- expose backend directly
- modify payload
- require CORS

---

## DEVELOPMENT EXPECTATIONS

### Backend

- FastAPI with Pydantic
- deterministic functions only for calculations
- MAF used only for orchestration

---

### Frontend

- Leptos SSR
- Axum routing
- All API calls under /api

---

## VALIDATION CHECKLIST

System:
- backend runs independently
- frontend runs independently
- proxy works

Functional:
- ingestion works (manual, paste, upload)
- analysis runs
- recommendations returned

Output:
- disclaimer present
- data quality shown
- explanations included

---

## TESTING

### Backend

pytest

Must test:
- overlap calculations
- scoring
- parsing
- normalisation

No external network calls.

---

### Frontend

- SSR renders correctly
- API integration works
- handles error states

---

## EXTENSIBILITY (DO NOT IMPLEMENT YET)

Prepare for:
- authentication
- caching
- background jobs
- external providers

---

## STRICT RULES

- no financial advice
- no invented data
- no hardcoded config
- must include explanation
- must include disclaimer

---

## DEFINITION OF DONE

- both services run with env vars
- proxy works
- UI renders correctly
- API responds correctly
- tests pass
- output includes explanation + disclaimer
