# Portfolio Analysis — Documentation

> For informational purposes only; not financial advice.

## Overview

Portfolio Analysis is a Portfolio Overlap & Fund Switch Candidate Analyzer inspired by tools such as Morningstar's Portfolio X-Ray. It helps users inspect ETF and mutual fund combinations by measuring holdings overlap, computing asset allocation and sector exposure, evaluating fee data, and identifying potential switch candidates with explainable scoring outputs.

The system uses a two-service architecture. A Rust frontend built with Leptos SSR and Axum serves the user interface, while a Python backend built with FastAPI handles ingestion, analysis, and recommendation APIs. This separation keeps presentation concerns and deterministic portfolio calculations modular while allowing each service to evolve independently.

The application is designed as a single-origin system: the browser communicates with the Axum frontend, and `/api/*` requests are reverse-proxied to the FastAPI backend. For teams that want workflow-based coordination, Microsoft Agent Framework (MAF) orchestration can be enabled as an optional layer for analysis and recommendation pipelines without changing the core deterministic logic.

## Table of Contents

1. **[Backend Architecture](backend.md)** — FastAPI server, API endpoints, deterministic tools (parsing, overlap, scoring, asset allocation, sector exposure, fees), Pydantic models, stub data, and testing
2. **[Frontend Architecture](frontend.md)** — Rust/Leptos SSR application, Axum server, reverse proxy configuration, page descriptions (Ingest, Analyse, Recommend), and Rust models
3. **[Multi-Agent Orchestration](multi-agent-orchestration.md)** — Microsoft Agent Framework (MAF) deep-dive: @workflow/@step decorators, analysis and recommendation pipelines, asyncio.gather parallelism, fallback strategy, and design decisions
4. **[Agent Orchestration Architecture](agent-orchestration.md)** — MAF v1.0 orchestrator/sub-agent architecture, execution modes, shared service delegation, Foundry deployment assets, and testing guidance
5. **[Azure Deployment Guide — `azd up`](azd-deployment.md)** — Azure Container Apps + Microsoft Foundry hosted-agent deployment, environment variables, provisioning flow, verification steps, monitoring, troubleshooting, cleanup, and cost notes

### Hosted Agent Reference

6. **[Analysis Agent](analysis-agent.md)** — Existing portfolio analysis agent: overlap matrices, concentration, data quality, asset allocation, sector exposure, and fee analysis
7. **[Candidate Agent](candidate-agent.md)** — Candidate universe evaluation agent: holdings normalisation and data quality checks
8. **[Recommendation Agent](recommendation-agent.md)** — Deterministic candidate scoring agent: 0–100 composite scoring with overlap reduction, performance, data quality, and cost components

## Quick Links

- Getting started → see [README.md](../README.md)
- System specification → see [AGENTS.md](../AGENTS.md)
- API health check → `curl http://127.0.0.1:3000/api/health`

## Architecture Diagram

```text
Browser
  │
  ▼
┌─────────────────────────────┐
│  Frontend (Axum :3000)      │
│  ├── / → Leptos SSR pages   │
│  └── /api/* → reverse proxy │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  Backend (FastAPI :8000)    │
│  ├── Routes (analyse,       │
│  │   recommend, ingest)     │
│  ├── Tools (deterministic)  │
│  └── Workflows (MAF, opt-in)│
└─────────────────────────────┘
```
