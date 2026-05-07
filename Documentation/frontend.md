# Frontend Architecture

> For informational purposes only; not financial advice.

## 1. Overview

The frontend is a Rust server application built with Leptos SSR and served by Axum. It renders the Ingest, Analyse, and Recommend pages on the server and keeps the browser on a single origin.

In practice, the browser talks only to the frontend on port `3000`. Axum serves HTML for page routes and exposes a same-origin `/api/*` reverse proxy that forwards requests to the backend on port `8000`. This avoids CORS complexity and keeps backend details behind the frontend boundary.

## 2. Technology Stack

- **Rust (stable toolchain)** — application language for the frontend server
- **Leptos (SSR)** — page rendering and UI composition
- **Axum** — HTTP server, routing, form handling, multipart upload handling
- **reqwest** — outbound HTTP client used for backend JSON calls and `/api/*` reverse proxying
- **serde / serde_json** — request and response serialization
- **tokio** — async runtime

### Why SSR was chosen over CSR

The current implementation is strongly SSR-oriented:

- Axum returns fully rendered HTML for `/`, `/analyse`, and `/recommend`
- forms submit to Axum handlers and the server rerenders the page with results
- `Cargo.toml` contains server-side dependencies only; there is no separate CSR bundle or browser-side fetch/hydration setup
- same-origin integration is simpler because Axum can validate form input, call the backend, and render the response in one place

This keeps the frontend small, predictable, and easy to extend without adding a client-side application runtime.

## 3. Project Structure

```text
frontend/
├── Cargo.toml              # Rust package manifest and server/runtime dependencies
└── src/
    ├── app.rs              # Leptos page layout, SSR rendering, page components, result sections, styling
    ├── main.rs             # Axum server, routes, form handlers, backend client helpers, /api reverse proxy
    ├── models.rs           # Rust structs for backend payloads and responses
    └── parsing.rs          # Input normalization helpers for symbols and optional allocations
```

## 4. Architecture

### Single-Origin Design

The frontend uses a same-origin flow:

```text
Browser
  ├── GET /, /analyse, /recommend ──> Axum frontend (:3000) ──> SSR HTML
  └── /api/* -----------------------> Axum frontend (:3000) ──> FastAPI backend (:8000)
```

Key points:

- Axum is the public entrypoint
- the backend base URL is internal to the frontend configuration
- the browser never needs to call the backend origin directly
- no CORS configuration is required because API access stays on the frontend origin

The frontend also has page-specific POST handlers:

- `POST /ingest/symbols`
- `POST /ingest/paste`
- `POST /ingest/upload`
- `POST /analyse`
- `POST /recommend`

These handlers receive standard HTML form submissions, call the backend with `reqwest`, and then rerender the page server-side with the returned data.

### Reverse Proxy

`main.rs` defines a catch-all proxy route:

- `ANY /api/{*path}` → `proxy_api`

How proxying works:

1. Build the target URL from `BACKEND_BASE_URL` plus the original path and query string
2. Read the incoming body (up to `10 MiB`)
3. Forward the original HTTP method
4. Copy request headers, excluding `Host` and `Content-Length`
5. Send the request with `reqwest`
6. Copy the backend status code and response body back to the browser
7. Copy response headers, excluding `Transfer-Encoding`, `Content-Length`, and `Connection`

This preserves the request shape closely while letting Axum remain the only browser-visible server.

## 5. Pages

### Ingest Page

The Ingest page is rendered by `render_ingest_page()` and `IngestPage`.

What it shows:

- a **Symbols** form for comma- or newline-separated fund symbols
- a **Paste data** form for pasted exports or raw symbol text
- an **Upload CSV or JSON** form for multipart file uploads
- an **Ingestion results** panel

Symbols flow:

1. User submits the Symbols form to `POST /ingest/symbols`
2. `main.rs` normalizes the input with `split_symbols()`
3. Empty submissions are rejected locally
4. Axum sends `SymbolsPayload { symbols }` to backend `POST /api/ingest/symbols`
5. The page rerenders with:
   - returned funds
   - warning messages
   - timestamp
   - disclaimer
   - holdings preview for each fund

Other ingestion flows:

- `POST /ingest/paste` forwards `PastePayload` to `POST /api/ingest/paste`
- `POST /ingest/upload` forwards multipart file data to `POST /api/ingest/upload`

### Analyse Page

The Analyse page is rendered by `render_analyse_page()` and `AnalysePage`.

What it shows:

- request form for existing fund symbols and optional allocations
- data quality cards with stale/fresh indicators
- unweighted overlap matrix
- weighted overlap matrix
- portfolio concentration table
- top overlapping fund pairs and shared tickers
- asset allocation section
- sector exposure section
- fee analysis section
- timestamp and disclaimer

Request flow:

1. User submits the form to `POST /analyse`
2. `split_symbols()` normalizes `existing_funds`
3. `parse_optional_allocations()` validates the optional allocation list and checks that the count matches the number of funds
4. Axum sends `AnalysePayload` to backend `POST /api/analyse`
5. The page rerenders with analysis output

Rendered sections:

