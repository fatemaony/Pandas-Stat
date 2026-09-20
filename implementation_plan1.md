# Phase 1 — Repository Inspection & Sub-Phase 1.1 Proposal

## 1. Repository Findings

### Project Structure
The repository is a **Next.js 16.2.4** application (not a monorepo — all code lives at the root) using:
- **App Router** with Turbopack (`next dev --turbopack`)
- **TypeScript** with strict mode, `@/*` path alias
- **Tailwind CSS v4** + shadcn/ui (button, input, label, sonner)
- **Prisma 7.10** with `PrismaPg` adapter connecting to **Neon PostgreSQL**
- **Better-Auth 1.6.9** for authentication (email/password, Google, GitHub, magic link)
- **Cloudinary** for image uploads (avatar only, currently)
- **No Python code exists** — no `backend/`, no `stat-engine/`, no `requirements.txt`, no `pyproject.toml`
- **No testing framework** configured on the JS side (no vitest, jest, or testing-library)

### Environment
- **Windows OS**, PowerShell
- **Python 3.13.7** available via `py` launcher (`C:\WINDOWS\py.exe`)
- **`uv` is NOT installed** — must be installed before proceeding
- **`python` is NOT on PATH** — only `py` works
- **Node.js** is working (npm run dev is running)

### Existing Files of Interest

