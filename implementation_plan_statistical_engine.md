# Statistical Engine Implementation Plan & Technical Schema

## 1. Overall Architecture

- **Frontend (Next.js + TypeScript)** – UI for dataset upload, configuration of preprocessing, selection of statistical tests, and visualisation of results. Communicates with backend via a **REST/GraphQL** API.
- **Backend (FastAPI + Python)** – Orchestrates the statistical engine, handles authentication, job scheduling, and serves API endpoints.
- **Statistical Engine (Python package `statengine`)** – Core library containing modules for ingestion, validation, profiling, preprocessing, EDA, test‑selection, assumption checking, computation, interpretation and visualisation.
- **Task Queue (Celery + Redis)** – Runs heavy‑weight jobs (large file parsing, model fitting, PDF report generation) asynchronously.
- **Database (PostgreSQL)** – Stores dataset metadata, variable profiles, preprocessing pipelines, analysis jobs, results, visualisation metadata and audit logs.
- **Object Storage (Cloudinary)** – Persists raw uploaded files, intermediate Parquet versions, generated charts (Plotly JSON) and PDF reports.

**Communication Flow**
1. UI uploads a file → `/api/datasets/upload` (multipart). Backend streams to object storage and creates a `Dataset` record.
2. An async Celery task `ingest_dataset` parses the file, extracts metadata, and creates a preview.
3. Front‑end polls `/api/datasets/{id}/profile` to get variable type detection & data‑quality report.
4. User configures preprocessing → `/api/datasets/{id}/preprocess`.
5. Preprocessing task stores a reproducible pipeline definition.
6. EDA, assumption checking, test selection and statistical computation are triggered via `/api/analysis/{job_id}/run`. Each step spawns a Celery worker and updates the `analysis_jobs` table.
7. Results, visualisations and natural‑language interpretation are persisted and returned to the UI.

**Technology Rationale**
- **FastAPI** – async, automatic OpenAPI docs, excellent integration with Pydantic for request validation.
- **Pandas / NumPy** – de‑facto data‑analysis stack.
- **SciPy, Statsmodels, scikit‑learn** – robust implementations of classic statistical tests and regression models.
- **pyreadstat** – native SPSS `.sav` reading.
- **Plotly Express** – interactive web‑ready charts.
- **Celery + Redis** – reliable distributed task queue with retry & progress.
- **PostgreSQL (JSONB)** – flexible schema for variable profiles & results.
- **Docker Compose** – reproducible dev environment.

## 2. Dataset Ingestion

| Step | Details |
|------|---------|
| **Upload Endpoint** | `POST /api/datasets/upload` – accepts `multipart/form-data`. Supported MIME types: `text/csv`, `application/vnd.openxmlformats‑officedocument.spreadsheetml.sheet`, `application/x‑spss‑sav`. Returns a UUID `dataset_id`.
| **Format Detection** | Use file extension + magic‑bytes (`python-magic`). Fallback to explicit MIME check.
| **Parsing** | - CSV/TSV → `pd.read_csv(..., engine='pyarrow', chunksize=100_000)` for large files.  
|  | - Excel → `pd.read_excel(..., engine='openpyxl')`.
|  | - SPSS → `pyreadstat.read_sav`.
| **Chunked Processing** | For > 500 k rows, stream chunks, compute incremental column statistics (count, sum, sumsq) to avoid loading whole file into memory.
| **Metadata Extraction** | Row count, column count, column names, detected format, file size, SHA‑256 checksum, first 100 rows preview (JSON).
| **Storage** | Raw file → object storage (key `datasets/{id}/raw.{ext}`).  
|  | After ingestion, store Parquet version (`datasets/{id}/parsed.parquet`) for fast downstream access.

## 3. Data Validation & Quality Report

- **Missing Values** – `df.isnull().sum()` per column.
- **Duplicate Records** – `df.duplicated().sum()`.
- **Invalid Types** – Attempt to cast each column to the detected type; collect failures.
- **Outliers** – Numeric: IQR, Z‑score (> 3). Categorical: rare levels (< 1%).
- **Consistency Checks** – For datetime columns, verify parsable ISO format.
- **Quality Report JSON** – Stored in `validation_reports` table; UI displays a summary table with warnings.

## 4. Variable Type Detection