- **Meta pills** — timestamp, top-10 concentration, total ticker count
- **Data quality** — one card per symbol with `last_updated`, `holdings_count`, and stale status
- **Overlap matrices** — rendered as tables from `OverlapMatrix`
- **Portfolio concentration** — top holdings and their weights
- **Top overlapping pairs** — fund pair, unweighted overlap, weighted overlap, shared tickers
- **Asset allocation** — portfolio table plus per-fund tables
- **Sector exposure** — portfolio table plus per-fund tables, with simple exposure bars
- **Fee analysis** — per-fund expense ratios, portfolio-weighted ER, and estimated annual cost per `$10k`

### Recommend Page

The Recommend page is rendered by `render_recommend_page()` and `RecommendPage`.

What it shows:

- request form for existing funds
- request form for candidate funds
- optional allocations field
- recommendation output grouped by existing fund
- scored candidate cards with explanation text

Request flow:

1. User submits the form to `POST /recommend`
2. `split_symbols()` normalizes existing and candidate fund lists
3. `parse_optional_allocations()` validates allocations when present
4. Axum sends `RecommendPayload` to backend `POST /api/recommend`
5. The page rerenders with grouped recommendation results

Score display format:

- candidate symbol
- total score shown as a large one-decimal metric
- explanation text from the backend
- data-quality badge derived from the penalty value
- four score rows with visual bars:
  - **Overlap reduction** (`0–50`)
  - **Performance** (`0–40`)
  - **Data quality penalty** (`0 to -20`)
  - **Cost penalty** (`0 to -10`)

## 6. Rust Models

`models.rs` contains the Rust types used to serialize requests and deserialize backend responses.

### Core response models

- `IngestResponse`
  - `funds: Vec<FundInput>`
  - `warnings: Vec<String>`
  - `disclaimer: String`
  - `timestamp: String`
- `AnalysisResponse`
  - `overlap_matrix: OverlapMatrix`
  - `concentration: ConcentrationResult`
  - `top_overlaps: Vec<OverlapPair>`
  - `data_quality: Vec<DataQualityEntry>`
  - `asset_allocation: AssetAllocation`
  - `sector_exposure: SectorExposure`
  - `fee_analysis: FeeAnalysis`
  - `disclaimer: String`
  - `timestamp: String`
- `RecommendResponse`
  - `recommendations: BTreeMap<String, Vec<ScoredCandidate>>`
  - `disclaimer: String`
  - `timestamp: String`

### Supporting analysis models

- `Holding` — ticker and weight
- `FundInput` — normalized fund symbol plus holdings
- `OverlapPair` — pairwise overlap details and shared tickers
- `OverlapMatrix` — ordered fund names plus unweighted/weighted matrices
- `ConcentrationEntry` / `ConcentrationResult` — top holdings and concentration summary
- `DataQualityEntry` — symbol, freshness date, stale flag, holdings count
- `AssetAllocationEntry` / `AssetAllocation` — portfolio and per-fund asset-class weights
- `SectorExposureEntry` / `SectorExposure` — portfolio and per-fund sector weights
- `FeeAnalysisEntry` / `FeeAnalysis` — expense-ratio detail and portfolio cost summary
- `ScoreBreakdown` — overlap reduction, performance, data quality penalty, cost penalty
- `ScoredCandidate` — candidate symbol, total score, breakdown, explanation

### Request payload models

- `SymbolsPayload { symbols }`
- `PastePayload { text }`
- `AnalysePayload { existing_funds, allocations }`
- `RecommendPayload { existing_funds, candidate_funds, allocations }`

## 7. Environment Variables

The frontend reads configuration from environment variables in `FrontendConfig::from_env()`:

- `FRONTEND_HOST` — default `127.0.0.1`
- `FRONTEND_PORT` — default `3000`
- `BACKEND_BASE_URL` — default `http://127.0.0.1:8000`

These values control:

- the Axum bind address
- the proxy target shown in the page header
- the target used by server-side `reqwest` requests and `/api/*` forwarding

## 8. Building and Running

Prerequisites:

- stable Rust toolchain
- backend running and reachable at `BACKEND_BASE_URL`

Build:

```bash
cd frontend
cargo build
```

Run with defaults:

```bash
cd frontend
cargo run
```

Run with explicit environment variables:

```bash
cd frontend
export FRONTEND_HOST=127.0.0.1
export FRONTEND_PORT=3000
export BACKEND_BASE_URL=http://127.0.0.1:8000
cargo run
```

When started, the frontend listens on `http://127.0.0.1:3000` by default and logs the backend proxy target.

## 9. Extending the Frontend

### Add a new page

1. Add page state and a `render_*_page()` function in `app.rs`
2. Create a Leptos component for the page body in `app.rs`
3. Add an Axum route and handler in `main.rs`
4. Add any request/response structs needed in `models.rs`
5. Add parsing helpers in `parsing.rs` if the page needs shared input normalization
6. Update navigation in `PageLayout`
7. If the page needs backend passthrough access, keep it under the same-origin `/api/*` pattern

### Add a new section to an existing page

1. Extend the relevant response struct in `models.rs`
2. Update the backend endpoint to return the new field
3. Add a rendering helper or Leptos component in `app.rs`
4. Insert the new section into `render_analysis_result()` or `render_recommendation_result()`
5. Reuse existing patterns such as:
   - card sections
   - table renderers
   - `meta` pills
   - badge and score-row helpers

### Implementation notes

- keep the disclaimer visible on every rendered page
- prefer adding typed Rust models before rendering new response data
- keep parsing and validation in shared helpers when multiple handlers need the same behavior
- preserve the single-origin boundary so the browser continues to use the frontend as its only origin
