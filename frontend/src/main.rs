mod app;
mod models;
mod parsing;

use std::env;

use app::{AnalysePageState, IngestPageState, RecommendPageState};
use axum::{
    Router,
    body::{Body, to_bytes},
    extract::{Form, Multipart, Request, State},
    http::{Response, StatusCode, header},
    response::{Html, IntoResponse},
    routing::{any, get, post},
};
use models::{
    AnalysePayload, AnalysisResponse, IngestResponse, PastePayload, RecommendPayload,
    RecommendResponse, SymbolsPayload,
};
use parsing::{parse_optional_allocations, split_symbols};
use reqwest::{Client, multipart};
use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};

const DEFAULT_FRONTEND_HOST: &str = "127.0.0.1";
const DEFAULT_FRONTEND_PORT: u16 = 3000;
const DEFAULT_BACKEND_BASE_URL: &str = "http://127.0.0.1:8000";
const MAX_PROXY_BODY_BYTES: usize = 10 * 1024 * 1024;

#[derive(Clone, Debug)]
struct FrontendConfig {
    frontend_host: String,
    frontend_port: u16,
    backend_base_url: String,
}

impl FrontendConfig {
    fn from_env() -> Self {
        let frontend_host =
            env::var("FRONTEND_HOST").unwrap_or_else(|_| DEFAULT_FRONTEND_HOST.to_string());
        let frontend_port = env::var("FRONTEND_PORT")
            .ok()
            .and_then(|value| value.parse::<u16>().ok())
            .unwrap_or(DEFAULT_FRONTEND_PORT);
        let backend_base_url =
            env::var("BACKEND_BASE_URL").unwrap_or_else(|_| DEFAULT_BACKEND_BASE_URL.to_string());

        Self {
            frontend_host,
            frontend_port,
            backend_base_url,
        }
    }
}

#[derive(Clone)]
struct AppState {
    client: Client,
    config: FrontendConfig,
}

impl AppState {
    fn new(config: FrontendConfig) -> Self {
        Self {
            client: Client::new(),
            config,
        }
    }

    fn backend_url(&self, path: &str) -> String {
        format!(
            "{}{}",
            self.config.backend_base_url.trim_end_matches('/'),
            path
        )
    }

    async fn post_json<TReq, TRes>(&self, path: &str, payload: &TReq) -> Result<TRes, FrontendError>
    where
        TReq: Serialize + ?Sized,
        TRes: DeserializeOwned,
    {
        let response = self
            .client
            .post(self.backend_url(path))
            .json(payload)
            .send()
            .await
            .map_err(|error| {
                FrontendError::new(format!("Backend request failed for {path}: {error}"))
            })?;

        parse_json_response(response).await
    }

    async fn post_multipart<TRes>(
        &self,
        path: &str,
        form: multipart::Form,
    ) -> Result<TRes, FrontendError>
    where
        TRes: DeserializeOwned,
    {
        let response = self
            .client
            .post(self.backend_url(path))
            .multipart(form)
            .send()
            .await
            .map_err(|error| {
                FrontendError::new(format!("Backend upload failed for {path}: {error}"))
            })?;

        parse_json_response(response).await
    }
}

#[derive(Clone, Debug)]
struct FrontendError {
    message: String,
}

impl FrontendError {
    fn new(message: String) -> Self {
        Self { message }
    }
}

impl From<FrontendError> for String {
    fn from(value: FrontendError) -> Self {
        value.message
    }
}

#[derive(Debug, Deserialize)]
struct SymbolsForm {
    symbols: String,
}

#[derive(Debug, Deserialize)]
struct PasteForm {
    text: String,
}

#[derive(Debug, Deserialize)]
struct AnalyseForm {
    existing_funds: String,
    #[serde(default)]
    allocations: String,
}

#[derive(Debug, Deserialize)]
struct RecommendForm {
    existing_funds: String,
    candidate_funds: String,
    #[serde(default)]
    allocations: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let config = FrontendConfig::from_env();
    let bind_address = format!("{}:{}", config.frontend_host, config.frontend_port);
    let listener = tokio::net::TcpListener::bind(&bind_address).await?;

    let app = Router::new()
        .route("/", get(get_ingest_page))
        .route("/ingest/symbols", post(post_ingest_symbols))
        .route("/ingest/paste", post(post_ingest_paste))
        .route("/ingest/upload", post(post_ingest_upload))
        .route("/analyse", get(get_analyse_page).post(post_analyse_page))
        .route(
            "/recommend",
            get(get_recommend_page).post(post_recommend_page),
        )
        .route("/api/{*path}", any(proxy_api))
        .with_state(AppState::new(config.clone()));