Heuristics (implemented in `statengine.type_detection`):
- **Numeric** – `np.issubdtype(dtype, np.number)` and > 90 % non‑null.
- **Categorical** – `object` dtype with ≤ 20 unique values.
- **Ordinal** – Categorical with an explicit ordered list (detected via common keywords `low|medium|high|step`).
- **Binary** – Exactly two unique non‑null values.
- **Datetime** – `pd.to_datetime` succeeds for > 80 % rows.
- **Text** – String dtype with average length > 50 characters.
- **Identifier** – High‑cardinality string column where uniqueness ≈ row count.

**Ambiguity Handling** – Columns flagged as `ambiguous` are sent to the UI for manual override via `PATCH /api/datasets/{id}/variables`.

## 5. Data Preprocessing

All steps are encoded as a **scikit‑learn `Pipeline`** and persisted as JSON.

| Step | Library | Persisted Parameters |
|------|---------|----------------------|
| Missing‑value imputation | `SimpleImputer` | strategy, fill_value, affected columns |
| Outlier treatment | Custom transformer (IQR/Winsorization) | method, bounds, columns |
| Categorical encoding | `OneHotEncoder` / `OrdinalEncoder` | method, columns, handle_unknown |
| Scaling | `StandardScaler` / `MinMaxScaler` | columns |
| Power transformation | `PowerTransformer` (Yeo‑Johnson) | lambda_, columns |
| Feature selection | `SelectKBest`, `RFE` | k, estimator |
| Imbalanced data handling | `SMOTE` (imblearn) | sampling_strategy |
| Train/Test split | `sklearn.model_selection.train_test_split` | test_size, random_state |

The pipeline JSON is stored in `preprocess_pipelines` with a version number for reproducibility.

## 6. Exploratory Data Analysis (EDA)

