# Backend Architecture

> For informational purposes only; not financial advice.

## 1. Overview

The backend is a Python FastAPI application that serves deterministic portfolio-analysis APIs. It ingests fund symbols or uploaded holdings data, normalises holdings, computes overlap/concentration/allocation/exposure/fee metrics, and ranks candidate funds with an explainable scoring model. Core calculations live in plain Python functions under `backend/src/tools/`; FastAPI and the optional Microsoft Agent Framework (MAF) workflow layer orchestrate those deterministic functions rather than replacing them.

Key characteristics:

- FastAPI HTTP API under `/api/*`
- Pydantic request/response models
- Deterministic analysis and scoring logic
- Optional MAF workflow execution via `USE_WORKFLOWS=true`
- Stub data source for holdings, performance, timestamps, and metadata
- Every main response includes the disclaimer and an ISO 8601 UTC timestamp

## 2. Project Structure

```text
backend/
├── pyproject.toml                 # Python package metadata; requires Python >=3.11; pytest config
├── requirements.txt              # Runtime and test dependencies
├── data/                         # Default local data directory (from DATA_DIR)
├── src/
│   ├── __init__.py
│   ├── api/
│   │   ├── main.py               # FastAPI app creation and router registration
│   │   ├── models/
│   │   │   ├── analysis.py       # Analyse request/response schemas
│   │   │   ├── debug.py          # DebugInfo and AgentCallRecord schemas
│   │   │   ├── ingest.py         # Ingestion request/response schemas and Holding/FundInput
│   │   │   └── recommendation.py # Recommendation request/response schemas
│   │   └── routes/
│   │       ├── analyse.py        # /api/analyse route; overlap, concentration, quality, allocation, sectors, fees
│   │       ├── health.py         # /api/health route
│   │       ├── ingest.py         # /api/ingest/* routes for symbols, paste, upload
│   │       └── recommend.py      # /api/recommend route; candidate scoring
│   ├── core/
│   │   ├── config.py             # Environment-driven settings object
│   │   └── disclaimer.py         # Shared disclaimer constant
│   ├── data/
│   │   └── stub_holdings.py      # Stub funds, holdings metadata, performance, timestamps, fund metadata
│   ├── tools/
│   │   ├── parsing.py            # parse_symbols/parse_paste/parse_csv/parse_json
│   │   ├── normalise.py          # Deduplication and weight normalisation
│   │   ├── overlap.py            # Pairwise and matrix overlap calculations
│   │   ├── concentration.py      # Portfolio concentration aggregation
│   │   ├── scoring.py            # Candidate scoring and explanation generation
│   │   ├── asset_allocation.py   # Asset-class breakdowns
│   │   ├── sector_exposure.py    # Sector breakdowns
│   │   └── fees.py               # Expense-ratio lookup and fee analysis
│   └── workflows/
│       ├── analysis_workflow.py  # Optional workflow wrapper around analysis pipeline
│       └── recommendation_workflow.py # Optional workflow wrapper around recommendation pipeline
└── tests/
    ├── conftest.py               # Shared pytest fixtures
    ├── test_api.py               # API integration tests
    ├── test_parsing.py           # Parsing-tool tests
    ├── test_normalise.py         # Holdings normalisation tests
    ├── test_overlap.py           # Overlap calculations tests
    ├── test_concentration.py     # Concentration tests
    ├── test_asset_allocation.py  # Asset allocation tests
    ├── test_sector_exposure.py   # Sector exposure tests
    ├── test_fees.py              # Fee-analysis tests
    ├── test_scoring.py           # Recommendation scoring tests
    └── test_workflows.py         # Workflow execution/fallback tests
```

## 3. Configuration

`backend/src/core/config.py` defines a lightweight `Settings` class that reads configuration from environment variables only.

| Variable | Default | Used for |
|---|---:|---|
| `BACKEND_HOST` | `127.0.0.1` | Host/interface for the FastAPI server |
| `BACKEND_PORT` | `8000` | Port for the FastAPI server |
| `LOG_LEVEL` | `INFO` | Logging level used by `logging.basicConfig(...)` in `src/api/main.py` |
| `DATA_DIR` | `./data` | Data directory path reserved for local backend data |
| `AUTH_ENABLED` | `false` | Boolean feature flag reserved for future authentication support |
| `CACHE_ENABLED` | `false` | Boolean feature flag reserved for future caching support |
| `USE_WORKFLOWS` | `false` | Enables the optional workflow layer for analyse/recommend routes |