    println!(
        "frontend listening on http://{}:{} and proxying /api/* to {}",
        config.frontend_host, config.frontend_port, config.backend_base_url
    );

    axum::serve(listener, app).await?;
    Ok(())
}

async fn get_ingest_page(State(state): State<AppState>) -> Html<String> {
    Html(app::render_ingest_page(
        IngestPageState::default(),
        &state.config.backend_base_url,
    ))
}

async fn post_ingest_symbols(
    State(state): State<AppState>,
    Form(form): Form<SymbolsForm>,
) -> Html<String> {
    let symbols = split_symbols(&form.symbols);
    let result = if symbols.is_empty() {
        Err("Enter at least one symbol before submitting.".to_string())
    } else {
        state
            .post_json::<_, IngestResponse>("/api/ingest/symbols", &SymbolsPayload { symbols })
            .await
            .map_err(String::from)
    };

    Html(app::render_ingest_page(
        IngestPageState {
            symbols_input: form.symbols,
            result: Some(result),
            ..IngestPageState::default()
        },
        &state.config.backend_base_url,
    ))
}

async fn post_ingest_paste(
    State(state): State<AppState>,
    Form(form): Form<PasteForm>,
) -> Html<String> {
    let result = if form.text.trim().is_empty() {
        Err("Paste data cannot be empty.".to_string())
    } else {
        state
            .post_json::<_, IngestResponse>(
                "/api/ingest/paste",
                &PastePayload {
                    text: form.text.clone(),
                },
            )
            .await
            .map_err(String::from)
    };

    Html(app::render_ingest_page(
        IngestPageState {
            paste_input: form.text,
            result: Some(result),
            ..IngestPageState::default()
        },
        &state.config.backend_base_url,
    ))
}

async fn post_ingest_upload(
    State(state): State<AppState>,
    mut multipart: Multipart,
) -> Html<String> {
    let mut filename = None;
    let mut upload: Option<(String, Vec<u8>, Option<String>)> = None;

    while let Ok(Some(field)) = multipart.next_field().await {
        if field.name() == Some("file") {
            let file_name = field
                .file_name()
                .map(str::to_string)
                .unwrap_or_else(|| "upload.bin".to_string());
            let content_type = field.content_type().map(str::to_string);
            match field.bytes().await {
                Ok(bytes) => {
                    filename = Some(file_name.clone());
                    upload = Some((file_name, bytes.to_vec(), content_type));
                }
                Err(error) => {
                    let page = IngestPageState {
                        upload_filename: Some(file_name),
                        result: Some(Err(format!("Could not read uploaded file: {error}"))),
                        ..IngestPageState::default()
                    };
                    return Html(app::render_ingest_page(
                        page,
                        &state.config.backend_base_url,
                    ));
                }
            }
            break;
        }
    }

    let result = if let Some((file_name, bytes, content_type)) = upload {
        let part = match content_type {
            Some(content_type) => multipart::Part::bytes(bytes.clone())
                .file_name(file_name.clone())
                .mime_str(&content_type)
                .unwrap_or_else(|_| multipart::Part::bytes(bytes).file_name(file_name.clone())),
            None => multipart::Part::bytes(bytes).file_name(file_name.clone()),
        };
        state
            .post_multipart::<IngestResponse>(
                "/api/ingest/upload",
                multipart::Form::new().part("file", part),
            )
            .await
            .map_err(String::from)
    } else {
        Err("Choose a CSV or JSON file before uploading.".to_string())
    };

    Html(app::render_ingest_page(
        IngestPageState {
            upload_filename: filename,
            result: Some(result),
            ..IngestPageState::default()
        },
        &state.config.backend_base_url,
    ))
}

async fn get_analyse_page(State(state): State<AppState>) -> Html<String> {
    Html(app::render_analyse_page(
        AnalysePageState::default(),
        &state.config.backend_base_url,
    ))
}

async fn post_analyse_page(
    State(state): State<AppState>,
    Form(form): Form<AnalyseForm>,
) -> Html<String> {
    let existing_funds = split_symbols(&form.existing_funds);
    let result = if existing_funds.is_empty() {
        Err("Enter at least one existing fund before analysing.".to_string())
    } else {
        match parse_optional_allocations(&form.allocations, existing_funds.len()) {
            Ok(allocations) => state
                .post_json::<_, AnalysisResponse>(
                    "/api/analyse",
                    &AnalysePayload {
                        existing_funds,
                        allocations,
                    },
                )
                .await
                .map_err(String::from),
            Err(error) => Err(error),
        }
    };

    Html(app::render_analyse_page(
        AnalysePageState {
            existing_funds_input: form.existing_funds,
            allocations_input: form.allocations,
            result: Some(result),
        },
        &state.config.backend_base_url,
    ))
}

