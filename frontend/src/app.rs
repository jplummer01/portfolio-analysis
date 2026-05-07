use leptos::prelude::*;

use crate::models::{
    AnalysisResponse, AssetAllocation, AssetAllocationEntry, FeeAnalysis, IngestResponse,
    RecommendResponse, ScoredCandidate, SectorExposure, SectorExposureEntry,
};

const DISCLAIMER: &str = "For informational purposes only; not financial advice.";
const STYLE: &str = r#"
:root {
  color-scheme: light;
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f4f7fb;
  color: #172033;
}
body {
  margin: 0;
  background: #f4f7fb;
  color: #172033;
}
a {
  color: #1557ff;
  text-decoration: none;
}
a:hover {
  text-decoration: underline;
}
.shell {
  max-width: 1180px;
  margin: 0 auto;
  padding: 0 1rem 3rem;
}
.banner {
  margin-top: 1rem;
  padding: 0.85rem 1rem;
  border-radius: 0.85rem;
  background: #fff8d6;
  border: 1px solid #ead58f;
  font-weight: 600;
}
.nav {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin: 1rem 0 1.5rem;
}
.nav a {
  padding: 0.7rem 1rem;
  border-radius: 999px;
  background: #dde7ff;
  color: #143063;
  font-weight: 600;
}
.nav a.active {
  background: #143063;
  color: white;
}
.hero {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: end;
  margin-bottom: 1.25rem;
}
.hero h1 {
  margin: 0 0 0.4rem;
  font-size: 2rem;
}
.hero p,
.muted {
  color: #52617a;
}
.grid {
  display: grid;
  gap: 1rem;
}
.grid.cols-2 {
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
}
.grid.cols-3 {
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}
.card {
  background: white;
  border-radius: 1rem;
  padding: 1rem;
  border: 1px solid #dde5f0;
  box-shadow: 0 6px 20px rgba(17, 38, 72, 0.06);
}
.card h2,
.card h3 {
  margin-top: 0;
}
form {
  display: grid;
  gap: 0.75rem;
}
input[type="text"],
textarea,
input[type="file"] {
  width: 100%;
  border: 1px solid #c7d3e5;
  border-radius: 0.75rem;
  padding: 0.75rem 0.85rem;
  font: inherit;
  box-sizing: border-box;
  background: #fcfdff;
}
textarea {
  min-height: 140px;
  resize: vertical;
}
button {
  appearance: none;
  border: 0;
  border-radius: 0.75rem;
  background: #1557ff;
  color: white;
  font: inherit;
  font-weight: 700;
  padding: 0.8rem 1rem;
  cursor: pointer;
}
button:hover {
  background: #1148d1;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 0.9rem;
}
.pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.65rem;
  border-radius: 999px;
  background: #eef3ff;
  color: #153262;
  font-size: 0.9rem;
}
.alert {
  padding: 0.85rem 1rem;
  border-radius: 0.85rem;
  border: 1px solid transparent;
}
.alert.info {
  background: #eef5ff;
  border-color: #c8daff;
}
.alert.error {
  background: #fff2f2;
  border-color: #f1b9b9;
  color: #7d1f1f;
}
.alert.warn {
  background: #fff8ea;
  border-color: #eccb7a;
  color: #735315;
}
.list {
  margin: 0;
  padding-left: 1.2rem;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.95rem;
}
th,
td {
  padding: 0.6rem 0.55rem;
  border-bottom: 1px solid #e4ebf4;
  text-align: left;
  vertical-align: top;
}
thead th {
  background: #f8fbff;
}
.metric {
  font-size: 1.5rem;
  font-weight: 800;
  color: #143063;
}
.badge {
  display: inline-block;
  padding: 0.28rem 0.6rem;
  border-radius: 999px;
  font-weight: 700;
  font-size: 0.85rem;
}
.badge.good {
  background: #e7f8ed;
  color: #18743d;
}
.badge.warn {
  background: #fff1da;
  color: #8a5b00;
}
.score-grid {
  display: grid;
  gap: 0.5rem;
}
.score-row {
  display: grid;
  gap: 0.35rem;
}
.score-row header {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.92rem;
}
.track {
  height: 0.7rem;
  background: #edf1f7;
  border-radius: 999px;
  overflow: hidden;
}
.fill {
  height: 100%;
  border-radius: 999px;
}
.fill.positive {
  background: linear-gradient(90deg, #2b6dff, #75a6ff);
}
.fill.negative {
  background: linear-gradient(90deg, #f29d38, #ffd08d);
}
.section-stack {
  display: grid;
  gap: 1rem;
}
.nested-card {
  padding: 0.85rem;
  border: 1px solid #e4ebf4;
  border-radius: 0.85rem;
  background: #f8fbff;
}
.nested-card h4 {
  margin: 0 0 0.75rem;
}
.table-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.table-bar .track {
  flex: 1;
  min-width: 7rem;
}
.footer {
  margin-top: 1.5rem;
  color: #64748b;
  font-size: 0.92rem;
}
@media (max-width: 700px) {
  .hero {
    flex-direction: column;
    align-items: start;
  }
}
"#;

#[derive(Clone)]
pub struct IngestPageState {
    pub symbols_input: String,
    pub paste_input: String,
    pub upload_filename: Option<String>,
    pub result: Option<Result<IngestResponse, String>>,
}

impl Default for IngestPageState {
    fn default() -> Self {
        Self {
            symbols_input: "SPY, QQQ".to_string(),
            paste_input: "SPY, QQQ, VTI".to_string(),
            upload_filename: None,
            result: None,
        }
    }
}

#[derive(Clone)]
pub struct AnalysePageState {
    pub existing_funds_input: String,
    pub allocations_input: String,
    pub result: Option<Result<AnalysisResponse, String>>,
}

impl Default for AnalysePageState {
    fn default() -> Self {
        Self {
            existing_funds_input: "SPY, QQQ".to_string(),
            allocations_input: "0.5, 0.5".to_string(),
            result: None,
        }
    }
}

#[derive(Clone)]
pub struct RecommendPageState {
    pub existing_funds_input: String,
    pub candidate_funds_input: String,
    pub allocations_input: String,
    pub result: Option<Result<RecommendResponse, String>>,
}

impl Default for RecommendPageState {
    fn default() -> Self {
        Self {
            existing_funds_input: "SPY".to_string(),
            candidate_funds_input: "ARKK, SCHD, VXUS".to_string(),
            allocations_input: String::new(),
            result: None,
        }
    }
}

pub fn render_ingest_page(state: IngestPageState, backend_base_url: &str) -> String {
    render(move || {
        view! {
            <PageLayout
                title="Ingest"
                active_path="/"
                headline="Ingest portfolio inputs"
                description="Capture existing and candidate funds from symbols, pasted text, or uploaded CSV/JSON files."
                backend_base_url=backend_base_url.to_string()
            >
                <IngestPage state=state />
            </PageLayout>
        }
    })
}

pub fn render_analyse_page(state: AnalysePageState, backend_base_url: &str) -> String {
    render(move || {
        view! {
            <PageLayout
                title="Analyse"
                active_path="/analyse"
                headline="Analyse portfolio overlap"
                description="Review overlap matrices, concentration, stale holdings flags, and the highest-overlap fund pairs."
                backend_base_url=backend_base_url.to_string()
            >
                <AnalysePage state=state />
            </PageLayout>
        }
    })
}

pub fn render_recommend_page(state: RecommendPageState, backend_base_url: &str) -> String {
    render(move || {
        view! {
            <PageLayout
                title="Recommend"
                active_path="/recommend"
                headline="Compare switch candidates"
                description="Inspect candidate scores, component-level breakdowns, explanation text, and data-quality penalties."
                backend_base_url=backend_base_url.to_string()
            >
                <RecommendPage state=state />
            </PageLayout>
        }
    })
}

fn render<F, V>(app: F) -> String
where
    F: FnOnce() -> V,
    V: IntoView,
{
    format!("<!DOCTYPE html>{}", app().into_view().to_html())
}

#[component]
fn PageLayout(
    title: &'static str,
    active_path: &'static str,
    headline: &'static str,
    description: &'static str,
    backend_base_url: String,
    children: Children,
) -> impl IntoView {
    let ingest_class = nav_class(active_path == "/");
    let analyse_class = nav_class(active_path == "/analyse");
    let recommend_class = nav_class(active_path == "/recommend");

    view! {
        <html lang="en">
            <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <title>{format!("{title} · Fund Overlap Analyzer")}</title>
                <style>{STYLE}</style>
            </head>
            <body>
                <div class="shell">
                    <div class="banner">{DISCLAIMER}</div>
                    <nav class="nav">
                        <a href="/" class=ingest_class>"Ingest"</a>
                        <a href="/analyse" class=analyse_class>"Analyse"</a>
                        <a href="/recommend" class=recommend_class>"Recommend"</a>
                    </nav>
                    <section class="hero">
                        <div>
                            <h1>{headline}</h1>
                            <p>{description}</p>
                        </div>
                        <div class="pill">
                            <strong>"Proxy target"</strong>
                            <span>{backend_base_url}</span>
                        </div>
                    </section>
                    {children()}
                    <div class="footer">
                        "All calculations and recommendations are informational only and should be reviewed alongside data quality notes."
                    </div>
                </div>
            </body>
        </html>
    }
}

#[component]
fn IngestPage(state: IngestPageState) -> impl IntoView {
    let result_view = match state.result.clone() {
        Some(Ok(response)) => render_ingest_result(response).into_any(),
        Some(Err(message)) => render_error_result(message).into_any(),
        None => view! {
            <div class="alert info">
                "Choose any ingestion method to preview normalized funds, warning messages, and response timestamps."
            </div>
        }
        .into_any(),
    };

    let upload_name = state
        .upload_filename
        .clone()
        .unwrap_or_else(|| "No file submitted yet".to_string());

    view! {
        <div class="grid cols-2">
            <section class="card">
                <h2>"Symbols"</h2>
                <p class="muted">"Submit comma- or newline-separated symbols to /api/ingest/symbols."</p>
                <form method="post" action="/ingest/symbols">
                    <input
                        type="text"
                        name="symbols"
                        value=state.symbols_input
                        placeholder="SPY, QQQ, VTI"
                    />
                    <button type="submit">"Ingest symbols"</button>
                </form>
            </section>
            <section class="card">
                <h2>"Paste data"</h2>
                <p class="muted">"Paste raw symbol text or provider exports and submit to /api/ingest/paste."</p>
                <form method="post" action="/ingest/paste">
                    <textarea name="text">{state.paste_input}</textarea>
                    <button type="submit">"Ingest pasted text"</button>
                </form>
            </section>
            <section class="card">
                <h2>"Upload CSV or JSON"</h2>
                <p class="muted">"Files are forwarded as multipart form data to /api/ingest/upload."</p>
                <form method="post" action="/ingest/upload" enctype="multipart/form-data">
                    <input type="file" name="file" accept=".csv,.json,application/json,text/csv" />
                    <div class="pill">{format!("Last submitted file: {upload_name}")}</div>
                    <button type="submit">"Upload file"</button>
                </form>
            </section>
            <section class="card">
                <h2>"Ingestion results"</h2>
                {result_view}
            </section>
        </div>
    }
}

#[component]
fn AnalysePage(state: AnalysePageState) -> impl IntoView {
    let result_view = match state.result.clone() {
        Some(Ok(response)) => render_analysis_result(response).into_any(),
        Some(Err(message)) => render_error_result(message).into_any(),
        None => view! {
            <div class="alert info">
                "Run an analysis to populate overlap matrices, concentration metrics, timestamps, and stale-data indicators."
            </div>
        }
        .into_any(),
    };

    view! {
        <div class="grid cols-2">
            <section class="card">
                <h2>"Analysis request"</h2>
                <form method="post" action="/analyse">
                    <label>
                        <strong>"Existing funds"</strong>
                        <input
                            type="text"
                            name="existing_funds"
                            value=state.existing_funds_input
                            placeholder="SPY, QQQ"
                        />
                    </label>
                    <label>
                        <strong>"Allocations (optional)"</strong>
                        <input
                            type="text"
                            name="allocations"
                            value=state.allocations_input
                            placeholder="0.5, 0.5"
                        />
                    </label>
                    <button type="submit">"Analyse portfolio"</button>
                </form>
            </section>
            <section class="card">
                <h2>"Analysis output"</h2>
                {result_view}
            </section>
        </div>
    }
}

#[component]
fn RecommendPage(state: RecommendPageState) -> impl IntoView {
    let result_view = match state.result.clone() {
        Some(Ok(response)) => render_recommendation_result(response).into_any(),
        Some(Err(message)) => render_error_result(message).into_any(),
        None => view! {
            <div class="alert info">
                "Run a recommendation request to inspect candidate scores, explanations, and data-quality penalties."
            </div>
        }
        .into_any(),
    };

    view! {
        <div class="grid cols-2">
            <section class="card">
                <h2>"Recommendation request"</h2>
                <form method="post" action="/recommend">
                    <label>
                        <strong>"Existing funds"</strong>
                        <input
                            type="text"
                            name="existing_funds"
                            value=state.existing_funds_input
                            placeholder="SPY"
                        />
                    </label>
                    <label>
                        <strong>"Candidate funds"</strong>
                        <input
                            type="text"
                            name="candidate_funds"
                            value=state.candidate_funds_input
                            placeholder="ARKK, SCHD, VXUS"
                        />
                    </label>
                    <label>
                        <strong>"Allocations (optional)"</strong>
                        <input
                            type="text"
                            name="allocations"
                            value=state.allocations_input
                            placeholder="0.5, 0.5"
                        />
                    </label>
                    <button type="submit">"Score candidates"</button>
                </form>
            </section>
            <section class="card">
                <h2>"Recommendation output"</h2>
                {result_view}
            </section>
        </div>
    }
}

fn render_ingest_result(response: IngestResponse) -> impl IntoView {
    let fund_count = response.funds.len();
    let warnings_view = if response.warnings.is_empty() {
        view! { <div class="alert info">"No ingestion warnings returned by the backend."</div> }
            .into_any()
    } else {
        let warnings = response
            .warnings
            .into_iter()
            .map(|warning| view! { <li>{warning}</li> })
            .collect_view();
        view! {
            <div class="alert warn">
                <strong>"Warnings"</strong>
                <ul class="list">{warnings}</ul>
            </div>
        }
        .into_any()
    };

    let rows = response
        .funds
        .into_iter()
        .map(|fund| {
            let preview = fund
                .holdings
                .iter()
                .take(4)
                .map(|holding| format!("{} ({})", holding.ticker, format_percent(holding.weight)))
                .collect::<Vec<_>>()
                .join(", ");
            view! {
                <tr>
                    <td><strong>{fund.symbol}</strong></td>
                    <td>{fund.holdings.len()}</td>
                    <td>{if preview.is_empty() { "No holdings returned".to_string() } else { preview }}</td>
                </tr>
            }
        })
        .collect_view();

    view! {
        <div class="meta">
            <span class="pill">{format!("Timestamp: {}", response.timestamp)}</span>
            <span class="pill">{format!("Funds: {fund_count}")}</span>
        </div>
        {warnings_view}
        <table>
            <thead>
                <tr>
                    <th>"Fund"</th>
                    <th>"Holdings"</th>
                    <th>"Preview"</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        <p class="muted">{response.disclaimer}</p>
    }
}

fn render_analysis_result(response: AnalysisResponse) -> impl IntoView {
    let AnalysisResponse {
        overlap_matrix,
        concentration,
        top_overlaps,
        data_quality,
        asset_allocation,
        sector_exposure,
        fee_analysis,
        disclaimer,
        timestamp,
    } = response;

    let data_quality_cards = data_quality
        .clone()
        .into_iter()
        .map(|entry| {
            let status_class = if entry.is_stale { "badge warn" } else { "badge good" };
            let status_label = if entry.is_stale { "Stale data" } else { "Fresh enough" };
            view! {
                <div class="card">
                    <div style="display:flex;justify-content:space-between;gap:0.75rem;align-items:start;">
                        <div>
                            <h3>{entry.symbol.clone()}</h3>
                            <p class="muted">{format!("Last updated: {}", entry.last_updated.unwrap_or_else(|| "Unknown".to_string()))}</p>
                            <p class="muted">{format!("Holdings captured: {}", entry.holdings_count)}</p>
                        </div>
                        <span class=status_class>{status_label}</span>
                    </div>
                </div>
            }
        })
        .collect_view();

    let overlap_rows = top_overlaps
        .into_iter()
        .map(|pair| {
            let shared = if pair.shared_tickers.is_empty() {
                "No shared tickers".to_string()
            } else {
                pair.shared_tickers.join(", ")
            };
            view! {
                <tr>
                    <td>{format!("{} ↔ {}", pair.fund_a, pair.fund_b)}</td>
                    <td>{format_percent(pair.unweighted)}</td>
                    <td>{format_percent(pair.weighted)}</td>
                    <td>{shared}</td>
                </tr>
            }
        })
        .collect_view();

    let top_10_weight = concentration.top_10_weight;
    let total_tickers = concentration.total_tickers;

    let concentration_rows = concentration
        .top_holdings
        .into_iter()
        .map(|holding| {
            view! {
                <tr>
                    <td>{holding.ticker}</td>
                    <td>{format_percent(holding.weight)}</td>
                </tr>
            }
        })
        .collect_view();

    let overlap_funds = overlap_matrix.funds;
    let unweighted_overlap = overlap_matrix.unweighted;
    let weighted_overlap = overlap_matrix.weighted;

    view! {
        <div class="meta">
            <span class="pill">{format!("Timestamp: {}", timestamp)}</span>
            <span class="pill">{format!("Top-10 concentration: {}", format_percent(top_10_weight))}</span>
            <span class="pill">{format!("Total tickers: {}", total_tickers)}</span>
        </div>
        <div class="grid cols-3">{data_quality_cards}</div>
        <div class="grid cols-2">
            <div class="card">
                <h3>"Overlap matrix — unweighted"</h3>
                <MatrixTable funds=overlap_funds.clone() values=unweighted_overlap />
            </div>
            <div class="card">
                <h3>"Overlap matrix — weighted"</h3>
                <MatrixTable funds=overlap_funds values=weighted_overlap />
            </div>
            <div class="card">
                <h3>"Portfolio concentration"</h3>
                <table>
                    <thead>
                        <tr>
                            <th>"Ticker"</th>
                            <th>"Weight"</th>
                        </tr>
                    </thead>
                    <tbody>{concentration_rows}</tbody>
                </table>
            </div>
            <div class="card">
                <h3>"Top overlapping pairs"</h3>
                <table>
                    <thead>
                        <tr>
                            <th>"Pair"</th>
                            <th>"Unweighted"</th>
                            <th>"Weighted"</th>
                            <th>"Shared tickers"</th>
                        </tr>
                    </thead>
                    <tbody>{overlap_rows}</tbody>
                </table>
            </div>
        </div>
        <div class="grid cols-2">
            <section class="card">
                <h3>"Asset allocation"</h3>
                <p class="muted">"Portfolio and per-fund asset class weights returned by the analysis endpoint."</p>
                <AssetAllocationSection asset_allocation=asset_allocation />
            </section>
            <section class="card">
                <h3>"Sector exposure"</h3>
                <p class="muted">"Portfolio and per-fund sector mixes with relative exposure bars."</p>
                <SectorExposureSection sector_exposure=sector_exposure />
            </section>
        </div>
        <section class="card">
            <h3>"Fee analysis"</h3>
            <FeeAnalysisSection fee_analysis=fee_analysis />
        </section>
        <p class="muted">{disclaimer}</p>
    }
}

#[component]
fn AssetAllocationSection(asset_allocation: AssetAllocation) -> impl IntoView {
    let portfolio_table = render_asset_allocation_table(asset_allocation.portfolio);
    let per_fund_tables = render_asset_allocation_fund_cards(asset_allocation.per_fund);

    view! {
        <div class="section-stack">
            <div>
                <h4>"Portfolio"</h4>
                {portfolio_table}
            </div>
            <div>
                <h4>"Per fund"</h4>
                {per_fund_tables}
            </div>
        </div>
    }
}

#[component]
fn SectorExposureSection(sector_exposure: SectorExposure) -> impl IntoView {
    let portfolio_table = render_sector_exposure_table(sector_exposure.portfolio);
    let per_fund_tables = render_sector_exposure_fund_cards(sector_exposure.per_fund);

    view! {
        <div class="section-stack">
            <div>
                <h4>"Portfolio"</h4>
                {portfolio_table}
            </div>
            <div>
                <h4>"Per fund"</h4>
                {per_fund_tables}
            </div>
        </div>
    }
}

#[component]
fn FeeAnalysisSection(fee_analysis: FeeAnalysis) -> impl IntoView {
    let weighted_er_raw = format!("{:.4}", fee_analysis.portfolio_weighted_er);
    let fee_rows = if fee_analysis.per_fund.is_empty() {
        view! { <tr><td colspan="3">"No fee data returned."</td></tr> }.into_any()
    } else {
        fee_analysis
            .per_fund
            .into_iter()
            .map(|entry| {
                view! {
                    <tr>
                        <td><strong>{entry.symbol}</strong></td>
                        <td>{entry.expense_ratio_pct}</td>
                        <td>{format!("{:.4}", entry.expense_ratio)}</td>
                    </tr>
                }
            })
            .collect_view()
            .into_any()
    };

    view! {
        <div class="section-stack">
            <div class="meta">
                <span class="pill">{format!("Portfolio-weighted ER: {}", fee_analysis.portfolio_weighted_er_pct)}</span>
                <span class="pill">{format!("Raw ER: {weighted_er_raw}")}</span>
                <span class="pill">{format!("Estimated annual cost per $10k: ${:.2}", fee_analysis.estimated_annual_cost_per_10k)}</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>"Fund"</th>
                        <th>"Expense ratio"</th>
                        <th>"Raw value"</th>
                    </tr>
                </thead>
                <tbody>{fee_rows}</tbody>
            </table>
        </div>
    }
}

fn render_recommendation_result(response: RecommendResponse) -> impl IntoView {
    let groups = response
        .recommendations
        .into_iter()
        .map(|(existing, candidates)| {
            let candidate_views = candidates.into_iter().map(render_candidate).collect_view();
            view! {
                <section class="card">
                    <h3>{format!("Existing fund: {existing}")}</h3>
                    <div class="grid">{candidate_views}</div>
                </section>
            }
        })
        .collect_view();

    view! {
        <div class="meta">
            <span class="pill">{format!("Timestamp: {}", response.timestamp)}</span>
            <span class="pill">"Data quality indicators use backend penalties and explanation text."</span>
        </div>
        <div class="grid">{groups}</div>
        <p class="muted">{response.disclaimer}</p>
    }
}

fn render_asset_allocation_table(entries: Vec<AssetAllocationEntry>) -> AnyView {
    if entries.is_empty() {
        view! { <div class="alert info">"No asset allocation data returned."</div> }.into_any()
    } else {
        let rows = entries
            .into_iter()
            .map(|entry| {
                view! {
                    <tr>
                        <td>{entry.asset_class}</td>
                        <td>{format_percent(entry.weight)}</td>
                    </tr>
                }
            })
            .collect_view();

        view! {
            <table>
                <thead>
                    <tr>
                        <th>"Asset class"</th>
                        <th>"Weight"</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        }
        .into_any()
    }
}

fn render_asset_allocation_fund_cards(
    per_fund: std::collections::BTreeMap<String, Vec<AssetAllocationEntry>>,
) -> AnyView {
    if per_fund.is_empty() {
        view! { <div class="alert info">"No per-fund asset allocation data returned."</div> }
            .into_any()
    } else {
        let cards = per_fund
            .into_iter()
            .map(|(symbol, entries)| {
                let table = render_asset_allocation_table(entries);
                view! {
                    <div class="nested-card">
                        <h4>{symbol}</h4>
                        {table}
                    </div>
                }
            })
            .collect_view();

        view! { <div class="grid cols-2">{cards}</div> }.into_any()
    }
}

fn render_sector_exposure_table(entries: Vec<SectorExposureEntry>) -> AnyView {
    if entries.is_empty() {
        view! { <div class="alert info">"No sector exposure data returned."</div> }.into_any()
    } else {
        let rows = entries
            .into_iter()
            .map(|entry| {
                let width = percentage(entry.weight, 1.0);
                view! {
                    <tr>
                        <td>{entry.sector}</td>
                        <td>{format_percent(entry.weight)}</td>
                        <td>
                            <div class="table-bar">
                                <div class="track">
                                    <div class="fill positive" style=format!("width: {width:.0}%;")></div>
                                </div>
                            </div>
                        </td>
                    </tr>
                }
            })
            .collect_view();

        view! {
            <table>
                <thead>
                    <tr>
                        <th>"Sector"</th>
                        <th>"Weight"</th>
                        <th>"Exposure"</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        }
        .into_any()
    }
}

fn render_sector_exposure_fund_cards(
    per_fund: std::collections::BTreeMap<String, Vec<SectorExposureEntry>>,
) -> AnyView {
    if per_fund.is_empty() {
        view! { <div class="alert info">"No per-fund sector exposure data returned."</div> }
            .into_any()
    } else {
        let cards = per_fund
            .into_iter()
            .map(|(symbol, entries)| {
                let table = render_sector_exposure_table(entries);
                view! {
                    <div class="nested-card">
                        <h4>{symbol}</h4>
                        {table}
                    </div>
                }
            })
            .collect_view();

        view! { <div class="grid cols-2">{cards}</div> }.into_any()
    }
}

fn render_candidate(candidate: ScoredCandidate) -> impl IntoView {
    let data_quality = penalty_summary(candidate.breakdown.data_quality_penalty);
    view! {
        <article class="card">
            <div style="display:flex;justify-content:space-between;gap:1rem;align-items:start;">
                <div>
                    <h3>{candidate.symbol.clone()}</h3>
                    <p class="muted">{candidate.explanation.clone()}</p>
                </div>
                <div>
                    <div class="metric">{format!("{:.1}", candidate.total_score)}</div>
                    <span class=data_quality.0>{data_quality.1}</span>
                </div>
            </div>
            <ScoreBreakdown candidate=candidate />
        </article>
    }
}

#[component]
fn ScoreBreakdown(candidate: ScoredCandidate) -> impl IntoView {
    view! {
        <div class="score-grid">
            <ScoreRow label="Overlap reduction" value=candidate.breakdown.overlap_reduction max=50.0 positive=true />
            <ScoreRow label="Performance" value=candidate.breakdown.performance max=40.0 positive=true />
            <ScoreRow label="Data quality penalty" value=candidate.breakdown.data_quality_penalty max=20.0 positive=false />
            <ScoreRow label="Cost penalty" value=candidate.breakdown.cost_penalty max=10.0 positive=false />
        </div>
    }
}

#[component]
fn ScoreRow(label: &'static str, value: f64, max: f64, positive: bool) -> impl IntoView {
    let width = if positive {
        percentage(value, max)
    } else {
        percentage(value.abs(), max)
    };
    let bar_class = if positive {
        "fill positive"
    } else {
        "fill negative"
    };

    view! {
        <div class="score-row">
            <header>
                <strong>{label}</strong>
                <span>{format!("{value:.1}")}</span>
            </header>
            <div class="track">
                <div class=bar_class style=format!("width: {width:.0}%;")></div>
            </div>
        </div>
    }
}

#[component]
fn MatrixTable(funds: Vec<String>, values: Vec<Vec<f64>>) -> impl IntoView {
    let headers = funds
        .clone()
        .into_iter()
        .map(|fund| view! { <th>{fund}</th> })
        .collect_view();

    let rows = funds
        .into_iter()
        .enumerate()
        .map(|(row_index, fund)| {
            let cells = values
                .get(row_index)
                .cloned()
                .unwrap_or_default()
                .into_iter()
                .map(|value| view! { <td>{format_percent(value)}</td> })
                .collect_view();
            view! {
                <tr>
                    <th>{fund}</th>
                    {cells}
                </tr>
            }
        })
        .collect_view();

    view! {
        <table>
            <thead>
                <tr>
                    <th>"Fund"</th>
                    {headers}
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    }
}

fn render_error_result(message: String) -> impl IntoView {
    view! { <div class="alert error">{message}</div> }
}

fn nav_class(active: bool) -> &'static str {
    if active { "active" } else { "" }
}

fn penalty_summary(value: f64) -> (&'static str, &'static str) {
    if value <= -10.0 {
        ("badge warn", "Penalty applied")
    } else {
        ("badge good", "No quality penalty")
    }
}

fn percentage(value: f64, max: f64) -> f64 {
    if max <= 0.0 {
        0.0
    } else {
        ((value / max) * 100.0).clamp(0.0, 100.0)
    }
}

fn format_percent(value: f64) -> String {
    format!("{:.2}%", value * 100.0)
}
