use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Holding {
    pub ticker: String,
    pub weight: f64,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct FundInput {
    pub symbol: String,
    pub holdings: Vec<Holding>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct IngestResponse {
    pub funds: Vec<FundInput>,
    pub warnings: Vec<String>,
    pub disclaimer: String,
    pub timestamp: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct OverlapPair {
    pub fund_a: String,
    pub fund_b: String,
    pub unweighted: f64,
    pub weighted: f64,
    pub shared_tickers: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct OverlapMatrix {
    pub funds: Vec<String>,
    pub unweighted: Vec<Vec<f64>>,
    pub weighted: Vec<Vec<f64>>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ConcentrationEntry {
    pub ticker: String,
    pub weight: f64,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ConcentrationResult {
    pub top_holdings: Vec<ConcentrationEntry>,
    pub total_tickers: usize,
    pub top_10_weight: f64,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct DataQualityEntry {
    pub symbol: String,
    pub last_updated: Option<String>,
    pub is_stale: bool,
    pub holdings_count: usize,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct AssetAllocationEntry {
    pub asset_class: String,
    pub weight: f64,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct AssetAllocation {
    pub portfolio: Vec<AssetAllocationEntry>,
    pub per_fund: BTreeMap<String, Vec<AssetAllocationEntry>>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct SectorExposureEntry {
    pub sector: String,
    pub weight: f64,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct SectorExposure {
    pub portfolio: Vec<SectorExposureEntry>,
    pub per_fund: BTreeMap<String, Vec<SectorExposureEntry>>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct FeeAnalysisEntry {
    pub symbol: String,
    pub expense_ratio: f64,
    pub expense_ratio_pct: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct FeeAnalysis {
    pub per_fund: Vec<FeeAnalysisEntry>,
    pub portfolio_weighted_er: f64,
    pub portfolio_weighted_er_pct: String,
    pub estimated_annual_cost_per_10k: f64,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct AgentCallRecord {
    pub agent_name: String,
    pub url: String,
    pub status_code: Option<i32>,
    pub latency_ms: Option<f64>,
    pub error: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct DebugInfo {
    pub execution_mode: String,
    pub agents_called: Vec<AgentCallRecord>,
    pub fallback_used: bool,
    pub fallback_reason: Option<String>,
    pub total_latency_ms: Option<f64>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct AnalysisResponse {
    pub overlap_matrix: OverlapMatrix,
    pub concentration: ConcentrationResult,
    pub top_overlaps: Vec<OverlapPair>,
    pub data_quality: Vec<DataQualityEntry>,
    pub asset_allocation: AssetAllocation,
    pub sector_exposure: SectorExposure,
    pub fee_analysis: FeeAnalysis,
    pub disclaimer: String,
    pub timestamp: String,
    pub debug_info: Option<DebugInfo>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ScoreBreakdown {
    pub overlap_reduction: f64,
    pub performance: f64,
    pub data_quality_penalty: f64,
    pub cost_penalty: f64,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ScoredCandidate {
    pub symbol: String,
    pub total_score: f64,
    pub breakdown: ScoreBreakdown,
    pub explanation: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct RecommendResponse {
    pub recommendations: std::collections::BTreeMap<String, Vec<ScoredCandidate>>,
    pub disclaimer: String,
    pub timestamp: String,
    pub debug_info: Option<DebugInfo>,
}

#[derive(Clone, Debug, Serialize)]
pub struct SymbolsPayload {
    pub symbols: Vec<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct PastePayload {
    pub text: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct AnalysePayload {
    pub existing_funds: Vec<String>,
    pub allocations: Option<Vec<f64>>,
}

#[derive(Clone, Debug, Serialize)]
pub struct RecommendPayload {
    pub existing_funds: Vec<String>,
    pub candidate_funds: Vec<String>,
    pub allocations: Option<Vec<f64>>,
}