async fn get_recommend_page(State(state): State<AppState>) -> Html<String> {
    Html(app::render_recommend_page(
        RecommendPageState::default(),
        &state.config.backend_base_url,
    ))
}

async fn post_recommend_page(
    State(state): State<AppState>,
    Form(form): Form<RecommendForm>,
) -> Html<String> {
    let existing_funds = split_symbols(&form.existing_funds);
    let candidate_funds = split_symbols(&form.candidate_funds);
    let result = if existing_funds.is_empty() {
        Err("Enter at least one existing fund before requesting candidates.".to_string())
    } else if candidate_funds.is_empty() {
        Err("Enter at least one candidate fund before requesting candidates.".to_string())
    } else {
        match parse_optional_allocations(&form.allocations, existing_funds.len()) {
            Ok(allocations) => state
                .post_json::<_, RecommendResponse>(
                    "/api/recommend",
                    &RecommendPayload {
                        existing_funds,
                        candidate_funds,
                        allocations,
                    },
                )
                .await
                .map_err(String::from),
            Err(error) => Err(error),
        }
    };

    Html(app::render_recommend_page(
        RecommendPageState {
            existing_funds_input: form.existing_funds,
            candidate_funds_input: form.candidate_funds,
            allocations_input: form.allocations,
            result: Some(result),
        },
        &state.config.backend_base_url,
    ))
}

async fn proxy_api(State(state): State<AppState>, request: Request) -> impl IntoResponse {
    let (parts, body) = request.into_parts();
    let target_url = format!(
        "{}{}",
        state.config.backend_base_url.trim_end_matches('/'),
        parts
            .uri
            .path_and_query()
            .map(|value| value.as_str())
            .unwrap_or(parts.uri.path())
    );

    let body_bytes = match to_bytes(body, MAX_PROXY_BODY_BYTES).await {
        Ok(bytes) => bytes,
        Err(error) => {
            return (
                StatusCode::BAD_REQUEST,
                format!("Could not read request body: {error}"),
            )
                .into_response();
        }
    };

    let mut outbound = state.client.request(parts.method, target_url);
    for (name, value) in &parts.headers {
        if *name != header::HOST && *name != header::CONTENT_LENGTH {
            outbound = outbound.header(name, value);
        }
    }

    let backend_response = match outbound.body(body_bytes).send().await {
        Ok(response) => response,
        Err(error) => {
            return (
                StatusCode::BAD_GATEWAY,
                format!("Backend proxy request failed: {error}"),
            )
                .into_response();
        }
    };

    build_proxy_response(backend_response).await
}

async fn build_proxy_response(response: reqwest::Response) -> Response<Body> {
    let status = response.status();
    let headers = response.headers().clone();
    let body = match response.bytes().await {
        Ok(bytes) => bytes,
        Err(error) => {
            return (
                StatusCode::BAD_GATEWAY,
                format!("Could not read backend response: {error}"),
            )
                .into_response();
        }
    };

    let mut builder = Response::builder().status(status);
    if let Some(target_headers) = builder.headers_mut() {
        for (name, value) in &headers {
            if *name != header::TRANSFER_ENCODING
                && *name != header::CONTENT_LENGTH
                && *name != header::CONNECTION
            {
                target_headers.insert(name, value.clone());
            }
        }
    }

    builder
        .body(Body::from(body))
        .unwrap_or_else(|error| (StatusCode::BAD_GATEWAY, error.to_string()).into_response())
}

async fn parse_json_response<T>(response: reqwest::Response) -> Result<T, FrontendError>
where
    T: DeserializeOwned,
{
    let status = response.status();
    let body = response.bytes().await.map_err(|error| {
        FrontendError::new(format!("Could not read backend response body: {error}"))
    })?;

    if !status.is_success() {
        let message = String::from_utf8_lossy(&body).to_string();
        return Err(FrontendError::new(format!(
            "Backend returned {}: {}",
            status,
            message.trim()
        )));
    }

    serde_json::from_slice::<T>(&body)
        .map_err(|error| FrontendError::new(format!("Could not parse backend JSON: {error}")))
}
