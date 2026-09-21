# Sub-Phase 1.4 — Dataset Upload API  ✅ FINALIZED

> All open questions resolved. Ready for implementation.

---

## Confirmed Decisions

| # | Question | Decision |
|---|---|---|
| Q1 | Size enforcement strategy | **Mid-stream rejection** — running byte counter per chunk; raise 413 before writing exceeds limit |
| Q2 | Async file I/O | **`aiofiles`** — add `aiofiles>=24.0.0` to `pyproject.toml` |
| Q3 | Next.js multipart forwarding | **Buffered forwarding acceptable for Phase 1** — avoid unnecessary `arrayBuffer()` copies; use `request.formData()` and reconstruct a new `FormData` for the downstream `fetch` |
| Q4 | `check_project_ownership` placement | **Keep in `DatasetRepository`** — same file, new method |
| Q5 | Response body | **Full `DatasetRow`** — return the complete schema (201) |

---

## A. Current Architecture Findings

### Next.js (frontend / BFF)

| Item | Detail |
|---|---|
| Framework | Next.js (App Router, TypeScript) |
| Auth | Better Auth — `prismaAdapter`, `nextCookies()`, `customSession` plugins |
| Session API | `auth.api.getSession({ headers })` — server-side in Route Handlers |
| Auth handler | `app/api/auth/[...all]/route.ts` → `toNextJsHandler(auth)` |
| Session token | Cookie `better-auth.session_token` |
| Prisma | `lib/prisma.ts` — single `PrismaClient`; only schema/migration authority |
| No datasets route | `app/api/` contains only `auth/` — upload proxy does not exist yet |

### FastAPI (stat-engine)

| Item | Detail |
|---|---|
| Entry | `app/main.py` — `create_app()` factory + `lifespan` |
| Config | `app/config.py` — `Settings`; `max_file_size_mb=50`, `upload_dir=stat-engine/uploads/`, `internal_api_secret` already present |
| DB | `app/db/session.py` — async engine + `get_db()` dependency |
| Tables | `app/db/tables.py` — SQLAlchemy Core mirror of Prisma schema |
| Repository | `app/repositories/dataset_repo.py` — full `DatasetRepository` |
| Schemas | `app/schemas/dataset.py` — `DatasetCreate`, `DatasetRow`, `DatasetStatus` |
| No router yet | `main.py` only has the inline health endpoint |
| Uploads dir | `stat-engine/uploads/` — empty, auto-created at startup via `lifespan` |
| `python-multipart` | Already in `pyproject.toml` ✅ |
| `aiofiles` | **Not yet** in `pyproject.toml` — must be added |

### Security already in place
- `internal_api_secret` in `Settings` (dev default: `stat-engine-internal-secret-dev`)
- `ALLOWED_ORIGINS` restricts CORS to `http://localhost:3000`
- `MAX_FILE_SIZE_MB` already configurable

---

## B. Existing Components to Reuse

| Component | Reuse |
|---|---|
| `DatasetRepository.create()` | Direct reuse — inserts row, sets `status=UPLOADED` automatically |
| `DatasetCreate` | Direct reuse — DB-insert payload |
| `DatasetRow` | Direct reuse — 201 response body |
| `DatasetStatus.UPLOADED` | Already the `create()` default — no explicit status logic in service |
| `get_db()` dependency | Inject `AsyncSession` into service via FastAPI DI |
| `generate_cuid()` | Used for safe filename generation |
| `Settings.upload_dir` | Base directory already resolved and auto-created |
| `Settings.max_file_size_mb` | Size limit already configurable |
| `Settings.internal_api_secret` | Shared secret already in `Settings` |
| `lifespan` | No change needed — upload dir creation already handled |

---

## C. API Contract

### FastAPI endpoint

```
POST /api/v1/datasets/upload
Content-Type: multipart/form-data
X-Internal-Secret: <internal_api_secret>
X-User-Id: <authenticated_user_id>

Form fields:
  file        UploadFile   required — the CSV file
  project_id  str          required — target project CUID
  name        str          optional — display name; defaults to original filename stem
```

### Next.js BFF endpoint (browser-facing)

