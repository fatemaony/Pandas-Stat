# Software Requirements Specification (SRS)
## AI-Powered Data Analysis & Visualization Platform

**Version:** 1.0
**Date:** August 27, 2026
**Prepared for:** Researchers, Students, Businesses & Organizations

---

## 1. Introduction

### 1.1 Purpose
This document describes the requirements for a web-based platform that lets users upload datasets (CSV, Excel, Google Sheets) and get automated data exploration, preprocessing, machine learning modeling, visualization, and AI-powered interpretation — no coding required.

### 1.2 Scope
The platform guides a user end-to-end: **Upload → Explore → Preprocess → Model → Train/Test → Analyze → Visualize → Interpret**, plus an AI chatbot to answer questions about their data and results in plain language.

### 1.3 Intended Audience
Researchers, students, data analysts, small businesses, and organizations who want quick, guided insights from their data without needing to write code.

### 1.4 Definitions
| Term | Meaning |
|---|---|
| EDA | Exploratory Data Analysis |
| ML | Machine Learning |
| LLM | Large Language Model (used for the chatbot) |

---

## 2. Overall Description

### 2.1 Product Perspective
A standalone SaaS web app with a Next.js frontend and a FastAPI (Python) backend for data science tasks, backed by PostgreSQL for storage and an OpenAI-powered chatbot for guidance and interpretation.

### 2.2 User Classes
- **Guest/Free user** – limited uploads, basic features
- **Registered user** (student/researcher/business) – full pipeline access, saved projects
- **Admin** – manages users, monitors usage, platform settings

### 2.3 Operating Environment
Modern web browsers (Chrome, Firefox, Safari, Edge), responsive for desktop and tablet.

---

## 3. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS |
| Charts/Visualization | Recharts |
| Backend (data/ML) | FastAPI, Python |
| Database | PostgreSQL + Prisma ORM |
| Authentication | Better Auth |
| AI Chatbot | OpenAI API |

---

## 4. Functional Requirements

### 4.1 Authentication & User Management
- Sign up / log in via email or OAuth (Better Auth)
- Role-based access (Guest, Registered, Admin)
- Profile & project/dataset history

### 4.2 Dataset Upload
- Upload CSV, XLSX, or connect a Google Sheet (via Google Sheets API)
- File size validation & format checks
- Preview raw data table before proceeding

### 4.3 Data Exploration (EDA)
- Auto-generate summary statistics (mean, median, std dev, nulls, data types)
- Column-level insights (distributions, unique values, correlations)
- Auto-suggested visual charts (histograms, box plots, correlation heatmap)

### 4.4 Data Preprocessing
- Handle missing values (drop/impute — mean, median, mode)
- Encode categorical variables (label/one-hot)
- Feature scaling (normalization/standardization)
- Outlier detection & removal
- Train/test split configuration

### 4.5 Model Selection
- Choose ML task type: Regression, Classification, or Clustering
- Choose algorithm (e.g., Linear/Logistic Regression, Decision Tree, Random Forest, KMeans, etc.)
- Auto-recommend a suitable model based on data characteristics (optional smart mode)

### 4.6 Training & Testing
- Configure hyperparameters (with sensible defaults)
- Run training with progress indicator
- Display evaluation metrics (accuracy, RMSE, R², F1-score, confusion matrix, etc. depending on task)

### 4.7 Analysis & Results
- Compare model performance across runs
- Feature importance visualization
- Prediction vs. actual results view

### 4.8 Visualization
- Interactive charts via Recharts (bar, line, scatter, pie, heatmap)
- Export charts as PNG/PDF
- Downloadable results report (PDF/CSV)

### 4.9 AI Interpretation & Recommendations
- Plain-language summary of EDA findings
- Model performance interpretation ("your model is doing well because...")
- Suggested next steps (e.g., "try removing outliers to improve accuracy")

### 4.10 AI Chatbot
- Context-aware chatbot that understands the uploaded dataset & current pipeline stage
- Users can ask questions like "what does this correlation mean?" or "which model should I use?"
- Chat history saved per project

---

## 5. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Performance | Handle datasets up to a defined size (e.g., 50MB) with response < 5s for EDA |
| Security | Encrypted storage, secure auth sessions, data privacy compliance |
| Scalability | Backend able to queue/process multiple training jobs |
| Usability | Simple, guided step-by-step UI (wizard-style flow) |
| Reliability | Auto-save progress; recover from failed training runs |
| Availability | 99% uptime target |

---

## 6. System Architecture Overview

```
User → Next.js Frontend (TypeScript, Tailwind, Recharts)
          ↓ REST/API calls
     FastAPI Backend (Python: pandas, scikit-learn)
          ↓
     PostgreSQL (via Prisma) — stores users, projects, datasets metadata, results
          ↓
     OpenAI API — powers chatbot & interpretation layer
```

---

## 7. Data Requirements
- Supported input formats: `.csv`, `.xlsx`, Google Sheets link
- Data stored securely; raw files retained per user's plan/storage quota
- Processed results & model artifacts linked to each project for future access

---

## 8. Assumptions & Constraints
- Users have basic tabular data (not unstructured text/image data, in v1)
- Initial release supports standard ML tasks (regression, classification, clustering) — deep learning may be a future phase
- OpenAI API usage costs should be monitored/rate-limited per user tier

---

## 9. Future Enhancements (Out of Scope for v1)
- Support for time-series and NLP datasets
- Collaborative multi-user projects
- AutoML pipeline with model auto-tuning
- Downloadable trained model (API/deployment ready)

---

*This SRS is a living document and may be refined as requirements evolve during development.*