`statengine.eda` produces:
- Descriptive stats per column (mean, median, std, min, max, nulls).
- Frequency tables for categoricals.
- Histogram bins / KDE for numerics.
- Pairwise correlation matrix (Pearson for numerics, Cramér's V for categoricals).
- Auto‑selected chart suggestions (see Section 13).
Results are returned as JSON and Plotly chart objects.

## 7. Statistical Test Selection Engine

A **rule‑based decision tree** (`statengine.test_selector`) that receives:
- Variable types of dependent and independent variables.
- Number of groups / levels.
- Whether observations are paired.
- Sample size, normality flags, variance homogeneity flag, independence flag.

### Decision Rules (excerpt)
| Situation | Recommended Test | Fallback |
|-----------|-------------------|----------|
| Two independent numeric groups, normal & equal variance | Student's *t*‑test | Mann‑Whitney U |
| Two independent numeric groups, non‑normal | Mann‑Whitney U | Kruskal‑Wallis (if > 2 groups) |
| Two paired numeric measurements | Paired *t*‑test | Wilcoxon signed‑rank |
| > 2 independent numeric groups, normal | One‑way ANOVA | Kruskal‑Wallis |
| Repeated measures > 2 groups | Repeated‑measures ANOVA | Friedman test |
| Two categorical variables | Chi‑square test of independence | Fisher's exact (if any expected < 5) |
| Binary outcome vs numeric predictor | Logistic regression | Fisher's exact (if very small sample) |
| Continuous outcome vs multiple predictors | Linear regression (OLS) | Robust regression |
| Correlation between two numerics | Pearson (normal) / Spearman (non‑normal) |
| Non‑parametric multivariate | Permutation MANOVA |

The engine outputs a **test ID**, required assumptions, and a **fallback test**.

## 8. Assumption‑Checking Layer

Implemented in `statengine.assumptions`. For each selected test, the corresponding checks run before computation:
- **Normality** – Shapiro‑Wilk (n ≤ 2000) else Anderson‑Darling.
- **Homoscedasticity** – Levene’s test.
- **Independence** – Durbin‑Watson (time series) or user‑provided design.
- **Multicollinearity** – VIF > 5 warning (for regression).
- **Linearity** – Residuals vs fitted scatter.
- **Influential observations** – Cook’s distance > 4/n.
If a critical assumption fails, the engine returns a **warning** with a recommended alternative test.

## 9. Statistical Computation Layer

- Primary libraries: **SciPy**, **Statsmodels**, **scikit‑learn**.
- For each test, a thin wrapper in `statengine.computation` calls the library function, captures the raw statistic object, and serialises the following to JSON: test statistic, p‑value, effect size, confidence interval, degrees of freedom, model coefficients (if applicable).
- Numerical accuracy ensured by using `np.float64` and deterministic random seeds for resampling methods.
- Complex designs (mixed‑effects, repeated measures) use `statsmodels.MixedLM` or the `pingouin` library.
- When a library lacks a specific metric (e.g., Cohen’s d for t‑test), compute manually.

## 10. Result Validation

- Verify convergence flags for regression (e.g., `model.fit()` success).
- Ensure p‑values ∈ [0, 1] and not NaN.
- Cross‑check that descriptive stats used for assumption checks match the stored dataset profile.
- Flag extreme effect sizes (> 2 SD) for manual review.
- Store a `validation_status` (`OK`, `WARN`, `FAIL`) in `analysis_results`.

## 11. Result Interpretation

Template‑driven NLG using **Jinja2** (`statengine.interpretation`). Templates contain placeholders for:
- Test name and purpose.
- Assumption outcomes.
- Primary statistic & p‑value (with plain‑language explanation of significance).
- Confidence interval interpretation.
- Effect size and its practical meaning.
- Recommendations (e.g., increase sample size, try non‑parametric alternative).
Internationalisation via JSON language packs.

## 12. Visualization Engine

- **Plotly Express** for interactive charts; server‑side renders static PNG via `kaleido` for PDF reports.
- Mapping rules (mirroring EDA):
  - Numeric → histogram, boxplot.
  - Numeric vs numeric → scatter with regression line.
  - Categorical vs numeric → violin/box.
  - Categorical vs categorical → stacked bar.
  - Regression diagnostics → residual plot, QQ‑plot, leverage plot.
  - Classification → ROC curve, confusion matrix heatmap.
- Chart objects (Plotly JSON) stored in object storage; thumbnail PNG stored alongside for quick UI listing.

## 13. Statistical Analysis Pipeline (Orchestrator)

```
Upload → Ingest → Validate → Profile → Detect Types →
Preprocess → EDA → Assumption Check → Test Selection →
Compute → Result Validation → Interpretation →
Visualization → Report Generation → Store & Return
```
The orchestrator (`statengine.pipeline`) records each stage in the `analysis_jobs` table with timestamps and status (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`).

## 14. Engine Schema (ER Diagram Summary)

- **datasets** (id, user_id, name, raw_path, format, rows, cols, created_at)
- **dataset_previews** (dataset_id, preview_json)
- **variable_profiles** (id, dataset_id, name, detected_type, user_override, stats_json)
- **validation_reports** (id, dataset_id, report_json)
- **preprocess_pipelines** (id, dataset_id, pipeline_json, version, created_at)
- **analysis_jobs** (id, dataset_id, pipeline_version, status, created_at, finished_at)
- **test_selections** (job_id, test_id, assumptions_json)
- **analysis_results** (job_id, result_json, validation_status)
- **visualizations** (result_id, chart_type, chart_json_path, thumbnail_path)
- **interpretations** (result_id, markdown_path)
- **reports** (job_id, pdf_path, generated_at)

## 15. API Design (Backend Endpoints)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/datasets/upload` | Upload raw CSV/Excel/SPSS file, returns `dataset_id` |
| `GET`  | `/api/datasets/{id}/profile` | Variable type detection + data‑quality report |
| `PATCH`| `/api/datasets/{id}/variables` | Manual override of detected variable types |
| `POST` | `/api/datasets/{id}/preprocess` | Submit preprocessing configuration, returns `pipeline_id` |
| `GET`  | `/api/datasets/{id}/preprocess/{pipeline_id}` | Retrieve stored pipeline definition |
| `POST` | `/api/analysis/{id}/eda` | Run EDA, returns summary & chart suggestions |
| `POST` | `/api/analysis/{id}/run` | Starts full statistical analysis pipeline, returns `job_id` |
| `GET`  | `/api/analysis/jobs/{job_id}` | Poll job status |
| `GET`  | `/api/analysis/jobs/{job_id}/results` | Fetch result JSON, visualisations, interpretation markdown |
| `GET`  | `/api/analysis/jobs/{job_id}/report` | Download PDF report |
| `DELETE`| `/api/datasets/{id}` | Cleanup dataset and associated artefacts |

All error responses follow **RFC 7807 Problem Details** with custom `type` identifiers (`invalid_file`, `validation_failed`, `assumption_violation`, `sample_size_error`, `method_not_implemented`).

## 16. Error Handling Strategies

- **Invalid Datasets** – 400 `invalid_file` with supported MIME list.
- **Unsupported Variable Types** – 422 with list of column names.
- **Assumption Violations** – 409 `assumption_violation` containing failed checks and suggested alternative.
- **Insufficient Sample Size** – 422 `sample_size_error` detailing required minimum.
- **Missing Required Variables** – 400 `missing_variables`.
- **Computational Errors** – 500 generic error, hide stack trace in production, log internally.
- **Unsupported Statistical Methods** – 501 `method_not_implemented`.

## 17. Testing Strategy

- **Unit Tests** – `pytest` for each module, using `hypothesis` for property‑based edge cases.
- **Statistical Correctness** – Synthetic datasets validated against `scipy.stats` reference outputs (t‑test, ANOVA, chi‑square, etc.).
- **Integration Tests** – Spin up Docker Compose stack, run end‑to‑end pipeline on a small CSV and assert final JSON shape.
- **Edge‑Case Tests** – All‑missing column, zero‑variance numeric, extremely imbalanced classes, > 1 M rows.
- **Regression Tests** – Snapshot JSON of results; nightly comparison against R `stats` package or Statsmodels.
- **Performance Benchmarks** – Ingestion of 1 M rows < 30 s, full pipeline on 200 k rows < 45 s.

## 18. Implementation Phases

| Phase | Features | Major Tasks | Dependencies | Definition of Done |
|-------|----------|------------|--------------|-------------------|
| **Phase 1 – Core Ingestion & Validation** | CSV upload, basic validation, variable profiling, simple t‑test & chi‑square | FastAPI scaffold, Celery queue, ingestion service, validation service, test selector (t‑test, chi‑square) | pandas, scipy, FastAPI, Celery, PostgreSQL | Upload → Validation → Test selection → Compute → JSON result works for small datasets |
| **Phase 2 – Multi‑Format & EDA** | Excel & SPSS ingestion, EDA service, Plotly chart generation | Add parsers for Excel/SPSS, implement `statengine.eda`, expose `/eda` endpoint, store chart JSON |
| **Phase 3 – Full Test Suite & Assumption Engine** | ANOVA, regression families, non‑parametric tests, assumption checking | Extend rule‑tree, add assumption modules, integrate with pipeline, update UI for suggested alternatives |
| **Phase 4 – Interpretation & Reporting** | Natural‑language interpretation, PDF report generation (WeasyPrint), chart thumbnails |
| **Phase 5 – Scalability & Production** | Chunked ingestion > 10 M rows, horizontal Celery workers, S3 storage, monitoring (Prometheus + Grafana) |

## 19. Folder / File Structure (Backend)

```
backend/
├─ app/
│   ├─ api/                     # FastAPI routers
│   │   ├─ datasets.py
│   │   ├─ analysis.py
│   │   └─ auth.py
│   ├─ core/                    # Core engine services
│   │   ├─ ingestion.py
│   │   ├─ validation.py
│   │   ├─ profiling.py
│   │   ├─ preprocessing.py
│   │   ├─ eda.py
│   │   ├─ test_selector.py
│   │   ├─ assumption_checker.py
│   │   ├─ computation.py
│   │   ├─ interpretation.py
│   │   └─ visualization.py
│   ├─ models/                  # SQLAlchemy ORM models (datasets, pipelines, jobs, results)
│   ├─ schemas/                 # Pydantic request/response models
│   ├─ workers/                 # Celery task definitions
│   └─ config.py
├─ tests/                       # pytest suite
├─ Dockerfile
├─ docker-compose.yml
└─ pyproject.toml
```

## 20. Final Architecture Diagram

*The diagram is stored as `architecture_diagram.png` in the artifact directory.*

---

**Next Steps**
1. Review the phase breakdown and confirm any missing priorities (e.g., preferred cloud storage provider, OAuth providers, deployment target).
2. Approve to start implementation of **Phase 1**.
3. Answer the open questions listed in the original `implementation_plan.md` if any clarification is needed.