```
POST /api/datasets/upload
Content-Type: multipart/form-data
Cookie: better-auth.session_token=<token>

Form fields:
  file        File         required
  project_id  string       required
  name        string       optional
```

The Next.js Route Handler:
1. Calls `auth.api.getSession({ headers: req.headers })` — no `arrayBuffer()` needed
2. Extracts `session.user.id`
3. Calls `req.formData()` once — parses the incoming form
4. Reconstructs a new `FormData`, appends the same `file`, `project_id`, `name`
5. `fetch(STAT_ENGINE_URL + "/api/v1/datasets/upload", { method: "POST", body: formData, headers: { "X-Internal-Secret": ..., "X-User-Id": ... } })`
6. Streams FastAPI's `Response` back to the browser (no second `arrayBuffer()` copy)

> **Q3 implementation note:** `req.formData()` reads the body once. The reconstructed `FormData` is passed directly to `fetch` — the native `fetch` implementation handles the multipart encoding without an intermediate `arrayBuffer()` call.

---

## D. Authentication & Authorization Flow

```
Browser
  │  POST /api/datasets/upload  (multipart, cookie)
  ▼
Next.js Route Handler  [app/api/datasets/upload/route.ts]
  │  1. auth.api.getSession({ headers: req.headers })
  │     ├── session valid   → session.user.id
  │     └── no session      → 401 { error: "Unauthenticated" }
  │
  │  2. req.formData()  → reconstruct FormData  → fetch() to FastAPI
  │     Headers added:
  │       X-Internal-Secret: process.env.STAT_ENGINE_INTERNAL_SECRET
  │       X-User-Id: session.user.id
  ▼
FastAPI Router  [app/api/v1/datasets/router.py]
  │  3. verify_internal_secret dependency
  │     ├── header matches settings.internal_api_secret  → continue
  │     └── mismatch / missing                           → 403
  │
  │  4. get_user_id dependency — extract X-User-Id header
  │     └── missing → 400
  │
  │  5. delegate to DatasetUploadService.upload()
  ▼
DatasetUploadService  [app/services/dataset_upload_service.py]
  │  6. file-level validation (extension, empty size pre-check)
  │  7. repo.check_project_ownership(project_id, user_id)
  │     ├── False → 403  (before any disk write)
  │     └── True  → continue
  │  8. ensure upload_dir/project_id exists (mkdir)
  │  9. stream file to disk chunk-by-chunk via aiofiles
  │     └── running counter ≥ max_size_bytes → 413, abort, delete partial
  │  10. repo.create(DatasetCreate(...))  → flush
  │  11. session.commit()
  │  12. return DatasetRow
```

### New environment variables

```bash
# stat-engine/.env  — ADD:
INTERNAL_API_SECRET=<shared-secret>

# pandas-stat/.env  — ADD:
STAT_ENGINE_INTERNAL_SECRET=<same-shared-secret>
STAT_ENGINE_URL=http://127.0.0.1:8000
```

---

## E. File Storage Design

### Directory structure

```
stat-engine/
└── uploads/
    └── {project_id}/          ← per-project subdirectory (mkdir on upload)
        └── {cuid}.csv         ← generated name, never the original
```

### Filename generation

```python
generated_stem = generate_cuid()          # 25-char CUID2
file_path = upload_dir / project_id / f"{generated_stem}.csv"
```

- Original filename is **never** used on disk
- Extension always hard-coded as `.csv` from validation, not from user input

### Database field mapping

| Field | Stored value |
|---|---|
| `fileName` | Sanitized original filename for display (strip null bytes, max 255 chars) |
| `fileUrl` | Relative path: `/uploads/{project_id}/{cuid}.csv` |
| `fileType` | Literal `"text/csv"` (from validation result, not user MIME header) |
| `fileSizeBytes` | Exact byte count accumulated during streaming write |
| `checksum` | `sha256:<hex>` computed during streaming write via `hashlib` |
| `parquetUrl` | `null` |
| `columns`, `rowCount`, `colCount` | `null` |

**Why relative path?** Absolute paths leak filesystem layout. Relative paths survive relocation. In Phase 2 (S3), `fileUrl` becomes a real URL — the column supports it already.

