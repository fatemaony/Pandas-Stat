/*
  Warnings:

  - You are about to drop the column `expiresAt` on the `accounts` table. All the data in the column will be lost.
  - You are about to drop the column `providerAccountId` on the `accounts` table. All the data in the column will be lost.
  - You are about to drop the column `tokenType` on the `accounts` table. All the data in the column will be lost.
  - You are about to drop the column `password` on the `users` table. All the data in the column will be lost.
  - You are about to drop the column `token` on the `verifications` table. All the data in the column will be lost.
  - You are about to drop the `posts` table. If the table is not empty, all the data it contains will be lost.
  - Made the column `name` on table `users` required. This step will fail if there are existing NULL values in that column.
  - Added the required column `emailVerified` to the `users` table without a default value. This is not possible if the table is not empty.
  - Added the required column `value` to the `verifications` table without a default value. This is not possible if the table is not empty.

*/
-- CreateEnum
CREATE TYPE "UserRole" AS ENUM ('USER', 'ADMIN');

-- CreateEnum
CREATE TYPE "DatasetStatus" AS ENUM ('UPLOADED', 'PROCESSING', 'READY', 'ERROR');

-- CreateEnum
CREATE TYPE "TrainingRunStatus" AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED');

-- CreateEnum
CREATE TYPE "AnalysisJobStatus" AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED');

-- CreateEnum
CREATE TYPE "ValidationStatus" AS ENUM ('OK', 'WARN', 'FAIL');

-- DropForeignKey
ALTER TABLE "posts" DROP CONSTRAINT "posts_userId_fkey";

-- DropIndex
DROP INDEX "verifications_token_key";

-- AlterTable
ALTER TABLE "accounts" DROP COLUMN "expiresAt",
DROP COLUMN "providerAccountId",
DROP COLUMN "tokenType",
ADD COLUMN     "accessTokenExpiresAt" TIMESTAMP(3),
ADD COLUMN     "refreshTokenExpiresAt" TIMESTAMP(3),
ALTER COLUMN "createdAt" DROP DEFAULT;

-- AlterTable
ALTER TABLE "sessions" ADD COLUMN     "impersonatedBy" TEXT,
ALTER COLUMN "createdAt" DROP DEFAULT;

-- AlterTable
ALTER TABLE "users" DROP COLUMN "password",
ADD COLUMN     "banExpires" TIMESTAMP(3),
ADD COLUMN     "banReason" TEXT,
ADD COLUMN     "banned" BOOLEAN,
ADD COLUMN     "deletedAt" TIMESTAMP(3),
ADD COLUMN     "role" "UserRole" NOT NULL DEFAULT 'USER',
ALTER COLUMN "createdAt" DROP DEFAULT,
ALTER COLUMN "name" SET NOT NULL,
DROP COLUMN "emailVerified",
ADD COLUMN     "emailVerified" BOOLEAN NOT NULL;

-- AlterTable
ALTER TABLE "verifications" DROP COLUMN "token",
ADD COLUMN     "value" TEXT NOT NULL,
ALTER COLUMN "createdAt" DROP NOT NULL,
ALTER COLUMN "createdAt" DROP DEFAULT,
ALTER COLUMN "updatedAt" DROP NOT NULL;

-- DropTable
DROP TABLE "posts";

