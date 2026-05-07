use serde::{Deserialize, Serialize};

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
pub struct AnalysisResponse {
    pub overlap_matrix: OverlapMatrix,
    pub concentration: ConcentrationResult,
    pub top_overlaps: Vec<OverlapPair>,
    pub data_quality: Vec<DataQualityEntry>,
    pub disclaimer: String,
    pub timestamp: String,
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
