# Multi-Agent Orchestration

> For informational purposes only; not financial advice.

## 1. Overview

This project uses the [Microsoft Agent Framework (MAF)](https://learn.microsoft.com/en-us/agent-framework/overview/) as an **optional orchestration layer** for the backend analysis and recommendation pipelines.

In this codebase, MAF is installed as:

```bash
pip install agent-framework
```

and is declared directly in `backend/requirements.txt`:

```txt
agent-framework
```

The project uses MAF's **Functional Workflow API** rather than agent-to-agent chat orchestration. Concretely:

- `from agent_framework import workflow, step`
- `@workflow` marks the workflow entry point
- `@step` marks workflow steps
- the workflow body uses native Python async control flow such as `await` and `asyncio.gather(...)`

MAF is used here for **workflow coordination only**. All portfolio math stays in deterministic helper functions under `backend/src/tools/`:

- overlap and overlap matrix
- concentration
- asset allocation
- sector exposure
- fee analysis
- candidate scoring

That separation is a core design choice: **the framework coordinates execution, but it does not decide the financial logic**.

## 2. Conceptual Agent Architecture

The project specification describes four conceptual agents:

| Conceptual agent | Responsibility in the spec | Current implementation |
| --- | --- | --- |
| `PortfolioOrchestratorAgent` | Coordinates the end-to-end flow | The workflow entry points: `analysis_workflow(...)` and `recommendation_workflow(...)` |
| `ExistingPortfolioAnalysisAgent` | Computes overlap, concentration, asset allocation, sector exposure, and fees | Analysis workflow steps plus direct deterministic tool calls in `backend/src/workflows/analysis_workflow.py` |
| `CandidateUniverseAnalysisAgent` | Evaluates candidate funds and data quality | Candidate parsing plus the deterministic scoring inputs used by `score_candidates(...)` |
| `RecommendationAgent` | Produces ranked candidate outputs with score breakdowns | `score_candidates_for_existing_fund(...)` and final recommendation assembly |

Important nuance: **these are conceptual agents, not separate runtime MAF agent instances**. The current implementation models them as workflow steps and deterministic function calls instead of creating multiple independent conversational agents.

So the "multi-agent" part of this project is best understood as **multi-stage orchestration with agent-like responsibility boundaries**, not as LLM agents handing messages to each other.

## 3. The `@workflow` and `@step` Decorators

Both workflow modules use the same import pattern:

```python
try:
    from agent_framework import step, workflow
    AGENT_FRAMEWORK_AVAILABLE = True
except Exception:
    AGENT_FRAMEWORK_AVAILABLE = False

    def step(func):
        return func

    def workflow(func):
        return func
```

### `@step`

`@step` marks an async function as a workflow step. In this project it is used on units such as:

- `parse_and_normalise_funds`
- `compute_overlap_summary`
- `compute_concentration_summary`
- `compute_data_quality_summary`
- `parse_and_normalise_existing_funds`
- `parse_and_normalise_candidate_funds`
- `score_candidates_for_existing_fund`

Per the MAF Functional Workflow documentation, `@step` is an **opt-in** decorator that adds workflow-aware behavior such as event emission and checkpoint integration when the function is executed inside a running workflow. Outside a workflow, it behaves like a normal async function, which is why these steps remain easy to unit test.

### `@workflow`

`@workflow` marks the async workflow entry point:

- `analysis_workflow(request: AnalyseRequest)`
- `recommendation_workflow(request: RecommendRequest)`

With MAF available, the decorated function gains a `.run(...)` method. Without MAF, the no-op fallback decorator leaves it as a plain async function.

### Experimental status

The Functional Workflow API is currently documented by Microsoft as **experimental**, and the local test run surfaces the same status through an `ExperimentalWarning` on `@step`. That experimental status is one reason the project has strong fallback behavior.

## 4. Analysis Workflow — Step by Step

Source: `backend/src/workflows/analysis_workflow.py`

The analysis workflow is the clearest example of MAF being used as an orchestration shell around deterministic portfolio analytics.

### Step 1: `parse_and_normalise_funds`

```python
@step
async def parse_and_normalise_funds(symbols: list[str]) -> list[NormalisedFund]:
    return normalise_holdings(_get_fund_inputs(symbols))
```

What it does:

1. Receives the list of `existing_funds` symbols from the request
2. Looks up holdings from `STUB_HOLDINGS`
3. Builds `FundInput` objects
4. Passes them to `normalise_holdings(...)`

This step is deterministic. Unknown symbols still become `FundInput` records, but with empty holdings.

### Step 2: parallel overlap + concentration

The pipeline first parses once, then runs two independent analyses concurrently:

```python
normalised = await parse_and_normalise_funds(request.existing_funds)
overlap_result, concentration_result = await asyncio.gather(
    compute_overlap_summary(normalised),
    compute_concentration_summary(normalised, request.allocations),
)
```

#### `compute_overlap_summary`

This step:

- calls `compute_overlap_matrix(funds)`
- constructs pairwise `OverlapPair` entries using `compute_overlap(...)`
- sorts overlap pairs by weighted overlap descending
- returns:
  - an `OverlapMatrix`
  - the top 10 pair overlaps

This is the implementation of the conceptual **existing portfolio overlap analysis** agent boundary.

#### `compute_concentration_summary`

This step:

- calls `compute_concentration(funds, allocations)`
- converts the deterministic result into the API response model
- returns:
  - top holdings
  - total ticker count
  - top-10 combined weight

This is the implementation of the conceptual **concentration analysis** part of existing portfolio analysis.

### Step 3: `compute_data_quality_summary`

```python
data_quality = await compute_data_quality_summary(request.existing_funds)
```

This step delegates to `_check_data_quality(...)`, which:

- reads `STUB_DATA_TIMESTAMPS`
- counts holdings for each fund
- marks data as stale when older than 90 days
- treats missing or invalid timestamps as stale

Returned fields include:

- `symbol`
- `last_updated`
- `is_stale`
- `holdings_count`

### Step 4: X-Ray analysis (direct deterministic calls)

After the step-based portion, the workflow performs three synchronous deterministic calculations:

```python
asset_alloc = compute_asset_allocation(normalised, request.allocations)
sector_exp = compute_sector_exposure(normalised, request.allocations)
fee_result = compute_fee_analysis(normalised, request.allocations)
```

These are not currently decorated with `@step`. They run directly inside the workflow function because the code treats them as straightforward deterministic computations rather than distinct checkpointable workflow stages.

This portion corresponds to the project's "Portfolio X-Ray"-style analysis:

- **Asset allocation**: Equity / Fixed Income / Cash style breakdown
- **Sector exposure**: portfolio and per-fund sector mix
- **Fee analysis**: per-fund expense ratios plus portfolio-weighted expense ratio and estimated annual cost per \$10k

### Final assembly

The workflow returns a full `AnalysisResponse` containing:

- overlap matrix
- concentration summary
- top overlaps
- data quality
- asset allocation
- sector exposure
- fee analysis
- disclaimer
- timestamp

The last two fields are always appended:

```python
disclaimer=DISCLAIMER,
timestamp=datetime.now(timezone.utc).isoformat(),
```

That keeps the workflow aligned with the application's safety requirement:

> For informational purposes only; not financial advice.

## 5. Recommendation Workflow — Step by Step

Source: `backend/src/workflows/recommendation_workflow.py`

The recommendation workflow uses the same orchestration style, but the main unit of work is candidate scoring.

### Step 1: parallel parsing

Existing funds and candidate funds are parsed concurrently:

```python
existing_funds, candidate_funds = await asyncio.gather(
    parse_and_normalise_existing_funds(request.existing_funds),
    parse_and_normalise_candidate_funds(request.candidate_funds),
)
```

Each parse step:

- cleans and uppercases symbols
- loads stub holdings
- creates `FundInput`
- normalises into `NormalisedFund`

This is the current implementation of the conceptual:

- `ExistingPortfolioAnalysisAgent` input preparation
- `CandidateUniverseAnalysisAgent` input preparation

### Step 2: parallel scoring across existing funds

Once both fund sets are ready, the workflow scores all candidates for each existing fund in parallel:

```python
scored_results = await asyncio.gather(
    *(
        score_candidates_for_existing_fund(existing_fund, candidate_funds)
        for existing_fund in existing_funds
    )
)
```

Each `score_candidates_for_existing_fund(...)` call:

1. takes one existing fund
2. scores every candidate against it via `score_candidates(...)`
3. converts tool-layer results into API response models
4. returns `(existing_symbol, [scored candidates...])`

### What the scoring tool does

The workflow itself does not invent scores. It delegates to the deterministic scoring tool in `backend/src/tools/scoring.py`, which applies the project's four-part scoring model:

- **OverlapReduction**: `0–50`
- **Performance**: `0–40`
- **DataQualityPenalty**: `0 to -20`
- **CostPenalty**: `0 to -10`

Current implementation details:

- overlap reduction is based on weighted overlap inversion
- performance blends 1y / 3y / 5y stub performance data
- stale or missing timestamps reduce the score
- higher expense ratios create a penalty

The workflow simply packages the results into:

- `symbol`
- `total_score`
- `breakdown`
- `explanation`

### Final assembly

The final `RecommendResponse` is a dictionary keyed by the existing fund symbol:

```python
RecommendResponse(
    recommendations={symbol: scored for symbol, scored in scored_results},
    disclaimer=DISCLAIMER,
    timestamp=datetime.now(timezone.utc).isoformat(),
)
```

So for a request containing `["SPY", "QQQ"]`, the output shape is effectively:

```json
{
  "recommendations": {
    "SPY": [...],
    "QQQ": [...]
  }
}
```

## 6. Parallelism Patterns

The most important MAF-related implementation detail is that the project uses the **Functional Workflow API plus native `asyncio.gather(...)`** for concurrency.

### Analysis workflow parallelism

```python
overlap_result, concentration_result = await asyncio.gather(
    compute_overlap_summary(normalised),
    compute_concentration_summary(normalised, request.allocations),
)
```

Why these run in parallel:

- both depend on the same normalised inputs
- neither mutates shared state
- neither depends on the other's output

### Recommendation workflow parallelism

#### Parallel parse

```python
existing_funds, candidate_funds = await asyncio.gather(
    parse_and_normalise_existing_funds(request.existing_funds),
    parse_and_normalise_candidate_funds(request.candidate_funds),
)
```

#### Parallel scoring

```python
scored_results = await asyncio.gather(
    *(
        score_candidates_for_existing_fund(existing_fund, candidate_funds)
        for existing_fund in existing_funds
    )
)
```

### Why this matters

This achieves the main practical benefit of "multi-agent" orchestration in this codebase:

- independent stages execute concurrently
- orchestration remains explicit and readable
- deterministic calculations stay isolated
- the workflow stays close to normal Python

### Important clarification

The project spec mentions MAF orchestration patterns such as `HandoffBuilder` and `ConcurrentBuilder`. The current code **does not use those graph-builder APIs**. Instead, it uses the lighter Functional Workflow API and expresses concurrency with `asyncio.gather(...)` directly.

That is still valid MAF usage; it is simply the simpler workflow style.

## 7. Fallback Strategy

This is the most important operational detail of the MAF integration.

The project has **two layers of fallback**:

1. **import-time fallback** when `agent_framework` is unavailable
2. **route-time fallback** when workflow execution fails

### 7.1 Feature flag: `USE_WORKFLOWS`

Source: `backend/src/core/config.py`

```python
@property
def use_workflows(self) -> bool:
    return os.environ.get("USE_WORKFLOWS", "false").lower() == "true"
```

Key points:

- controlled entirely by environment variable
- default is `false`
- workflow orchestration is opt-in

If `USE_WORKFLOWS` is not enabled, the API routes do **not** attempt MAF execution at all.

### 7.2 Import-time fallback when MAF is missing

Both workflow files wrap the import:

```python
try:
    from agent_framework import step, workflow
    AGENT_FRAMEWORK_AVAILABLE = True
except Exception:
    AGENT_FRAMEWORK_AVAILABLE = False

    def step(func):
        return func

    def workflow(func):
        return func
```

This means:

- the module still imports cleanly even if `agent-framework` is not installed
- decorated functions still exist
- they behave like ordinary async functions
- the application does not crash just because MAF is absent

This is a strong compatibility pattern.

### 7.3 Route-time fallback when workflow execution fails

Source: `backend/src/api/routes/analyse.py`

```python
if settings.use_workflows:
    try:
        return await analysis_workflows.execute_analysis_workflow(request)
    except Exception as exc:
        logger.warning(
            "Analysis workflow failed; falling back to direct tools: %s",
            exc,
        )

return _build_analysis_response(request)
```

Source: `backend/src/api/routes/recommend.py`

```python
if settings.use_workflows:
    try:
        return await recommendation_workflows.execute_recommendation_workflow(request)
    except Exception as exc:
        logger.warning(
            "Recommendation workflow failed; falling back to direct tools: %s",
            exc,
        )

return _build_recommendation_response(request)
```

This gives the backend a graceful degradation path:

- try workflow orchestration first
- if it fails, log a warning
- recompute the response directly with deterministic functions

### 7.4 Why the fallback is robust

There are actually three successful execution paths:

| Scenario | Result |
| --- | --- |
| `USE_WORKFLOWS=false` | Route immediately uses direct deterministic builders |
| `USE_WORKFLOWS=true` and MAF works | Route uses `execute_*_workflow(...)` |
| `USE_WORKFLOWS=true` but workflow layer fails | Route logs warning and falls back to direct builders |

There is also a subtle hybrid case:

| Scenario | Result |
| --- | --- |
| `USE_WORKFLOWS=true` but `agent_framework` import failed | No-op decorators leave plain async functions in place; execute wrappers call them directly |

So even when the dependency is missing, the backend can still behave correctly.

## 8. Execution Model

The execution wrappers are where the MAF/non-MAF bridge is implemented.

### Analysis wrapper

```python
async def execute_analysis_workflow(request: AnalyseRequest) -> AnalysisResponse:
    if hasattr(analysis_workflow, "run"):
        result = await analysis_workflow.run(request)
        outputs = result.get_outputs()
        if outputs:
            return outputs[-1]
        raise RuntimeError("Analysis workflow completed without an output")

    return await analysis_workflow(request)
```

### Recommendation wrapper

```python
async def execute_recommendation_workflow(request: RecommendRequest) -> RecommendResponse:
    if hasattr(recommendation_workflow, "run"):
        result = await recommendation_workflow.run(request)
        outputs = result.get_outputs()
        if outputs:
            return outputs[-1]
        raise RuntimeError("Recommendation workflow completed without an output")

    return await recommendation_workflow(request)
```

### How this works

When MAF decorates the function, the workflow object exposes `.run(...)`. The wrapper then:

1. calls `.run(request)`
2. receives a MAF workflow run result
3. extracts outputs with `get_outputs()`
4. returns the final output object

If `.run` does not exist, the wrapper simply awaits the workflow function directly.

### Why `outputs[-1]`?

The wrapper assumes the workflow's final emitted output is the response object the route needs. If the workflow completes without outputs, the wrapper raises a `RuntimeError`, which is then caught by the route-level fallback handler when `USE_WORKFLOWS=true`.

## 9. Testing Workflows

Source: `backend/tests/test_workflows.py`

The workflow test suite validates both correctness and resilience.

### Direct pipeline tests

#### `test_analysis_pipeline_direct`

This test calls:

```python
response = await analysis_workflows.run_analysis_pipeline(request)
```

Then it recomputes expected values using deterministic tools:

- `normalise_holdings(...)`
- `compute_overlap_matrix(...)`
- `compute_concentration(...)`

It verifies that the workflow pipeline matches the direct calculations.

#### `test_recommendation_pipeline_direct`

This test calls:

```python
response = await recommendation_workflows.run_recommendation_pipeline(request)
```

Then it recomputes expected ranking data using:

- `normalise_holdings(...)`
- `score_candidates(...)`

Again, the workflow output must match the deterministic tool layer.

### Execution-wrapper tests

#### `test_analysis_workflow_execution`

Validates:

- `execute_analysis_workflow(...)` returns a valid response
- the response contains the expected funds
- the disclaimer is present

#### `test_recommendation_workflow_execution`

Validates:

- `execute_recommendation_workflow(...)` returns a valid response
- the response is keyed by existing fund symbol
- the disclaimer is present

### Route fallback tests

#### `test_analyse_route_falls_back_when_workflow_fails`

This test:

1. sets `USE_WORKFLOWS=true`
2. monkeypatches `execute_analysis_workflow` to raise `RuntimeError`
3. calls the route
4. verifies that a valid direct response is still returned

#### `test_recommend_route_falls_back_when_workflow_fails`

This test repeats the same resilience pattern for recommendations.

### What the tests prove

Together, these tests verify:

- direct workflow pipelines are correct
- execution wrappers work
- route-level fallback works
- disclaimer and timestamps remain present in workflow responses

## 10. Adding New Workflow Steps

When extending the system, follow the current pattern.

### Step 1: keep business logic deterministic

Put new calculations in `backend/src/tools/`, not inside workflow control code.

Good examples:

- parsing and normalisation helpers
- new metrics
- new scoring components
- quality checks

### Step 2: wrap orchestration boundaries in `@step`

Example:

```python
@step
async def compute_new_metric(funds: list[NormalisedFund]) -> NewMetricResult:
    return deterministic_new_metric(funds)
```

### Step 3: call the step from the pipeline

```python
@workflow
async def analysis_workflow(request: AnalyseRequest) -> AnalysisResponse:
    normalised = await parse_and_normalise_funds(request.existing_funds)
    metric = await compute_new_metric(normalised)
    ...
```

### Step 4: use `asyncio.gather(...)` for independent work

If a new step does not depend on another step's output, run them together:

```python
metric_a, metric_b = await asyncio.gather(
    compute_metric_a(normalised),
    compute_metric_b(normalised),
)
```

### Step 5: keep fallback parity

This project has both:

- workflow pipelines in `backend/src/workflows/`
- direct response builders in `backend/src/api/routes/`

If you add a new output field, update both paths or extract shared assembly code so that:

- workflow mode
- non-workflow mode
- fallback mode

all return the same shape.

### Step 6: add tests

Follow the existing pattern:

- direct pipeline test
- execution wrapper test
- fallback route test when relevant

## 11. Design Decisions

### Deterministic tools + MAF orchestration

This project avoids LLM-based financial calculations on purpose.

Why:

- overlap, concentration, fee, and scoring logic are formula-based
- deterministic tools are testable and auditable
- responses remain explainable
- there is less risk of fabricated outputs

MAF is therefore used for **control flow**, not inference.

### Fallback is mandatory because the workflow API is experimental

The codebase explicitly treats MAF as helpful but non-essential:

- import fallback prevents startup failures
- route fallback prevents request failures
- direct deterministic builders remain the source of truth

That is a pragmatic choice for production safety.

### Workflows are opt-in via environment variable

`USE_WORKFLOWS=false` by default means:

- simpler local startup
- no forced dependency on workflow orchestration
- easier debugging of deterministic behavior
- safer rollout of an experimental framework

### Functional Workflow API was chosen because it matches the problem

This backend has:

- a small number of clear stages
- explicit data dependencies
- straightforward concurrency opportunities
- no need for autonomous agent planning

So the Functional Workflow API is a good fit:

- less boilerplate than graph builders
- easy to read
- easy to test
- easy to fall back from

### Why not separate runtime agents?

At the moment, the portfolio analysis domain in this repo is mostly:

- parse data
- normalise holdings
- run formulas
- package results

That does not require multiple conversational agents negotiating with each other. The code still preserves agent-like separation of responsibilities, but it implements those boundaries as workflow steps and deterministic functions.

## Summary

In this project, Microsoft Agent Framework is used as a **thin orchestration layer** over deterministic finance-related tooling.

The key takeaways are:

- MAF is installed as `agent-framework`
- the project uses the Functional Workflow API with `@workflow` and `@step`
- analysis and recommendation pipelines are the workflow entry points
- concurrency is expressed with `asyncio.gather(...)`
- computation stays in deterministic tools
- `USE_WORKFLOWS` makes orchestration opt-in
- both import-time and route-time fallbacks protect reliability

That gives the application the structure of a multi-agent system while keeping the actual calculations transparent, testable, and safe.