-- CreateTable
CREATE TABLE "audit_logs" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "action" TEXT NOT NULL,
    "entity" TEXT NOT NULL,
    "entityId" TEXT,
    "details" JSONB,
    "ipAddress" TEXT,
    "userAgent" TEXT,
    "userId" TEXT,

    CONSTRAINT "audit_logs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "projects" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "deletedAt" TIMESTAMP(3),
    "name" TEXT NOT NULL,
    "description" TEXT,
    "userId" TEXT NOT NULL,

    CONSTRAINT "projects_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "datasets" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "deletedAt" TIMESTAMP(3),
    "name" TEXT NOT NULL,
    "fileName" TEXT NOT NULL,
    "fileType" TEXT NOT NULL,
    "fileSizeBytes" INTEGER NOT NULL,
    "fileUrl" TEXT NOT NULL,
    "parquetUrl" TEXT,
    "columns" JSONB,
    "rowCount" INTEGER,
    "colCount" INTEGER,
    "checksum" TEXT,
    "status" "DatasetStatus" NOT NULL DEFAULT 'UPLOADED',
    "projectId" TEXT NOT NULL,

    CONSTRAINT "datasets_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "dataset_previews" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" TIMESTAMP(3),
    "previewJson" JSONB NOT NULL,
    "datasetId" TEXT NOT NULL,

    CONSTRAINT "dataset_previews_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "variable_profiles" (
    "id" TEXT NOT NULL,
    "deletedAt" TIMESTAMP(3),
    "columnName" TEXT NOT NULL,
    "detectedType" TEXT NOT NULL,
    "userOverride" TEXT,
    "statsJson" JSONB,
    "datasetId" TEXT NOT NULL,

    CONSTRAINT "variable_profiles_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "validation_reports" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" TIMESTAMP(3),
    "reportJson" JSONB NOT NULL,
    "datasetId" TEXT NOT NULL,

    CONSTRAINT "validation_reports_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "preprocess_pipelines" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" TIMESTAMP(3),
    "version" INTEGER NOT NULL DEFAULT 1,
    "pipelineJson" JSONB NOT NULL,
    "datasetId" TEXT NOT NULL,

    CONSTRAINT "preprocess_pipelines_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "training_runs" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" TIMESTAMP(3),
    "taskType" TEXT NOT NULL,
    "algorithm" TEXT NOT NULL,
    "hyperparams" JSONB NOT NULL,
    "metrics" JSONB,
    "modelArtifact" TEXT,
    "status" "TrainingRunStatus" NOT NULL DEFAULT 'PENDING',
    "projectId" TEXT NOT NULL,
    "datasetId" TEXT NOT NULL,

    CONSTRAINT "training_runs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "analysis_jobs" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finishedAt" TIMESTAMP(3),
    "deletedAt" TIMESTAMP(3),
    "pipelineVersion" INTEGER,
    "status" "AnalysisJobStatus" NOT NULL DEFAULT 'PENDING',
    "currentStage" TEXT,
    "errorMessage" TEXT,
    "datasetId" TEXT NOT NULL,

    CONSTRAINT "analysis_jobs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "test_selections" (
    "id" TEXT NOT NULL,
    "deletedAt" TIMESTAMP(3),
    "testId" TEXT NOT NULL,
    "assumptionsJson" JSONB NOT NULL,
    "fallbackTestId" TEXT,
    "analysisJobId" TEXT NOT NULL,

    CONSTRAINT "test_selections_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "analysis_results" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" TIMESTAMP(3),
    "resultJson" JSONB NOT NULL,
    "validationStatus" "ValidationStatus" NOT NULL DEFAULT 'OK',
    "analysisJobId" TEXT NOT NULL,

    CONSTRAINT "analysis_results_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "visualizations" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" TIMESTAMP(3),
    "chartType" TEXT NOT NULL,
    "chartJsonPath" TEXT NOT NULL,
    "thumbnailPath" TEXT,
    "analysisResultId" TEXT NOT NULL,

    CONSTRAINT "visualizations_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "interpretations" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" TIMESTAMP(3),
    "content" TEXT NOT NULL,
    "markdownPath" TEXT,
    "analysisResultId" TEXT NOT NULL,

    CONSTRAINT "interpretations_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "reports" (
    "id" TEXT NOT NULL,
    "generatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" TIMESTAMP(3),
    "pdfPath" TEXT NOT NULL,
    "format" TEXT NOT NULL DEFAULT 'pdf',
    "analysisJobId" TEXT NOT NULL,

    CONSTRAINT "reports_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "chat_messages" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" TIMESTAMP(3),
    "role" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "projectId" TEXT NOT NULL,

    CONSTRAINT "chat_messages_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "saved_charts" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "deletedAt" TIMESTAMP(3),
    "title" TEXT NOT NULL,
    "chartType" TEXT NOT NULL,
    "configJson" JSONB NOT NULL,
    "projectId" TEXT NOT NULL,

    CONSTRAINT "saved_charts_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "audit_logs_userId_idx" ON "audit_logs"("userId");