Boolean parsing is strict string comparison against `"true"` after lowercasing.

Example:

```bash
cd backend
export BACKEND_HOST=127.0.0.1
export BACKEND_PORT=8000
export LOG_LEVEL=INFO
export DATA_DIR=./data
export AUTH_ENABLED=false
export CACHE_ENABLED=false
export USE_WORKFLOWS=false
uvicorn src.api.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT"
```

## 4. API Endpoints

All examples below target `http://127.0.0.1:3000`, which is the frontend/Axum origin that reverse-proxies `/api/*` to FastAPI.

### GET `/api/health`

- **Purpose:** Liveness check
- **Request body:** None
- **Response body:**
  - `status: str` — currently `"ok"`
  - `timestamp: str` — ISO 8601 UTC timestamp

Example:

```bash
curl http://127.0.0.1:3000/api/health
```

### POST `/api/ingest/symbols`

- **Purpose:** Resolve a list of fund symbols into `FundInput` objects using stub data
- **Request model:** `SymbolsRequest`
  - `symbols: list[str]` — required, minimum length 1
- **Response model:** `IngestResponse`
  - `funds: list[FundInput]`
  - `warnings: list[str]`
  - `disclaimer: str`
  - `timestamp: str`

Example:

```bash
curl -X POST http://127.0.0.1:3000/api/ingest/symbols \
  -H 'Content-Type: application/json' \
  -d '{"symbols":["SPY","QQQ","VTI"]}'
```

### POST `/api/ingest/paste`

- **Purpose:** Parse pasted symbols from lines, commas, or tabs
- **Request model:** `PasteRequest`
  - `text: str` — required, minimum length 1
- **Response model:** `IngestResponse`
  - `funds: list[FundInput]`
  - `warnings: list[str]`
  - `disclaimer: str`
  - `timestamp: str`

Example:

```bash
curl -X POST http://127.0.0.1:3000/api/ingest/paste \
  -H 'Content-Type: application/json' \
  -d '{"text":"SPY, QQQ\nVTI\nSCHD"}'
```

### POST `/api/ingest/upload`

- **Purpose:** Parse uploaded CSV or JSON content
- **Request body:** multipart form data
  - `file` — required uploaded file
- **Accepted formats:**
  - JSON arrays of symbols or fund objects
  - JSON object with `symbols` or `funds`
  - CSV symbol list
  - CSV detailed holdings rows with `fund_symbol`/`fund`/`symbol`, `ticker`, `weight`
- **Response model:** `IngestResponse`
  - `funds: list[FundInput]`
  - `warnings: list[str]`
  - `disclaimer: str`
  - `timestamp: str`

Example:

```bash
curl -X POST http://127.0.0.1:3000/api/ingest/upload \
  -F 'file=@holdings.csv'
```

### POST `/api/analyse`

- **Purpose:** Analyse an existing portfolio
- **Query params:**
  - `debug: bool` — optional (default `false`). When `true`, the response includes a `debug_info` object.
- **Request model:** `AnalyseRequest`
  - `existing_funds: list[str]` — required, minimum length 1
  - `allocations: list[float] | null` — optional portfolio allocations; equal weighting is used if missing or length mismatches
- **Response model:** `AnalysisResponse`
  - `overlap_matrix` — fund order plus unweighted/weighted matrices
  - `concentration` — top holdings, ticker count, top-10 weight
  - `top_overlaps` — ranked pairwise overlaps
  - `data_quality` — freshness and holdings count per fund
  - `asset_allocation` — portfolio and per-fund asset-class weights
  - `sector_exposure` — portfolio and per-fund sector weights
  - `fee_analysis` — per-fund ERs and portfolio weighted ER
  - `disclaimer: str`
  - `timestamp: str`
  - `debug_info: DebugInfo | null` — present only when `?debug=true`

If `USE_WORKFLOWS=true`, the route first tries the workflow implementation and falls back to direct tool execution on error.

Example:

```bash
curl -X POST http://127.0.0.1:3000/api/analyse \
  -H 'Content-Type: application/json' \
  -d '{"existing_funds":["SPY","QQQ","VTI"],"allocations":[0.5,0.3,0.2]}'
```