### Mid-stream size enforcement (Q1 confirmed)

```python
CHUNK = 1024 * 64  # 64 KB chunks
accumulated = 0
max_bytes = settings.max_file_size_mb * 1024 * 1024

async with aiofiles.open(file_path, "wb") as f:
    while chunk := await upload_file.read(CHUNK):
        accumulated += len(chunk)
        if accumulated > max_bytes:
            # close and delete partial file, then raise
            await f.close()
            file_path.unlink(missing_ok=True)
            raise HTTPException(status_code=413, detail="File exceeds maximum size of 50 MB")
        await f.write(chunk)
        hasher.update(chunk)

if accumulated == 0:
    file_path.unlink(missing_ok=True)
    raise HTTPException(status_code=400, detail="Uploaded file is empty")
```

### Duplicate / checksum
- SHA-256 stored in `checksum` field
- No duplicate enforcement in this phase (no UNIQUE constraint in Prisma schema)
- Future phases can query `WHERE checksum = $1 AND projectId = $2`

---

## F. Dataset Lifecycle

```
[ Sub-Phase 1.4 ]         [ Future sub-phases ]
    UPLOADED  ─────────►  PROCESSING  ─────────►  READY
                                      └─────────►  ERROR
```

`DatasetRepository.create()` already hard-codes `status = DatasetStatus.UPLOADED`. No status transition logic is needed in this phase.

---

## G. Proposed Files

### New files — FastAPI

| File | Purpose |
|---|---|
| `app/api/__init__.py` | Package marker |
| `app/api/v1/__init__.py` | Package marker |
| `app/api/v1/datasets/__init__.py` | Package marker |
| `app/api/v1/datasets/router.py` | `POST /api/v1/datasets/upload` — HTTP boundary only |
| `app/services/__init__.py` | Package marker |
| `app/services/dataset_upload_service.py` | All upload business logic |
| `app/dependencies/__init__.py` | Package marker |
| `app/dependencies/auth.py` | `verify_internal_secret`, `get_user_id` FastAPI dependencies |
| `tests/test_dataset_upload.py` | 15 upload tests |

### Modified files — FastAPI

| File | Change |
|---|---|
| `app/main.py` | Include datasets router via `app.include_router(...)` |
| `app/repositories/dataset_repo.py` | Add `check_project_ownership(project_id, user_id)` method |
| `pyproject.toml` | Add `aiofiles>=24.0.0` to dependencies |
| `.env.example` | Document `INTERNAL_API_SECRET`, `STAT_ENGINE_URL` |

### New files — Next.js

| File | Purpose |
|---|---|
| `app/api/datasets/upload/route.ts` | BFF proxy: session check + reconstruct FormData + forward |

### Modified files — Next.js

| File | Change |
|---|---|
| `.env` / `.env.example` | Add `STAT_ENGINE_INTERNAL_SECRET`, `STAT_ENGINE_URL` |

### Layer responsibilities (enforced)

```
router.py                    HTTP only — parse multipart, call service, return response
  ↓
dataset_upload_service.py    Business logic — validate, authorize, store, create record
  ↓
dataset_repo.py              SQL only — INSERT + check_project_ownership
  ↓
tables.py / session.py       Unchanged
```

---

## H. Request / Response Examples

### Successful upload

**Browser → Next.js**
```http
POST /api/datasets/upload HTTP/1.1
Host: localhost:3000
Cookie: better-auth.session_token=abc123...
Content-Type: multipart/form-data; boundary=----Boundary

------Boundary
Content-Disposition: form-data; name="file"; filename="sales_data.csv"
Content-Type: text/csv

id,name,revenue
1,Alice,5000
------Boundary
Content-Disposition: form-data; name="project_id"

cm1a2b3c4d5e6f7g8h9i0j1k2
------Boundary
Content-Disposition: form-data; name="name"

Sales Dataset Q3
------Boundary--
```

**Next.js → FastAPI (internal)**
```http
POST /api/v1/datasets/upload HTTP/1.1
Host: 127.0.0.1:8000
X-Internal-Secret: stat-engine-internal-secret-dev
X-User-Id: cm9x8y7z6w5v4u3t2s1r0q
Content-Type: multipart/form-data; boundary=...
[reconstructed FormData body]
```

