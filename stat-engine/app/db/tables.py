"""
SQLAlchemy Core Table definitions mirroring Prisma's PostgreSQL schema.

Prisma owns migrations; this file provides typed SQL table structures
for fast, type-safe queries without maintaining a second ORM abstraction.
"""

from sqlalchemy import (
    MetaData,
    Table,
    Column,
    String,
    Integer,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    JSON,
    Text,
)

# ── PostgreSQL enum types (created by Prisma, NOT by SQLAlchemy) ──────
# create_type=False tells SQLAlchemy these types already exist in the DB.
UserRoleEnum = Enum("USER", "ADMIN", name="UserRole", create_type=False)
DatasetStatusEnum = Enum("UPLOADED", "PROCESSING", "READY", "ERROR", name="DatasetStatus", create_type=False)
TrainingRunStatusEnum = Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", name="TrainingRunStatus", create_type=False)
AnalysisJobStatusEnum = Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", name="AnalysisJobStatus", create_type=False)
ValidationStatusEnum = Enum("OK", "WARN", "FAIL", name="ValidationStatus", create_type=False)

metadata = MetaData()

# ── Users ─────────────────────────────────────────────────────────────
users = Table(
    "users",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("email", String, unique=True, nullable=False),
    Column("emailVerified", Boolean, nullable=False),
    Column("image", String, nullable=True),
    Column("role", UserRoleEnum, nullable=False, default="USER"),
    Column("createdAt", DateTime, nullable=False),
    Column("updatedAt", DateTime, nullable=False),
    Column("deletedAt", DateTime, nullable=True),
)

# ── Projects ──────────────────────────────────────────────────────────
projects = Table(
    "projects",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("description", String, nullable=True),
    Column("userId", String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("createdAt", DateTime, nullable=False),
    Column("updatedAt", DateTime, nullable=False),
    Column("deletedAt", DateTime, nullable=True),
)

# ── Datasets ──────────────────────────────────────────────────────────
datasets = Table(
    "datasets",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("fileName", String, nullable=False),
    Column("fileType", String, nullable=False),
    Column("fileSizeBytes", Integer, nullable=False),
    Column("fileUrl", String, nullable=False),
    Column("parquetUrl", String, nullable=True),
    Column("columns", JSON, nullable=True),
    Column("rowCount", Integer, nullable=True),
    Column("colCount", Integer, nullable=True),
    Column("checksum", String, nullable=True),
    Column("status", DatasetStatusEnum, nullable=False, default="UPLOADED"),
    Column("projectId", String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
    Column("createdAt", DateTime, nullable=False),
    Column("updatedAt", DateTime, nullable=False),
    Column("deletedAt", DateTime, nullable=True),
)

# ── Dataset Previews ──────────────────────────────────────────────────
dataset_previews = Table(
    "dataset_previews",
    metadata,
    Column("id", String, primary_key=True),
    Column("previewJson", JSON, nullable=False),
    Column("datasetId", String, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
    Column("createdAt", DateTime, nullable=False),
    Column("deletedAt", DateTime, nullable=True),
)

# ── Variable Profiles ─────────────────────────────────────────────────
variable_profiles = Table(
    "variable_profiles",
    metadata,
    Column("id", String, primary_key=True),
    Column("columnName", String, nullable=False),
    Column("detectedType", String, nullable=False),
    Column("userOverride", String, nullable=True),
    Column("statsJson", JSON, nullable=True),
    Column("datasetId", String, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
    Column("deletedAt", DateTime, nullable=True),
)

# ── Validation Reports ────────────────────────────────────────────────
validation_reports = Table(
    "validation_reports",
    metadata,
    Column("id", String, primary_key=True),
    Column("reportJson", JSON, nullable=False),
    Column("datasetId", String, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
    Column("createdAt", DateTime, nullable=False),
    Column("deletedAt", DateTime, nullable=True),
)

# ── Preprocess Pipelines ──────────────────────────────────────────────
preprocess_pipelines = Table(
    "preprocess_pipelines",
    metadata,
    Column("id", String, primary_key=True),
    Column("version", Integer, nullable=False, default=1),
    Column("pipelineJson", JSON, nullable=False),
    Column("datasetId", String, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
    Column("createdAt", DateTime, nullable=False),
    Column("deletedAt", DateTime, nullable=True),
)

# ── Analysis Jobs ─────────────────────────────────────────────────────
analysis_jobs = Table(
    "analysis_jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column("pipelineVersion", Integer, nullable=True),
    Column("status", AnalysisJobStatusEnum, nullable=False, default="PENDING"),
    Column("currentStage", String, nullable=True),
    Column("errorMessage", String, nullable=True),
    Column("datasetId", String, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
    Column("createdAt", DateTime, nullable=False),
    Column("finishedAt", DateTime, nullable=True),
    Column("deletedAt", DateTime, nullable=True),
)

# ── Test Selections ───────────────────────────────────────────────────
test_selections = Table(
    "test_selections",
    metadata,
    Column("id", String, primary_key=True),
    Column("testId", String, nullable=False),
    Column("assumptionsJson", JSON, nullable=False),
    Column("fallbackTestId", String, nullable=True),
    Column("analysisJobId", String, ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False),
    Column("deletedAt", DateTime, nullable=True),
)

# ── Analysis Results ──────────────────────────────────────────────────
analysis_results = Table(
    "analysis_results",
    metadata,
    Column("id", String, primary_key=True),
    Column("resultJson", JSON, nullable=False),
    Column("validationStatus", ValidationStatusEnum, nullable=False, default="OK"),
    Column("analysisJobId", String, ForeignKey("analysis_jobs.id", ondelete="CASCADE"), unique=True, nullable=False),
    Column("createdAt", DateTime, nullable=False),
    Column("deletedAt", DateTime, nullable=True),
)

# ── Visualizations ────────────────────────────────────────────────────
visualizations = Table(
    "visualizations",
    metadata,
    Column("id", String, primary_key=True),
    Column("chartType", String, nullable=False),
    Column("chartJsonPath", String, nullable=False),
    Column("thumbnailPath", String, nullable=True),
    Column("analysisResultId", String, ForeignKey("analysis_results.id", ondelete="CASCADE"), nullable=False),
    Column("createdAt", DateTime, nullable=False),
    Column("deletedAt", DateTime, nullable=True),
)

# ── Interpretations ───────────────────────────────────────────────────
interpretations = Table(
    "interpretations",
    metadata,
    Column("id", String, primary_key=True),
    Column("content", Text, nullable=False),
    Column("markdownPath", String, nullable=True),
    Column("analysisResultId", String, ForeignKey("analysis_results.id", ondelete="CASCADE"), unique=True, nullable=False),
    Column("createdAt", DateTime, nullable=False),
    Column("deletedAt", DateTime, nullable=True),
)

# ── Reports ───────────────────────────────────────────────────────────
reports = Table(
    "reports",
    metadata,
    Column("id", String, primary_key=True),
    Column("pdfPath", String, nullable=False),
    Column("format", String, nullable=False, default="pdf"),
    Column("analysisJobId", String, ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False),
    Column("generatedAt", DateTime, nullable=False),
    Column("deletedAt", DateTime, nullable=True),
)