### POST `/api/recommend`

- **Purpose:** Score candidate replacement funds for each existing fund
- **Query params:**
  - `debug: bool` — optional (default `false`). When `true`, the response includes a `debug_info` object.
- **Request model:** `RecommendRequest`
  - `existing_funds: list[str]` — required, minimum length 1
  - `candidate_funds: list[str]` — required, minimum length 1
  - `allocations: list[float] | null` — present on the model for future use; not consumed by the current scoring path
- **Response model:** `RecommendResponse`
  - `recommendations: dict[str, list[ScoredCandidate]]`
  - `disclaimer: str`
  - `timestamp: str`
  - `debug_info: DebugInfo | null` — present only when `?debug=true`
- **Per candidate fields:**
  - `symbol: str`
  - `total_score: float`
  - `breakdown.overlap_reduction: float`
  - `breakdown.performance: float`
  - `breakdown.data_quality_penalty: float`
  - `breakdown.cost_penalty: float`
  - `explanation: str`

Like `/api/analyse`, this route can execute through the optional workflow layer and falls back to direct tools if workflow execution fails.

Example:

```bash
curl -X POST http://127.0.0.1:3000/api/recommend \
  -H 'Content-Type: application/json' \
  -d '{"existing_funds":["SPY"],"candidate_funds":["ARKK","SCHD","VXUS"]}'
```

### Debug info schema (`DebugInfo`)

Returned in `debug_info` when `?debug=true`:

| Field | Type | Description |
|-------|------|-------------|
| `execution_mode` | `string` | Which mode ran (`direct`, `workflow`, `agent_local`, `agent_distributed`) |
| `agents_called` | `AgentCallRecord[]` | Remote agent invocations (empty in `direct` mode) |
| `fallback_used` | `bool` | Whether the route fell back to direct execution |
| `fallback_reason` | `string \| null` | Error that triggered fallback |
| `total_latency_ms` | `float \| null` | Total request processing time in milliseconds |

Each `AgentCallRecord`:

| Field | Type | Description |
|-------|------|-------------|
| `agent_name` | `string` | Agent name (e.g. `analysis-agent`) |
| `url` | `string` | Full invocations protocol URL |
| `status_code` | `int \| null` | HTTP status from the agent |
| `latency_ms` | `float \| null` | Round-trip time in milliseconds |
| `error` | `string \| null` | Error message if the call failed |

## 5. Deterministic Tools

### 5.1 `parsing.py`

#### `parse_symbols(symbols: list[str]) -> tuple[list[FundInput], list[str]]`
- Normalises each symbol with `strip().upper()`
- Looks up holdings from `STUB_HOLDINGS`
- Returns empty holdings plus a warning when a symbol is unknown

#### `parse_paste(text: str) -> tuple[list[FundInput], list[str]]`
- Parses pasted text split by lines, commas, or tabs
- Ignores blank lines and comment lines starting with `#`
- Filters tokens with regex `^[A-Z0-9.]+$`
- Delegates symbol resolution to `parse_symbols`

#### `parse_csv(content: bytes) -> tuple[list[FundInput], list[str]]`
- Decodes UTF-8 CSV content
- Supports:
  - simple symbol list CSV
  - detailed holdings CSV with `ticker` and `weight`, plus a fund column such as `fund_symbol`, `fund`, or `symbol`
- Invalid weight values add warnings and skip the bad row

#### `parse_json(content: bytes) -> tuple[list[FundInput], list[str]]`
- Decodes JSON and supports:
  - `[`symbol strings`]`
  - `[`fund objects`]`
  - `{"symbols": [...]}`
  - `{"funds": [...]}`
- For object entries without holdings, it falls back to stub-symbol lookup
- Returns `([], ["Unrecognized JSON format"])` for unsupported shapes

### 5.2 `normalise.py`

#### `normalise_holdings(funds: list[FundInput]) -> list[NormalisedFund]`
- Converts each `FundInput` into `NormalisedFund(symbol: str, holdings: dict[str, float])`
- Deduplicates repeated tickers by summing weights
- Uppercases ticker symbols
- Normalises merged weights so each fund sums to `1.0` when total weight is positive
- Preserves empty-holdings funds as empty dictionaries

### 5.3 `overlap.py`

