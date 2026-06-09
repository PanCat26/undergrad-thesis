# Agentic Research Tool

An agentic research workspace: a LaTeX editor (Overleaf-like), a library of uploaded sources
(papers and datasets), and an LLM agent that performs grounded, citation-backed research and
literature review over the uploaded material and the current draft.

The codebase is built in phases: foundation + auth (1), LaTeX workspace (2), sources library +
ingestion (3), the grounded Ask/Agent assistant (4), and production hardening + abuse guardrails (5).

## Stack

| Layer     | Technology                                            |
| --------- | ----------------------------------------------------- |
| Frontend  | Next.js (App Router), React, Tailwind, shadcn/ui      |
| Backend   | FastAPI, async SQLAlchemy, Alembic                    |
| Auth      | AWS Cognito (real dev and prod user pools)            |
| Datastore | PostgreSQL (relational), Qdrant (vectors, from Ph. 3) |
| Agent     | LangChain + OpenAI (`gpt-4.1-mini`), from Phase 4     |
| Infra     | Docker Compose (dev), single EC2 + Terraform (prod)   |

## Repository layout

```
backend/    FastAPI service, models, migrations, agent, abuse guardrails
frontend/   Next.js app
infra/       Terraform (Cognito, S3, EC2)
docs/        Additional documentation (incl. DEPLOY.md)
```

## Local development

### Prerequisites

- Docker and Docker Compose
- An AWS account with credentials allowed to create and call a Cognito user pool
- Terraform (only to create the dev Cognito pool)

### 1. Create the dev Cognito user pool

The backend validates real Cognito tokens, so a dev user pool must exist before auth works.

```
cd infra/terraform
terraform init
terraform apply -var-file=dev.tfvars
```

Copy the `user_pool_id` and `client_id` outputs.

### 2. Configure environment

```
cp .env.example .env
```

Fill in `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `COGNITO_USER_POOL_ID`, and
`COGNITO_CLIENT_ID` from the Terraform outputs. The rest have working dev defaults.

### 3. Start the stack

```
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API + docs: http://localhost:8000/docs
- The backend applies Alembic migrations automatically on startup.

## Testing

Backend (in a virtual environment):

```
cd backend
python -m venv .venv
. .venv/Scripts/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

Frontend:

```
cd frontend
npm install
npm test
```

## Production deployment

Production runs on a single EC2 host via `docker-compose.prod.yml` (Caddy with automatic HTTPS,
the frontend, the backend, and Postgres + Qdrant as containers), with source files in **S3** and a
prod **Cognito** pool. See [`docs/DEPLOY.md`](docs/DEPLOY.md) for the full runbook.

## Abuse guardrails

Because Guest mode is unauthenticated, the cost-bearing endpoints (chat/LLM, upload, compile) are
rate-limited per identity (guests far tighter than registered users), guest-session creation is
throttled per IP, and a global daily circuit breaker bounds total LLM usage. Counters live in
Postgres; limits are in `backend/app/core/ratelimit.py`. In prod the app refuses to start unless
`GUEST_TOKEN_SECRET` and the other required secrets are set.

## Environment split (dev vs prod)

`APP_ENV` and the per-service variables switch behaviour: local disk vs **S3** for source storage,
and the dev vs prod **Cognito** pool. Postgres and Qdrant run as containers in both dev and prod.
Application code stays the same; only configuration changes.
