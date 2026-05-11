# Cloud Cost Optimizer & Remediation Engine

An Azure FinOps platform that automatically identifies idle and orphaned cloud resources, estimates waste cost, and generates PowerShell remediation scripts — all surfaced through a React dashboard.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Local Development](#local-development)
- [Environment Variables](#environment-variables)
- [Running Tests](#running-tests)
- [Docker](#docker)
- [API Reference](#api-reference)
- [Deploy to Azure](#deploy-to-azure)
- [Security](#security)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  React Dashboard (Vite)          :5173                       │
│    ↕ REST                                                    │
│  FastAPI Backend                 :8000                       │
│    ├── Analysis Pipeline                                     │
│    │     └── 10 resource-type analyzers (Azure Monitor)     │
│    ├── SQLite DB  ←→  Azure Blob Storage (optimizer-db)     │
│    └── Export CSVs / PS1 scripts → Azure Blob (exports)     │
│                                                              │
│  Azure Infrastructure (Terraform)                            │
│    ├── Azure Container Apps  (API + Job)                     │
│    ├── Azure Container Registry                              │
│    ├── Azure Key Vault  (SAS token secrets)                  │
│    └── Azure Storage Account  (DB + exports containers)      │
└─────────────────────────────────────────────────────────────┘
```

## Features

- **Resource Discovery** — queries Azure Resource Graph for all resources across a subscription
- **Cost Analysis** — pulls 30-day spend from Azure Cost Management API
- **Idle Detection** — 10 built-in analyzers covering:
  - Virtual Machines (low CPU)
  - Managed Disks (unattached)
  - AKS Clusters (low CPU)
  - App Services (no requests)
  - Azure Functions (no invocations)
  - SQL Databases (low DTU)
  - Cosmos DB (low RU)
  - Storage Accounts (no reads)
  - Logic Apps (no runs)
  - ADF Pipelines (no runs)
- **Remediation Scripts** — auto-generates per-resource PowerShell scripts (tag + delete)
- **React Dashboard** — live KPIs, findings table, job history, script download
- **Persistent SQLite** — DB file synced to Azure Blob between runs (zero-cost persistence)
- **CI/CD** — Azure DevOps pipeline with Docker build → ACR push → Container Apps deploy

---

## Project Structure

```
.
├── api/                        # FastAPI backend
│   ├── analysis/               # Resource analyzers (one file per type)
│   │   ├── base.py             # BaseAnalyzer, Finding model, MetricAnalyzer
│   │   ├── virtual_machines.py
│   │   ├── managed_disks.py
│   │   ├── aks.py
│   │   ├── app_services.py
│   │   ├── azure_functions.py
│   │   ├── sql_databases.py
│   │   ├── cosmos_db.py
│   │   ├── storage_accounts.py
│   │   ├── logic_apps.py
│   │   ├── adf_pipelines.py
│   │   └── __init__.py         # AnalysisPipeline (orchestrator)
│   ├── db/                     # DB provider abstraction (SQLite/PostgreSQL/MySQL/SQL Server)
│   ├── routers/                # FastAPI route handlers
│   │   ├── jobs.py             # Pipeline trigger + job status
│   │   ├── dashboard.py        # Summary KPIs
│   │   ├── findings.py         # Orphan findings list
│   │   ├── scripts.py          # Script generation + ZIP download
│   │   ├── resources.py        # Resource list
│   │   └── costs.py            # Cost record list
│   ├── services/               # Azure SDK wrappers
│   │   ├── azure_auth.py       # ClientSecretCredential + Key Vault
│   │   ├── http_client.py      # Authenticated httpx wrapper
│   │   ├── resource_export.py  # Azure Resource Graph + ARM
│   │   ├── cost_export.py      # Azure Cost Management API
│   │   ├── metrics.py          # Azure Monitor metrics
│   │   └── storage.py          # Blob container service (DB + exports)
│   ├── config.py               # Pydantic Settings (env vars)
│   ├── database.py             # SQLAlchemy engine + session factory
│   ├── models.py               # ORM models
│   ├── schemas.py              # Pydantic response schemas
│   ├── dependencies.py         # FastAPI Depends factories
│   └── main.py                 # App + lifespan (blob sync)
├── dashboard/                  # React + Vite frontend
│   └── src/
├── infra/                      # Terraform (Azure Container Apps, ACR, KV, Storage)
│   ├── main.tf
│   ├── variables.tf
│   ├── container_app.tf
│   ├── keyvault.tf
│   ├── storage.tf
│   ├── acr.tf
│   └── outputs.tf
├── tests/                      # pytest unit tests (81% coverage)
├── .azuredevops/               # Azure DevOps pipeline
│   └── azure-pipelines.yml
├── Dockerfile.api
├── Dockerfile.job
├── docker-compose.yml
├── pyproject.toml
├── .env.example
└── DESIGN_AND_ARCHITECTURE.md  # Full design document
```

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | ≥ 3.11 | Backend runtime |
| [uv](https://docs.astral.sh/uv/) | latest | Fast Python package manager |
| Node.js | ≥ 18 | React dashboard |
| Docker Desktop | latest | Container builds |
| Terraform | ≥ 1.7 | Azure infra provisioning |
| Azure CLI | latest | Auth for local Terraform |

---

## Local Development

### 1. Clone and install dependencies

```bash
# Install uv (if not already installed)
pip install uv

# Install Python dependencies into a virtual environment
uv venv
uv pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your Azure credentials and resource names
```

### 3. Run the API

```bash
# Activate venv (Windows)
.venv\Scripts\activate

# Start uvicorn with the .env file
uvicorn api.main:app --env-file .env --reload --host 0.0.0.0 --port 8000
```

API docs available at: http://localhost:8000/docs

### 4. Run the dashboard

```bash
cd dashboard
npm install
npm run dev
```

Dashboard available at: http://localhost:5173

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values. **Never commit `.env`** — it is excluded by `.gitignore`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `AZURE_TENANT_ID` | ✅ | — | Azure AD tenant ID |
| `AZURE_CLIENT_ID` | ✅ | — | Service principal app ID |
| `AZURE_CLIENT_SECRET` | ✅ | — | Service principal secret |
| `AZURE_SUBSCRIPTION_ID` | ✅ | — | Target subscription |
| `AZURE_KEYVAULT_URL` | ✅ | — | Key Vault URI (e.g. `https://myvault.vault.azure.net/`) |
| `AZURE_STORAGE_ACCOUNT_URL` | ✅ | — | Blob storage URL |
| `KV_SECRET_DB_SAS` | | `storage-db-sas-token` | KV secret name holding DB container SAS |
| `KV_SECRET_EXPORTS_SAS` | | `storage-exports-sas-token` | KV secret name holding exports SAS |
| `AZURE_DB_CONTAINER_NAME` | | `optimizer-db` | Blob container for SQLite DB |
| `AZURE_EXPORTS_CONTAINER_NAME` | | `optimizer-exports` | Blob container for CSVs/scripts |
| `DATABASE_PROVIDER` | | `sqlite` | `sqlite` \| `postgresql` \| `mysql` \| `sqlserver` |
| `LOCAL_DB_PATH` | | `/tmp/optimizer.db` | Local path for SQLite file |
| `LOG_LEVEL` | | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |

---

## Running Tests

```bash
# Run all tests with coverage report
python -m pytest tests/ --cov=api --cov-report=html --cov-report=term -q

# HTML report written to htmlcov/index.html
```

Current coverage: **81%** across 162 tests.

| Layer | Coverage |
|---|---|
| Analysis (all 10 analyzers) | 91–100% |
| Config, Models, Schemas | 100% |
| HTTP Client | 99% |
| Azure Auth Service | 100% |
| Resource Export Service | 97% |
| Routers (dashboard, findings, costs, resources) | 100% |

---

## Docker

```bash
# Build and start both API and dashboard
docker compose up --build

# API:       http://localhost:8000
# Dashboard: http://localhost:5173
```

The compose file reads from `.env` automatically.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/jobs/extract-all` | Trigger full extraction + analysis pipeline |
| `GET` | `/api/v1/jobs` | List all job runs |
| `GET` | `/api/v1/jobs/{job_id}` | Get status of a specific job |
| `GET` | `/api/v1/dashboard/summary` | KPIs for the React dashboard |
| `GET` | `/api/v1/findings/` | All orphan/idle resource findings |
| `GET` | `/api/v1/resources/` | All discovered resources for the latest run |
| `GET` | `/api/v1/costs/` | All cost records for the latest run |
| `POST` | `/api/v1/scripts/generate` | Generate PowerShell remediation scripts |
| `GET` | `/api/v1/scripts/download-all` | Download all scripts as a ZIP archive |
| `GET` | `/health` | Health check (returns job count + status) |

Interactive Swagger UI: `http://localhost:8000/docs`

---

## Deploy to Azure

### Prerequisites

- Terraform ≥ 1.7 installed
- `az login` authenticated with a service principal that has Contributor + Key Vault Admin rights
- Azure Container Registry, Key Vault, and Storage Account already provisioned (referenced as data sources)

### Terraform

```bash
cd infra

terraform init

# Plan — pass secrets via CLI or a tfvars file (never commit terraform.tfvars)
terraform plan \
  -var="subscription_id=<SUB_ID>" \
  -var="tenant_id=<TENANT_ID>" \
  -var="client_id=<CLIENT_ID>" \
  -var="client_secret=<CLIENT_SECRET>" \
  -var="app_sp_object_id=<SP_OBJECT_ID>"

terraform apply
```

### Azure DevOps CI/CD

The pipeline in [`.azuredevops/azure-pipelines.yml`](.azuredevops/azure-pipelines.yml) does:

1. **Build** — Docker build + push to ACR for both `api` and `job` images
2. **Terraform Plan** — runs `terraform plan`, publishes plan artifact
3. **Terraform Apply** — applies plan to Azure Container Apps

All secrets (`CLIENT_SECRET`, `ACR_PASSWORD`) are stored in an **Azure DevOps Library group** named `cloud-cost-optimizer-secrets` — never hardcoded in YAML.

---

## Security

- **No secrets in code** — all credentials loaded from environment variables via `pydantic-settings`
- **`.env` excluded** from git — see `.gitignore`
- **`terraform.tfvars` excluded** from git — pass secrets via CI pipeline variables or `TF_VAR_*` env vars
- **Terraform state excluded** — `*.tfstate`, `*.tfstate.backup`, `*.tfplan` all in `.gitignore`
- **SAS tokens** stored in Azure Key Vault, fetched at runtime — never in env vars or code
- **`client_secret`** injected into Container App as a Container App secret reference, not a plaintext env var
- **`sensitive = true`** on all secret variables in `variables.tf`

> See [DESIGN_AND_ARCHITECTURE.md](DESIGN_AND_ARCHITECTURE.md) for the full system design including data flow, security architecture, and database schema.