**201 Created**
```json
{
  "id": "cm4n5m6l7k8j9i0h1g2f3e4d5",
  "name": "Sales Dataset Q3",
  "fileName": "sales_data.csv",
  "fileType": "text/csv",
  "fileSizeBytes": 204800,
  "fileUrl": "/uploads/cm1a2b3c4d5e6f7g8h9i0j1k2/cm4n5m6l7k8j9i0h1g2f3e4d5.csv",
  "parquetUrl": null,
  "columns": null,
  "rowCount": null,
  "colCount": null,
  "checksum": "sha256:3a7bd3e2360a3d29eea436fcfb7e44c735d117c42d1c1835420b6b9942dd4f1b",
  "status": "UPLOADED",
  "projectId": "cm1a2b3c4d5e6f7g8h9i0j1k2",
  "createdAt": "2026-09-21T00:10:00.000Z",
  "updatedAt": "2026-09-21T00:10:00.000Z",
  "deletedAt": null
}
```

---

## I. Error Handling

| Scenario | HTTP | `detail` |
|---|---|---|
| Wrong / missing `X-Internal-Secret` | 403 | `"Forbidden"` |
| Missing `X-User-Id` header | 400 | `"Missing X-User-Id header"` |
| Missing `file` form field | 422 | FastAPI auto-validation |
| Missing `project_id` form field | 422 | FastAPI auto-validation |
| Extension not `.csv` | 400 | `"Only CSV files are accepted"` |
| Content-Type not text/csv | 400 | `"Only CSV files are accepted"` |
| File > `max_file_size_mb` | 413 | `"File exceeds maximum size of 50 MB"` |
| Empty file (0 bytes) | 400 | `"Uploaded file is empty"` |
| Project not found / not owned | 403 | `"Project not found or access denied"` |
| Disk write failure | 500 | `"File storage failed"` |
| DB insert failure | 500 | `"Database error"` |
| Malformed multipart | 422 | FastAPI auto-validation |

**Next.js layer:** `auth.api.getSession()` returns `null` → `401 { "error": "Unauthenticated" }`. All FastAPI errors forwarded as-is.

---

## J. Security Considerations

| Threat | Mitigation |
|---|---|
| Path traversal | Original filename never used on disk; `pathlib.Path` joins only trusted CUID components |
| Arbitrary file upload | Extension `.csv` check (case-insensitive) is the primary gate |
| MIME spoofing | Extension check is not bypassable via `Content-Type`; MIME is a secondary signal only |
| Filename injection | `fileName` stored for display only; sanitized (strip null bytes, truncate to 255 chars) |
| Oversized files | Mid-stream reject at chunk boundary — no full oversized file ever written |
| Resource exhaustion | `MAX_FILE_SIZE_MB` cap + uvicorn worker limits |
| Unauthorized project access | `check_project_ownership()` runs before disk write; `False` → 403 immediately |
| Internal path leakage | `fileUrl` relative only; full paths only in server logs |
| Direct FastAPI access bypass | `X-Internal-Secret` blocks unauthorized callers; port 8000 not public |

---

## K. Testing Strategy — 15 Tests

All tests: `httpx.AsyncClient(transport=ASGITransport(app=create_app()))`. DB: live Neon PostgreSQL (same pattern as 1.3). Filesystem: real `upload_dir` (cleaned in teardown).