-- CreateIndex
CREATE INDEX "audit_logs_entity_entityId_idx" ON "audit_logs"("entity", "entityId");

-- CreateIndex
CREATE INDEX "audit_logs_createdAt_idx" ON "audit_logs"("createdAt");

-- CreateIndex
CREATE INDEX "projects_userId_idx" ON "projects"("userId");

-- CreateIndex
CREATE INDEX "datasets_projectId_idx" ON "datasets"("projectId");

-- CreateIndex
CREATE INDEX "dataset_previews_datasetId_idx" ON "dataset_previews"("datasetId");

-- CreateIndex
CREATE UNIQUE INDEX "variable_profiles_datasetId_columnName_key" ON "variable_profiles"("datasetId", "columnName");

-- CreateIndex
CREATE INDEX "validation_reports_datasetId_idx" ON "validation_reports"("datasetId");

-- CreateIndex
CREATE INDEX "preprocess_pipelines_datasetId_idx" ON "preprocess_pipelines"("datasetId");

-- CreateIndex
CREATE INDEX "training_runs_projectId_idx" ON "training_runs"("projectId");

-- CreateIndex
CREATE INDEX "training_runs_datasetId_idx" ON "training_runs"("datasetId");

-- CreateIndex
CREATE INDEX "analysis_jobs_datasetId_idx" ON "analysis_jobs"("datasetId");

-- CreateIndex
CREATE INDEX "test_selections_analysisJobId_idx" ON "test_selections"("analysisJobId");

-- CreateIndex
CREATE UNIQUE INDEX "analysis_results_analysisJobId_key" ON "analysis_results"("analysisJobId");

-- CreateIndex
CREATE INDEX "visualizations_analysisResultId_idx" ON "visualizations"("analysisResultId");

-- CreateIndex
CREATE UNIQUE INDEX "interpretations_analysisResultId_key" ON "interpretations"("analysisResultId");

-- CreateIndex
CREATE INDEX "reports_analysisJobId_idx" ON "reports"("analysisJobId");

-- CreateIndex
CREATE INDEX "chat_messages_projectId_idx" ON "chat_messages"("projectId");

-- CreateIndex
CREATE INDEX "saved_charts_projectId_idx" ON "saved_charts"("projectId");

-- AddForeignKey
ALTER TABLE "audit_logs" ADD CONSTRAINT "audit_logs_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "projects" ADD CONSTRAINT "projects_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "datasets" ADD CONSTRAINT "datasets_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "dataset_previews" ADD CONSTRAINT "dataset_previews_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "datasets"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "variable_profiles" ADD CONSTRAINT "variable_profiles_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "datasets"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "validation_reports" ADD CONSTRAINT "validation_reports_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "datasets"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "preprocess_pipelines" ADD CONSTRAINT "preprocess_pipelines_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "datasets"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "training_runs" ADD CONSTRAINT "training_runs_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "training_runs" ADD CONSTRAINT "training_runs_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "datasets"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "analysis_jobs" ADD CONSTRAINT "analysis_jobs_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "datasets"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "test_selections" ADD CONSTRAINT "test_selections_analysisJobId_fkey" FOREIGN KEY ("analysisJobId") REFERENCES "analysis_jobs"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "analysis_results" ADD CONSTRAINT "analysis_results_analysisJobId_fkey" FOREIGN KEY ("analysisJobId") REFERENCES "analysis_jobs"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "visualizations" ADD CONSTRAINT "visualizations_analysisResultId_fkey" FOREIGN KEY ("analysisResultId") REFERENCES "analysis_results"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "interpretations" ADD CONSTRAINT "interpretations_analysisResultId_fkey" FOREIGN KEY ("analysisResultId") REFERENCES "analysis_results"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "reports" ADD CONSTRAINT "reports_analysisJobId_fkey" FOREIGN KEY ("analysisJobId") REFERENCES "analysis_jobs"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "chat_messages" ADD CONSTRAINT "chat_messages_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "saved_charts" ADD CONSTRAINT "saved_charts_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;