#### `compute_overlap(fund_a: NormalisedFund, fund_b: NormalisedFund) -> OverlapResult`
- Returns `OverlapResult(fund_a, fund_b, unweighted, weighted, shared_tickers)`
- Algorithms:
  - `shared = intersection(A, B)`
  - `unweighted = len(shared) / min(len(A), len(B))`
  - `weighted = sum(min(wA[t], wB[t]) for t in shared)`
- If either fund has zero holdings, unweighted overlap is `0.0`
- `shared_tickers` is sorted; scores are rounded to 4 decimals

#### `compute_overlap_matrix(funds: list[NormalisedFund]) -> tuple[list[str], list[list[float]], list[list[float]]]`
- Returns fund symbols plus symmetric unweighted and weighted matrices
- Diagonal values are set to `1.0`
- Each off-diagonal cell is filled from `compute_overlap(...)`

### 5.4 `concentration.py`

#### `compute_concentration(funds: list[NormalisedFund], allocations: list[float] | None = None) -> ConcentrationResult`
- Returns `ConcentrationResult(top_holdings, total_tickers, top_10_weight)`
- Formula:
  - `portfolio_weight[ticker] = sum(allocation_i * holding_weight_ij)`
- Uses equal weights when allocations are missing, mismatched, or sum to `0`
- Returns the top 25 holdings, total ticker count, and the aggregate weight of the top 10 holdings

### 5.5 `scoring.py`

#### `score_candidates(existing: NormalisedFund, candidates: list[NormalisedFund]) -> list[ScoredCandidate]`
- Returns sorted `ScoredCandidate` objects with:
  - `symbol`
  - `breakdown: ScoreBreakdown`
  - `explanation`
  - computed property `total_score`
- `total_score` is clipped at a minimum of `0.0`
- Sort order is descending by total score

Internal scoring helpers:

- `_compute_overlap_reduction_score(existing, candidate) -> float`
- `_compute_performance_score(symbol) -> float`
- `_compute_data_quality_penalty(symbol) -> float`
- `_compute_cost_penalty(symbol) -> float`

### 5.6 `asset_allocation.py`

#### `compute_asset_allocation(funds: list[NormalisedFund], allocations: list[float] | None = None) -> AssetAllocationResult`
- Returns `AssetAllocationResult(allocation, per_fund)`
- Uses `STUB_FUND_METADATA[symbol]["asset_class_mix"]` when available
- Otherwise derives asset classes from `STUB_HOLDING_METADATA[ticker]["asset_class"]`
- Unclassified remainder is assigned to `"Other"`
- Aggregates to portfolio level using normalised fund allocations

### 5.7 `sector_exposure.py`

#### `compute_sector_exposure(funds: list[NormalisedFund], allocations: list[float] | None = None) -> SectorExposureResult`
- Returns `SectorExposureResult(exposure, per_fund)`
- Maps each ticker to `STUB_HOLDING_METADATA[ticker]["sector"]`
- Missing metadata is classified as `"Unknown"`
- Aggregates per fund, then to portfolio level using fund allocations

### 5.8 `fees.py`

#### `compute_fee_analysis(funds: list[NormalisedFund], allocations: list[float] | None = None) -> FeeAnalysisResult`
- Returns:
  - `per_fund: dict[str, float | None]`
  - `portfolio_weighted_er: float`
  - `estimated_annual_cost_per_10k: float`
- Expense ratios come from `STUB_FUND_METADATA[symbol]["expense_ratio"]`
- Portfolio weighted ER uses normalised fund allocations
- Annual cost is `weighted_er * 10000`, rounded to 2 decimals

#### `get_expense_ratio(symbol: str) -> float | None`
- Helper used by scoring
- Returns the fund expense ratio or `None`

## 6. Scoring Algorithm

Candidate scoring is implemented entirely in `backend/src/tools/scoring.py`.

### Total score

```text
total = overlap_reduction + performance + data_quality_penalty + cost_penalty
final_score = max(0.0, total)
```

### OverlapReduction (0–50)
- Computed from weighted overlap with the existing fund
- Formula:

```text
overlap_reduction = (1 - weighted_overlap) * 50
```

- A candidate with `0.00` weighted overlap gets `50`
- A candidate with `1.00` weighted overlap gets `0`