| # | Test | Verifies |
|---|---|---|
| 1 | `test_upload_csv_success` | 201, `DatasetRow` shape, `status=UPLOADED`, file on disk, checksum set |
| 2 | `test_upload_missing_secret` | 403 when `X-Internal-Secret` absent |
| 3 | `test_upload_wrong_secret` | 403 when `X-Internal-Secret` has wrong value |
| 4 | `test_upload_missing_user_id` | 400 when `X-User-Id` absent |
| 5 | `test_upload_wrong_project_owner` | 403 when `project_id` owned by another user |
| 6 | `test_upload_nonexistent_project` | 403 for non-existent `project_id` |
| 7 | `test_upload_invalid_extension_txt` | 400 — `.txt` rejected |
| 8 | `test_upload_invalid_extension_exe` | 400 — `.exe` rejected |
| 9 | `test_upload_no_extension` | 400 — no extension rejected |
| 10 | `test_upload_oversized_file` | 413 — file > `max_file_size_mb` |
| 11 | `test_upload_empty_file` | 400 — zero-byte file |
| 12 | `test_upload_safe_filename_generation` | `fileUrl` does not contain original filename |
| 13 | `test_upload_dataset_record_in_db` | DB row has correct `projectId`, `fileName`, `fileSizeBytes` |
| 14 | `test_upload_file_exists_on_disk` | File at `fileUrl` path exists after upload |
| 15 | `test_upload_default_name_from_filename` | When `name` omitted, stem of `fileName` used as display name |

**Fixtures (mirrors 1.3 pattern):**
- Module-scoped engine + session factory
- `setup_and_teardown`: create test user + owned project + other user + other project
- Teardown: hard-delete datasets, files from disk, projects, users
- Per-test `session` rolls back

> [!NOTE]
> Storage-failure and DB-failure tests: `unittest.mock.patch` — inject `OSError` / `RuntimeError` without needing real infrastructure failures.

---

## L. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Direct FastAPI port access bypasses Next.js auth | Low | `X-Internal-Secret` blocks it; firewall port 8000 in production |
| Disk full during upload | Low | OS error caught → 500 with cleanup; operator monitoring |
| Race: project deleted between ownership check and DB insert | Very Low | Single request, no concurrent delete in Phase 1 |
| `arrayBuffer()` double-copy in Next.js proxy | Avoided by design | Use `req.formData()` → reconstruct `FormData` → pass to `fetch` directly |
| Original filename XSS on frontend | Low | `fileName` display-only; frontend must HTML-escape |
| Next.js Route Handler on edge runtime | Low | `export const runtime = "nodejs"` in route file |
| Partial file left on disk after 413 / error | Mitigated | `file_path.unlink(missing_ok=True)` in except/finally block |

---

## M. Definition of Done

**FastAPI:**
- [ ] `POST /api/v1/datasets/upload` registered via `APIRouter`, mounted in `main.py`
- [ ] Wrong/missing `X-Internal-Secret` → 403
- [ ] Missing `X-User-Id` → 400
- [ ] Non-`.csv` extension → 400
- [ ] File > `max_file_size_mb` → 413, mid-stream reject, no full file written
- [ ] Empty file → 400
- [ ] Non-owned `project_id` → 403, checked before disk write
- [ ] File written to `uploads/{project_id}/{cuid}.csv` (never original filename)
- [ ] SHA-256 checksum computed via streaming and stored in `checksum`
- [ ] Dataset record created with `status=UPLOADED`, correct `fileUrl`, `fileName`, `fileSizeBytes`
- [ ] Full `DatasetRow` returned with HTTP 201
- [ ] `DatasetRepository.check_project_ownership(project_id, user_id)` implemented
- [ ] `aiofiles>=24.0.0` added to `pyproject.toml`
- [ ] `INTERNAL_API_SECRET` in `stat-engine/.env.example`

**Next.js:**
- [ ] `app/api/datasets/upload/route.ts` created with `export const runtime = "nodejs"`
- [ ] Unauthenticated request → 401
- [ ] Session valid → `req.formData()` → reconstruct `FormData` → `fetch` to FastAPI (no `arrayBuffer()`)
- [ ] FastAPI response forwarded to browser as-is
- [ ] `STAT_ENGINE_INTERNAL_SECRET` and `STAT_ENGINE_URL` in `.env` / `.env.example`

**Tests:**
- [ ] All 15 tests in `test_dataset_upload.py` pass
- [ ] Existing 25 stat-engine tests still pass (regression)

**Architecture rules:**
- [ ] No Prisma schema modified
- [ ] No SQLAlchemy ORM introduced
- [ ] No Celery/Redis introduced
- [ ] No CSV parsing performed
- [ ] Router contains no business logic
- [ ] Service contains no SQL queries
