# AI-Powered Data Analysis & Visualization Platform — Implementation Roadmap

> Derived from [SRS_Data_Analysis_Platform.md](file:///c:/projects/ai-analytics/SRS_Data_Analysis_Platform.md)

---

## Technology Stack (Confirmed)

| Purpose | Tool |
|---|---|
| Frontend Framework | Next.js 14+ (App Router), TypeScript, Tailwind CSS |
| Charts / Visualization | Recharts |
| Backend (Data / ML) | FastAPI, Python 3.11+ |
| Database | **Neon DB** (Serverless PostgreSQL) |
| ORM | Prisma (with `@prisma/adapter-neon` serverless driver) |
| Authentication | Better Auth |
| AI Chatbot / Interpretation | OpenAI API |
| Package Manager (JS) | npm |
| Package Manager (Python) | uv |
| Containerization | Docker Compose (backend only; frontend deploys to Vercel) |
| CI/CD | GitHub Actions |
| Code Quality | ESLint, Prettier (frontend) · Ruff (backend) |

---

## Repository Structure (Monorepo)

```
ai-analytics/
├── frontend/                # Next.js app
│   ├── app/                 # App Router pages & layouts
│   │   ├── (auth)/          # Auth pages (login, signup)
│   │   ├── (dashboard)/     # Protected dashboard routes
│   │   ├── api/             # API routes (auth handler, proxy)
│   │   └── layout.tsx
│   ├── components/          # Reusable UI components
│   │   ├── ui/              # Primitives (Button, Card, Modal…)
│   │   ├── charts/          # Recharts wrappers
│   │   ├── data/            # Data table, upload, preview
│   │   └── chat/            # AI chatbot widget
│   ├── lib/                 # Utilities (prisma client, auth, api helpers)
│   ├── prisma/              # Schema & migrations
│   ├── public/
│   ├── styles/
│   └── package.json
│
├── backend/                 # FastAPI Python service
│   ├── app/
│   │   ├── main.py          # FastAPI entry point
│   │   ├── api/
│   │   │   └── routers/     # Endpoint routers (eda, preprocess, train…)
│   │   ├── schemas/         # Pydantic request/response models
│   │   ├── services/        # Business logic (ML pipelines, EDA)
│   │   ├── core/            # Config, security, dependencies
│   │   └── models/          # Serialized model storage helpers
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
│
├── docker-compose.yml       # Backend + Redis (dev)
├── .github/workflows/       # CI/CD pipelines
├── .env.example
└── README.md
```

---

## Phase 1 — Project Bootstrap & Infrastructure

**Goal:** Scaffolded monorepo, database connected, dev servers running, CI green.

### 1.1 Repository & Tooling Setup
- Initialize Git repo with `.gitignore` (Node, Python, `.env`)
- Create `frontend/` via `npx -y create-next-app@latest ./` (TypeScript, Tailwind, App Router, ESLint)
- Create `backend/` with `uv init` + FastAPI scaffold
- Add ESLint + Prettier config (frontend), Ruff config (backend)
- Add Husky + lint-staged for pre-commit hooks

### 1.2 Neon DB + Prisma Setup
- Create a Neon project → copy **pooled** and **direct** connection strings
- Install Prisma + Neon serverless driver:
  ```bash
  npm install @prisma/client @prisma/adapter-neon @neondatabase/serverless
  npm install prisma --save-dev
  ```
- `npx prisma init` → configure `schema.prisma`:
  ```prisma
  datasource db {
    provider  = "postgresql"
    url       = env("DATABASE_URL")          // pooled
    directUrl = env("DATABASE_URL_UNPOOLED") // direct (migrations)
  }

  generator client {
    provider        = "prisma-client-js"
    previewFeatures = ["driverAdapters"]
  }
  ```
- Create `lib/prisma.ts` singleton using `PrismaNeon` adapter
- `.env` with `DATABASE_URL`, `DATABASE_URL_UNPOOLED`

### 1.3 Backend Scaffold
- `pyproject.toml` with FastAPI, uvicorn, pandas, scikit-learn, python-multipart, openai
- `/health` endpoint returning `{"status": "ok"}`
- Docker Compose file for backend + Redis 7

### 1.4 CI Pipeline (GitHub Actions)
- Lint frontend (ESLint) + backend (Ruff)
- Type-check frontend (`tsc --noEmit`)
- Run backend tests (`pytest`)
- Run Prisma migration check

### ✅ Phase 1 Gate
| Check | Criteria |
|---|---|
| `npm run dev` | Next.js compiles, loads in browser |
| `uvicorn` | FastAPI docs at `/docs`, `/health` returns 200 |
| Prisma | `npx prisma migrate dev` succeeds against Neon |
| CI | Pipeline green on push |

---

## Phase 2 — Authentication & User Management

**Goal:** Users can sign up, log in, and access role-gated pages.

### 2.1 Prisma Schema — Auth Models
```prisma
model User {
  id        String   @id @default(cuid())
  name      String?
  email     String   @unique
  role      Role     @default(USER)
  projects  Project[]
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}

enum Role {
  GUEST
  USER
  ADMIN
}

model Project {
  id        String   @id @default(cuid())
  name      String
  userId    String
  user      User     @relation(fields: [userId], references: [id])
  datasets  Dataset[]
  chatMessages ChatMessage[]
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}
```
> Better Auth will add its own session/account tables alongside these.

### 2.2 Better Auth Integration
- Install `better-auth`
- Create `lib/auth.ts`:
  - Email + password provider enabled
  - OAuth providers (GitHub, Google) — configurable
  - Prisma database adapter pointing to Neon
- Create API route `app/api/auth/[...all]/route.ts`
- Create `lib/auth-client.ts` for client-side hooks (`useSession`)

### 2.3 Frontend Auth Pages
- `/login` — email/password + OAuth buttons
- `/signup` — registration form with validation
- `/forgot-password` — password reset flow
- Middleware (`middleware.ts`) to protect `/dashboard/*` routes
- Redirect unauthenticated users to `/login`

### 2.4 Role-Based Access Control
- Admin middleware on `/admin/*` routes
- Guest vs Registered feature flags (upload limits, saved projects)
- Admin panel page stub (`/admin/users`)

### ✅ Phase 2 Gate
| Check | Criteria |
|---|---|
| Sign up | New user created in Neon, session established |
| Login/Logout | Session cookies set/cleared correctly |
| Protected route | Unauthenticated → redirected to `/login` |
| Role guard | Non-admin cannot access `/admin/*` |
| OAuth | At least one social provider works end-to-end |

---

## Phase 3 — Dataset Upload & Management

**Goal:** Users can upload CSV/XLSX files, preview data, and manage datasets within projects.

### 3.1 Prisma Schema — Dataset Model
```prisma
model Dataset {
  id          String   @id @default(cuid())
  name        String
  fileName    String
  fileType    String   // csv | xlsx | google_sheets
  fileSizeBytes Int
  fileUrl     String   // storage path or URL
  projectId   String
  project     Project  @relation(fields: [projectId], references: [id])
  columns     Json?    // cached column metadata
  rowCount    Int?
  status      DatasetStatus @default(UPLOADED)
  createdAt   DateTime @default(now())
}

enum DatasetStatus {
  UPLOADED
  PROCESSING
  READY
  ERROR
}
```

### 3.2 File Upload API (Backend)
- `POST /api/datasets/upload` — accepts multipart file (CSV, XLSX)
- File validation: type check, size ≤ 50 MB
- Save file to local storage (Phase 1) → later to cloud storage (S3/GCS)
- Parse file with pandas → extract column names, dtypes, row count
- Return dataset metadata + first 100 rows as JSON preview

### 3.3 Google Sheets Integration
- `POST /api/datasets/google-sheets` — accepts sheet URL
- Use Google Sheets API to read data
- Convert to DataFrame internally, same processing pipeline

### 3.4 Frontend — Upload & Preview UI
- **Upload page** (`/dashboard/projects/[id]/upload`)
  - Drag-and-drop zone with file type icons
  - Progress bar during upload
  - Google Sheets URL input tab
- **Data preview component**
  - Paginated table showing raw data
  - Column headers with data type badges
  - Row count & file info summary

### 3.5 Dataset Management
- List all datasets in a project
- Delete dataset (cascade cleanup)
- Re-upload / replace dataset

### ✅ Phase 3 Gate
| Check | Criteria |
|---|---|
| CSV upload | File uploaded, parsed, metadata stored in Neon |
| XLSX upload | Excel file parsed correctly |
| Size limit | Files > 50 MB rejected with clear error |
| Preview | First 100 rows render in data table |
| Google Sheets | Sheet URL fetched and previewed |

---

## Phase 4 — Exploratory Data Analysis (EDA)

**Goal:** Auto-generated statistical summaries, column insights, and suggested visualizations.

### 4.1 EDA Backend Service
- `POST /api/eda/summary` — receives dataset ID, returns:
  - **Summary statistics** per column: mean, median, std, min, max, null count, dtype
  - **Distributions**: histogram bins for numeric columns
  - **Unique values**: counts for categorical columns
  - **Correlation matrix**: pairwise Pearson correlation (numeric columns)
  - **Missing value heatmap data**

### 4.2 Auto-Suggested Charts
- Backend analyzes column types and relationships:
  - Numeric → histogram, box plot
  - Numeric × Numeric → scatter plot
  - Categorical → bar chart (frequency)
  - Correlation → heatmap
- Returns chart suggestions as structured JSON (chart type, x/y columns, title)

### 4.3 Frontend — EDA Dashboard
- **Summary cards**: dataset shape, dtypes breakdown, total nulls
- **Column explorer**: click a column → see distribution chart, stats, unique values
- **Correlation heatmap**: interactive Recharts heatmap
- **Auto-suggested charts panel**: rendered chart carousel
- **AI Interpretation** (Phase 7 integration point — show placeholder)

### ✅ Phase 4 Gate
| Check | Criteria |
|---|---|
| Summary stats | All numeric/categorical columns summarized correctly |
| Histograms | Distribution charts render for numeric columns |
| Correlation | Heatmap renders, values match pandas output |
| Auto-suggest | At least 3 chart types suggested for a mixed dataset |
| Performance | EDA on a 50 MB CSV completes in < 5 seconds |

---

## Phase 5 — Data Preprocessing

**Goal:** Users configure and apply cleaning/transformation steps via a guided UI.

### 5.1 Preprocessing Backend Service
- `POST /api/preprocess/apply` — receives dataset ID + config:
  ```json
  {
    "missing_values": { "strategy": "mean", "columns": ["age", "income"] },
    "encoding": { "method": "one_hot", "columns": ["city", "gender"] },
    "scaling": { "method": "standard", "columns": ["age", "income"] },
    "outliers": { "method": "iqr", "columns": ["income"], "action": "remove" },
    "train_test_split": { "test_size": 0.2, "random_state": 42 }
  }
  ```
- Apply steps sequentially using pandas + scikit-learn
- Return transformed dataset preview + transformation summary (rows removed, new columns, etc.)
- Store preprocessed data & config for reproducibility

### 5.2 Frontend — Preprocessing Wizard
Step-by-step wizard UI:

1. **Missing Values** — per-column strategy selector (drop, mean, median, mode)
2. **Encoding** — select categorical columns → label or one-hot encoding
3. **Scaling** — select numeric columns → normalization or standardization
4. **Outlier Detection** — IQR/Z-score method → preview flagged rows → confirm removal
5. **Train/Test Split** — slider for test ratio (10–40%), random seed input
6. **Review & Apply** — summary of all steps → apply button → show before/after comparison

### ✅ Phase 5 Gate
| Check | Criteria |
|---|---|
| Missing values | Nulls imputed correctly (verified against pandas) |
| Encoding | One-hot creates correct dummy columns |
| Scaling | StandardScaler produces μ=0, σ=1 |
| Outliers | IQR method flags and removes correct rows |
| Split | Train/test shapes match configured ratio |
| Idempotency | Applying same config twice produces identical results |

---

## Phase 6 — Model Selection, Training & Evaluation

**Goal:** Users select an ML task, pick an algorithm, train, and view results.

### 6.1 Model Registry (Backend)
```python
MODEL_REGISTRY = {
    "classification": {
        "logistic_regression": LogisticRegression,
        "decision_tree_classifier": DecisionTreeClassifier,
        "random_forest_classifier": RandomForestClassifier,
        "svm_classifier": SVC,
    },
    "regression": {
        "linear_regression": LinearRegression,
        "decision_tree_regressor": DecisionTreeRegressor,
        "random_forest_regressor": RandomForestRegressor,
    },
    "clustering": {
        "kmeans": KMeans,
        "dbscan": DBSCAN,
    },
}
```

### 6.2 Training Endpoint
- `POST /api/models/train` — receives:
  - Dataset ID, task type, algorithm, target column, hyperparameters
- Builds scikit-learn Pipeline (preprocessing + model)
- Trains on training set → evaluates on test set
- Returns metrics:
  - **Classification**: accuracy, precision, recall, F1, confusion matrix, ROC-AUC
  - **Regression**: R², RMSE, MAE, residual plot data
  - **Clustering**: silhouette score, cluster labels, inertia
- Serializes model with `joblib` → stores artifact path in DB

### 6.3 Prisma Schema — Training Run
```prisma
model TrainingRun {
  id            String   @id @default(cuid())
  projectId     String
  datasetId     String
  taskType      String   // classification | regression | clustering
  algorithm     String
  hyperparams   Json
  metrics       Json
  modelArtifact String?  // file path to serialized model
  status        String   @default("completed")
  createdAt     DateTime @default(now())
}
```

### 6.4 Frontend — Model Training UI
- **Task selection**: toggle between Classification / Regression / Clustering
- **Algorithm picker**: cards with algorithm names + brief descriptions
- **Smart mode** (optional): auto-recommend based on data characteristics
- **Hyperparameter form**: dynamic form based on selected algorithm (with defaults)
- **Training progress**: progress spinner → results panel
- **Results dashboard**:
  - Metric cards (accuracy, R², etc.)
  - Confusion matrix heatmap (classification)
  - Feature importance bar chart
  - Prediction vs Actual scatter (regression)
  - Cluster visualization (clustering)

### 6.5 Run Comparison
- Table comparing metrics across multiple training runs
- Side-by-side chart comparison
- "Best run" highlighting

### ✅ Phase 6 Gate
| Check | Criteria |
|---|---|
| Classification | Logistic Regression trains, confusion matrix correct |
| Regression | Linear Regression trains, R² matches sklearn output |
| Clustering | KMeans trains, silhouette score returned |
| Hyperparams | Custom params applied (e.g., `n_estimators=200`) |
| Comparison | 3+ runs display in comparison table |
| Artifacts | Model file saved, can be reloaded for prediction |

---

## Phase 7 — AI Interpretation & Chatbot

**Goal:** AI-powered plain-language insights and a context-aware chatbot.

### 7.1 AI Interpretation Service (Backend)
- `POST /api/ai/interpret` — accepts context (EDA stats, model metrics, dataset summary)
- Constructs prompt with structured data context
- Calls OpenAI API (GPT-4o) → returns interpretation
- Three modes:
  1. **EDA interpretation**: "Your data has a strong positive correlation between X and Y…"
  2. **Model interpretation**: "Your model achieved 92% accuracy. The most important feature…"
  3. **Recommendations**: "Consider removing outliers in column Z to improve…"

### 7.2 Chatbot Backend
- `POST /api/chat/message` — receives user message + project context
- Builds system prompt with:
  - Current pipeline stage
  - Dataset metadata (columns, dtypes, summary stats)
  - Latest model metrics (if available)
- Streams response via SSE (Server-Sent Events)
- Saves chat messages to DB

### 7.3 Prisma Schema — Chat
```prisma
model ChatMessage {
  id        String   @id @default(cuid())
  projectId String
  project   Project  @relation(fields: [projectId], references: [id])
  role      String   // user | assistant
  content   String
  createdAt DateTime @default(now())
}
```

### 7.4 Frontend — AI Features
- **Interpretation cards**: auto-generated insights shown after EDA and training
- **Chatbot widget**: floating bottom-right panel
  - Chat input with send button
  - Streaming message display
  - Message history (scrollable)
  - Context indicator ("Currently viewing: EDA results")
- **Suggested questions**: quick-action chips ("What does this correlation mean?")

### ✅ Phase 7 Gate
| Check | Criteria |
|---|---|
| EDA interpretation | Generates relevant plain-language summary |
| Model interpretation | Explains metrics in context |
| Recommendations | Suggests actionable next steps |
| Chatbot | Answers data-specific questions accurately |
| Streaming | Responses stream token-by-token |
| History | Chat history persisted and reloaded per project |
| Rate limiting | OpenAI calls rate-limited per user tier |

---

## Phase 8 — Visualization & Export

**Goal:** Interactive charts, downloadable reports, and exportable results.

### 8.1 Chart Builder (Frontend)
- **Interactive chart types** via Recharts:
  - Bar, Line, Scatter, Pie, Area, Heatmap
- **Chart configuration panel**: select columns for X/Y axes, color grouping, title
- **Chart gallery**: saved charts per project

### 8.2 Export Functionality
- **Chart export**: download as PNG (html2canvas) or PDF
- **Results report**: generate PDF with:
  - Dataset summary
  - EDA highlights
  - Preprocessing steps applied
  - Model metrics + visualizations
  - AI interpretation
- **Data export**: download preprocessed data as CSV
- Backend endpoint: `GET /api/export/report/{project_id}` → generates PDF

### ✅ Phase 8 Gate
| Check | Criteria |
|---|---|
| Charts | All 6 chart types render with real data |
| Interactivity | Hover tooltips, zoom, legend toggle work |
| PNG export | Chart downloads as high-res PNG |
| PDF report | Multi-page report generates with correct content |
| CSV export | Preprocessed data downloads correctly |

---

## Phase 9 — Admin Panel & User Management

**Goal:** Admins can manage users, monitor platform usage, and configure settings.

### 9.1 Admin Dashboard
- `/admin` — overview: total users, active projects, dataset uploads, API usage
- `/admin/users` — user table with search, filter by role, edit role, disable account
- `/admin/usage` — OpenAI API call logs, cost tracking per user
- `/admin/settings` — file size limits, rate limits, feature toggles

### 9.2 Guest/Free Tier Limits
- Max 3 datasets, 10 MB each
- No Google Sheets integration
- Limited chat messages per day (e.g., 10)
- Upgrade prompt UI

### ✅ Phase 9 Gate
| Check | Criteria |
|---|---|
| Admin access | Only ADMIN role can access `/admin/*` |
| User management | Admin can change user role, disable accounts |
| Usage stats | Dashboard shows accurate metrics |
| Tier limits | Guest user blocked after exceeding limits |

---

## Phase 10 — Polish, Performance & Security Hardening

**Goal:** Production-grade performance, security, and user experience.

### 10.1 Performance Optimization
- Next.js: dynamic imports, image optimization, route-level code splitting
- Backend: Redis caching for EDA results, model artifact caching
- Database: Prisma query optimization, proper indexes on Neon
- File processing: chunked upload for large files, progress streaming

### 10.2 Security Hardening
- HTTPS everywhere (Vercel handles frontend; backend behind reverse proxy)
- CSRF protection on all mutations
- Input sanitization (file uploads, chat messages)
- Rate limiting on API endpoints (per-user, per-IP)
- Data encryption at rest (Neon handles this natively)
- Secure session management (Better Auth defaults + HTTPOnly, SameSite cookies)
- `.env` audit — no secrets in code

### 10.3 UX Polish
- Loading skeletons across all data-heavy pages
- Error boundaries with friendly messages
- Toast notifications for async operations
- Responsive design audit (desktop + tablet breakpoints)
- Accessibility pass (keyboard nav, ARIA labels, contrast ratios)
- Wizard progress bar for the full pipeline flow

### 10.4 Error Handling & Reliability
- Auto-save pipeline progress (per step)
- Training run failure recovery (retry with same config)
- Graceful degradation when OpenAI API is down
- Global error logging (backend + frontend)

### ✅ Phase 10 Gate
| Check | Criteria |
|---|---|
| Lighthouse | Score ≥ 90 on Performance, Accessibility, Best Practices |
| Load test | Backend handles 50 concurrent EDA requests |
| Security | OWASP top-10 checklist reviewed |
| Error handling | All error states show user-friendly messages |
| Mobile | UI usable on tablet screens |

---

## Phase 11 — Deployment & CI/CD

**Goal:** Fully automated deployment pipeline, production environment live.

### 11.1 Frontend Deployment (Vercel)
- Connect GitHub repo → Vercel project
- Configure environment variables (Neon URLs, Better Auth secrets, OpenAI key)
- Enable preview deployments on PRs
- Custom domain setup

### 11.2 Backend Deployment
- Dockerize FastAPI service
- Deploy to cloud provider (Railway / Render / AWS ECS)
- Configure Redis instance (Upstash Redis for serverless, or managed Redis)
- Health check endpoint for monitoring
- Auto-scaling rules based on CPU/memory

### 11.3 CI/CD Pipeline (GitHub Actions)
```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline
on: [push, pull_request]

jobs:
  frontend:
    - Lint (ESLint)
    - Type check (tsc)
    - Build (next build)
    - Unit tests (Vitest)

  backend:
    - Lint (Ruff)
    - Unit tests (pytest)
    - Integration tests

  deploy:
    needs: [frontend, backend]
    if: github.ref == 'refs/heads/main'
    - Deploy frontend (Vercel auto-deploys)
    - Deploy backend (Docker push + deploy trigger)
    - Run Prisma migrations against production Neon
```

### 11.4 Monitoring & Observability
- Application monitoring (Vercel Analytics for frontend)
- Backend logging (structured JSON logs)
- Error tracking (Sentry)
- Uptime monitoring (Neon dashboard + external ping)
- OpenAI cost monitoring dashboard

### ✅ Phase 11 Gate
| Check | Criteria |
|---|---|
| Frontend | Live at production URL, HTTPS, assets loading |
| Backend | API reachable, `/health` returns 200 |
| Database | Neon production branch with migrations applied |
| CI/CD | Push to `main` triggers auto-deploy |
| Monitoring | Sentry capturing errors, uptime checks passing |

---

## Phase Summary & Timeline Estimate

| Phase | Description | Estimated Duration |
|---|---|---|
| **1** | Project Bootstrap & Infrastructure | 3–4 days |
| **2** | Authentication & User Management | 4–5 days |
| **3** | Dataset Upload & Management | 4–5 days |
| **4** | Exploratory Data Analysis (EDA) | 5–6 days |
| **5** | Data Preprocessing | 5–6 days |
| **6** | Model Selection, Training & Evaluation | 6–8 days |
| **7** | AI Interpretation & Chatbot | 5–6 days |
| **8** | Visualization & Export | 4–5 days |
| **9** | Admin Panel & User Management | 3–4 days |
| **10** | Polish, Performance & Security | 4–5 days |
| **11** | Deployment & CI/CD | 3–4 days |
| | **Total** | **~46–58 days** |

> [!IMPORTANT]
> Each phase has a **gate** — a set of pass/fail criteria that must be verified before starting the next phase. Do not skip gates.

---

## Open Questions

> [!IMPORTANT]
> Please clarify the following before we begin implementation:

1. **Neon DB Plan** — Are you on Neon's Free tier, or do you have a paid plan? This affects connection limits and branching features.
2. **OAuth Providers** — Which social login providers do you want? (GitHub, Google, both, or others?)
3. **File Storage** — For uploaded datasets, should we use local disk storage initially and migrate to cloud storage (S3/GCS) later, or set up cloud storage from Phase 1?
4. **Deployment Target** — Frontend on Vercel is assumed. For the backend, do you have a preference? (Railway, Render, AWS, GCP, self-hosted?)
5. **OpenAI Model** — Which OpenAI model for the chatbot? (GPT-4o, GPT-4o-mini for cost savings, or configurable per tier?)
6. **Redis** — Do you want Upstash (serverless Redis) or a managed Redis instance alongside the backend?