### Performance (0–40)
- Uses `STUB_PERFORMANCE[symbol]`
- Blends trailing returns with weights:
  - 1y: 40%
  - 3y: 35%
  - 5y: 25%
- Each return is normalized from an assumed range of `-30%` to `+30%`

```text
normalize(r) = clamp((r + 0.3) / 0.6, 0, 1)
performance = (
  normalize(1y) * 0.40 +
  normalize(3y) * 0.35 +
  normalize(5y) * 0.25
) * 40
```

- Missing return values are treated as neutral (`0.5` after normalization)
- Missing entire performance records yield `0`

### DataQualityPenalty (0 to -20)
- Uses `STUB_DATA_TIMESTAMPS[symbol]`
- If no timestamp exists or parsing fails: `-20`
- If data age is `<= 90` days: `0`
- If age is `91–180` days: linear penalty from `0` to `-20`
- If age is `> 180` days: `-20`

```text
penalty = -20 * (age_days - 90) / 90
```

### CostPenalty (0 to -10)
- Uses `get_expense_ratio(symbol)`
- `None`/unknown expense ratio => `-5`
- `0.00%` ER => `0`
- `1.00%` ER or higher => `-10`
- Linear in between:

```text
cost_penalty = -min(10, expense_ratio / 0.01 * 10)
```

### Explanation generation
Each `ScoredCandidate` includes a plain-language explanation string summarising:
- total score
- overlap-reduction component
- performance component
- optional data-quality penalty note
- optional cost-penalty note with the expense ratio if known

## 7. Pydantic Models

### Ingestion models (`api/models/ingest.py`)
- `Holding`
  - `ticker: str`
  - `weight: float` (`0.0 <= weight <= 1.0`)
- `FundInput`
  - `symbol: str`
  - `holdings: list[Holding] = []`
- `SymbolsRequest`
  - `symbols: list[str]` with `min_length=1`
- `PasteRequest`
  - `text: str` with `min_length=1`
- `IngestResponse`
  - `funds: list[FundInput]`
  - `warnings: list[str]`
  - `disclaimer: str`
  - `timestamp: str`

### Analysis models (`api/models/analysis.py`)
- `AnalyseRequest`
  - `existing_funds: list[str]` with `min_length=1`
  - `allocations: list[float] | None`
- `OverlapPair`
  - `fund_a`, `fund_b`, `unweighted`, `weighted`, `shared_tickers`
- `OverlapMatrix`
  - `funds`, `unweighted`, `weighted`
- `ConcentrationEntry`
  - `ticker`, `weight`
- `ConcentrationResult`
  - `top_holdings`, `total_tickers`, `top_10_weight`
- `DataQualityEntry`
  - `symbol`, `last_updated`, `is_stale`, `holdings_count`
- `AssetAllocationEntry`
  - `asset_class`, `weight`
- `AssetAllocationResult`
  - `portfolio`, `per_fund`
- `SectorExposureEntry`
  - `sector`, `weight`
- `SectorExposureResult`
  - `portfolio`, `per_fund`
- `FeeAnalysisEntry`
  - `symbol`, `expense_ratio`, `expense_ratio_pct`
- `FeeAnalysisResult`
  - `per_fund`, `portfolio_weighted_er`, `portfolio_weighted_er_pct`, `estimated_annual_cost_per_10k`
- `AnalysisResponse`
  - `overlap_matrix`, `concentration`, `top_overlaps`, `data_quality`, `asset_allocation`, `sector_exposure`, `fee_analysis`, `disclaimer`, `timestamp`

### Recommendation models (`api/models/recommendation.py`)
- `ScoreBreakdown`
  - `overlap_reduction: float` (`0–50`)
  - `performance: float` (`0–40`)
  - `data_quality_penalty: float` (`-20–0`)
  - `cost_penalty: float` (`-10–0`)
- `ScoredCandidate`
  - `symbol`, `total_score`, `breakdown`, `explanation`
- `RecommendRequest`
  - `existing_funds: list[str]` with `min_length=1`
  - `candidate_funds: list[str]` with `min_length=1`
  - `allocations: list[float] | None`
- `RecommendResponse`
  - `recommendations`, `disclaimer`, `timestamp`

## 8. Stub Data

`backend/src/data/stub_holdings.py` is the single in-repo stub data source. The file explicitly states that the holdings and performance values are fabricated for development/testing.