| File | Purpose |
|---|---|
| [`prisma/schema.prisma`](file:///c:/projects/ai-analytics/pandas-stat/prisma/schema.prisma) | Full schema — auth + dataset + statistical engine tables |
| [`lib/auth.ts`](file:///c:/projects/ai-analytics/pandas-stat/lib/auth.ts) | Better-Auth server config |
| [`lib/auth-client.ts`](file:///c:/projects/ai-analytics/pandas-stat/lib/auth-client.ts) | Better-Auth client hooks |
| [`lib/prisma.ts`](file:///c:/projects/ai-analytics/pandas-stat/lib/prisma.ts) | Prisma singleton with PrismaPg adapter |
| [`lib/permissions.ts`](file:///c:/projects/ai-analytics/pandas-stat/lib/permissions.ts) | RBAC (USER, ADMIN) |
| [`proxy.ts`](file:///c:/projects/ai-analytics/pandas-stat/proxy.ts) | Middleware protecting /profile, /admin/dashboard |
| [`app/api/auth/[...all]/route.ts`](file:///c:/projects/ai-analytics/pandas-stat/app/api/auth/%5B...all%5D/route.ts) | Better-Auth catch-all handler |
| [`implementation_plan.md`](file:///c:/projects/ai-analytics/pandas-stat/implementation_plan.md) | Full 11-phase roadmap (general platform) |
| [`implementation_plan_statistical_engine.md`](file:///c:/projects/ai-analytics/pandas-stat/implementation_plan_statistical_engine.md) | Detailed statistical engine architecture |

---

## 2. Existing Functionality

| Feature | Status |
|---|---|
| Authentication (email/password, OAuth, magic link) | ✅ Fully implemented |
| User roles (USER, ADMIN) | ✅ Working |
| Session management + cookie caching | ✅ Working |
| Email verification | ✅ Working |
| Profile page | ✅ Working |
| Admin dashboard page | ✅ Working (stub) |
| Prisma schema for datasets | ✅ Schema defined, but **NOT migrated** (see critical finding below) |
| Prisma schema for statistical engine models | ✅ Schema defined, but **NOT migrated** |
| Dataset upload API | ❌ Does not exist |
| Python backend | ❌ Does not exist |
| Any statistical computation | ❌ Does not exist |

### ⚠️ Critical Finding: Schema Drift

> [!WARNING]
> **The Prisma schema contains 15+ models (Dataset, DatasetPreview, VariableProfile, ValidationReport, AnalysisJob, etc.) but only ONE migration exists** (`20260508133716_authentication`), which only created the `users`, `sessions`, `accounts`, `verifications`, and `posts` tables.
>
> This means the dataset and statistical engine tables **do not exist in the database yet**. A new migration must be generated and applied before any Python code can read/write these tables.
>
> Additionally, the current schema has evolved significantly since the initial migration (e.g., User now has `role`, `banned`, `banReason`, `deletedAt` fields that aren't in the migration SQL). Better-Auth may have applied these via its own sync mechanism, but the dataset tables are definitely missing.

---

## 3. Missing Functionality (Phase 1 Scope)

| Component | Status |
|---|---|
| `uv` installed on system | ❌ Must install |
| `stat-engine/` directory with Python project | ❌ Must create |
| `pyproject.toml` + dependencies | ❌ Must create |
| FastAPI application scaffold | ❌ Must create |
| SQLAlchemy models mirroring Prisma tables | ❌ Must create |
| Database connection from Python | ❌ Must create |
| CSV ingestion service | ❌ Must create |
| Data validation service | ❌ Must create |
| Variable profiling service | ❌ Must create |
| Dataset preview service | ❌ Must create |
| API endpoints (upload, GET metadata, GET preview, GET validation, GET profiles) | ❌ Must create |
| Next.js → FastAPI proxy route | ❌ Must create |
| Prisma migration for dataset tables | ❌ Must run |
| Automated tests | ❌ Must create |

---

## 4. Conflicts Between Implementation Plans and Repository

| Topic | `implementation_plan.md` | `implementation_plan_statistical_engine.md` | Current Repo | Resolution |
|---|---|---|---|---|
| **Directory name** | `backend/` | `backend/` | Neither exists | Use `stat-engine/` per our approved plan |
| **Repo structure** | Monorepo with `frontend/` + `backend/` | Monorepo `backend/` | Flat Next.js at root (no `frontend/` subdir) | Keep Next.js at root, add `stat-engine/` alongside it |
| **File storage** | "Local Phase 1, cloud later" | "Cloudinary for raw files" | Cloudinary configured for avatars only | Use local storage for Phase 1 (approved) |
| **Celery/Redis** | Phase 1 includes basic setup | Phase 1 includes async tasks | Not installed | Skip for Phase 1 — synchronous processing (approved) |
| **Package name** | Not specified | `statengine` | N/A | Use `stat-engine` as the directory, `app` as the Python package |
| **Auth from Python** | Separate auth in FastAPI | Separate auth in FastAPI | Better-Auth in Next.js | Proxy pattern — Next.js verifies session, forwards `X-User-Id` (approved) |

> [!NOTE]
> No architectural conflicts require user approval. The approved implementation plan already resolves all these discrepancies.

---

## 5. Proposed Architecture (Phase 1)

```
Browser → Next.js (session check) → /api/stat-engine/[...path] → FastAPI :8000
                                                                      ↓
                                                              services layer
                                                         (ingestion/validation/
                                                          profiling/preview)
                                                                      ↓
                                                              PostgreSQL
                                                            (same Neon DB)
```

---

## 6. Sub-Phase Breakdown

I propose breaking Phase 1 into these independently reviewable sub-phases:

| # | Sub-Phase | Scope |
|---|---|---|
| **1.1** | Backend Foundation | Install uv, scaffold `stat-engine/`, pyproject.toml, FastAPI app, config, health endpoint |
| **1.2** | Database Connection + Models | SQLAlchemy models, DB session, Prisma migration for dataset tables |
| **1.3** | Auth Proxy | Next.js → FastAPI proxy route with session verification |
| **1.4** | CSV Ingestion Service | Upload endpoint, file save, CSV parse, checksum, metadata extraction |
| **1.5** | Validation Service | Data quality checks, structured validation report, persistence |
| **1.6** | Variable Profiling Service | Type detection, per-column statistics, persistence |
| **1.7** | Dataset Preview Service | First N rows, JSON preview, persistence |
| **1.8** | GET API Endpoints | Read endpoints for metadata, preview, validation, profiles |
| **1.9** | Automated Tests | Unit tests for all services, API integration tests |
| **1.10** | Security & Edge Cases | Filename sanitization, path traversal, size limits, unauthorized access tests |
| **1.11** | Final Phase 1 Review | End-to-end walkthrough, cleanup, documentation |

---

## 7. Sub-Phase 1.1 Proposal — Backend Foundation

### What it does
Sets up the Python project skeleton and a running FastAPI server with a health endpoint.

### Files to Create

| File | Purpose |
|---|---|
| `stat-engine/pyproject.toml` | Project metadata, Python ≥3.11, all dependencies |
| `stat-engine/app/__init__.py` | Package marker |
| `stat-engine/app/main.py` | FastAPI app, CORS, health endpoint |
| `stat-engine/app/config.py` | Pydantic `BaseSettings` for config |
| `stat-engine/.env.example` | Documented env var template |

### Files to Modify

| File | Change |
|---|---|
| [`.gitignore`](file:///c:/projects/ai-analytics/pandas-stat/.gitignore) | Add Python/uv ignores |

### Dependencies (pyproject.toml)

**Runtime:**
- fastapi
- uvicorn[standard]
- pandas
- numpy
- scipy
- pydantic
- pydantic-settings
- sqlalchemy
- psycopg2-binary
- python-multipart
- python-dotenv

**Dev (dependency-groups):**
- pytest
- httpx
- pytest-asyncio

### Database Impact
None in this sub-phase.

### API Changes
One new endpoint: `GET /api/v1/health` → `{"status": "ok", "version": "0.1.0"}`

### Risks
- `uv` must be installed first. If the Windows `py` launcher doesn't work with `uv`, we'll need to install Python properly on PATH.

### Steps
1. Install `uv` via the official installer
2. Create `stat-engine/` directory
3. Initialize with `uv init` + configure `pyproject.toml`
4. Install dependencies with `uv sync`
5. Create FastAPI scaffold
6. Verify `uv run uvicorn app.main:app` starts and `/api/v1/health` returns 200
7. Update `.gitignore`

---

## 8. Testing Strategy (Sub-Phase 1.1)

- Manually verify the health endpoint returns `{"status": "ok", "version": "0.1.0"}`
- Verify `uv run pytest` runs successfully (even with no tests yet — confirms the test runner works)

---

**Awaiting your approval to proceed with Sub-Phase 1.1.**