### Structures

- `STUB_HOLDINGS: dict[str, dict[str, float]]`
  - maps fund symbol -> `{ticker: holding_weight}`
  - used by ingestion, analysis, and recommendation routes
- `STUB_HOLDING_METADATA: dict[str, dict[str, str]]`
  - maps ticker -> metadata such as `sector`, `asset_class`, `country`
  - used by sector and asset allocation tools
- `STUB_FUND_METADATA: dict[str, dict]`
  - maps fund symbol -> fund metadata such as:
    - `expense_ratio`
    - `asset_class_mix`
- `STUB_PERFORMANCE: dict[str, dict[str, float | None]]`
  - maps fund symbol -> trailing return data for `1y`, `3y`, `5y`
- `STUB_DATA_TIMESTAMPS: dict[str, str]`
  - maps fund symbol -> ISO 8601 freshness timestamp

### Available stub fund symbols

- `SPY`
- `QQQ`
- `VTI`
- `ARKK`
- `SCHD`
- `VUG`
- `VXUS`

Notes:
- `VXUS` is intentionally stale in `STUB_DATA_TIMESTAMPS` (`2026-01-15T00:00:00Z`) to exercise data-quality penalties.
- Fund metadata currently includes expense ratios and asset-class mixes for all seven stub funds.

### How to add a new fund

To add another stub fund consistently:

1. Add its holdings to `STUB_HOLDINGS`
2. Add any new underlying tickers to `STUB_HOLDING_METADATA` with at least sector and asset class
3. Add `expense_ratio` and optionally `asset_class_mix` to `STUB_FUND_METADATA`
4. Add `1y`/`3y`/`5y` entries to `STUB_PERFORMANCE`
5. Add an ISO timestamp to `STUB_DATA_TIMESTAMPS`
6. Add or update tests if the new fund changes expected fixtures or ranking behavior

If a symbol exists in requests but not in `STUB_HOLDINGS`, ingestion returns an empty-holdings `FundInput` plus a warning.

## 9. Testing

Backend tests are pytest-based.

### How to run

```bash
cd backend
pytest
```

### Current status

- `98` tests collected
- `98` tests passed in the current codebase during documentation work

### Coverage areas

- `test_api.py` — endpoint behavior, payload shapes, data quality, recommendation breakdowns
- `test_parsing.py` — symbols, pasted text, CSV, JSON parsing formats
- `test_normalise.py` — ticker deduplication and weight normalization
- `test_overlap.py` — pairwise and matrix overlap logic
- `test_concentration.py` — portfolio aggregation logic
- `test_asset_allocation.py` — asset class aggregation and fallbacks
- `test_sector_exposure.py` — sector mapping and aggregation
- `test_fees.py` — expense ratio and weighted-fee calculations
- `test_scoring.py` — score components and ranking order
- `test_workflows.py` — async workflow execution plus direct fallback behavior

`pyproject.toml` also sets:
- `requires-python = ">=3.11"`
- `pytest` test path = `tests`
- `asyncio_mode = "auto"`

## 10. Dependencies

Dependencies from `backend/requirements.txt`:

| Package | Purpose |
|---|---|
| `fastapi>=0.115.0` | Web framework for the API routes and request/response handling |
| `uvicorn>=0.30.0` | ASGI server used to run the FastAPI app |
| `pydantic>=2.0.0` | Data validation and serialization for API models |
| `python-multipart>=0.0.9` | Required by FastAPI for `UploadFile` / multipart form uploads |
| `agent-framework` | Optional Microsoft Agent Framework integration for workflow orchestration |
| `pytest>=8.0.0` | Test runner |
| `pytest-asyncio>=0.23.0` | Async test support for FastAPI/workflow tests |
| `httpx>=0.27.0` | Async HTTP client used in API integration tests |

## Additional implementation notes

- `src/api/main.py` creates the FastAPI app with title `Portfolio Overlap & Fund Analyzer` and version `0.1.0`.
- `src/core/disclaimer.py` centralizes the shared disclaimer string: `For informational purposes only; not financial advice.`
- `src/api/routes/analyse.py` and `src/api/routes/recommend.py` both support an optional workflow path and direct-tool fallback path.
- The backend does not make external market-data calls; it operates entirely on in-repo stub data and deterministic calculations.
