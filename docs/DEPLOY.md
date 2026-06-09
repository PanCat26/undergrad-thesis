# Production deployment (single EC2)

The production stack runs on **one EC2 host** via `docker-compose.prod.yml`: **Caddy** (automatic
HTTPS), the **Next.js frontend**, the **FastAPI backend**, and **Postgres + Qdrant** as containers.
Uploaded source files live in **S3**; authentication uses a **prod Cognito** pool. Abuse guardrails
(rate limits + a global LLM circuit breaker) are always on in prod.

```
            ┌─────────────── EC2 host ───────────────┐
 Internet → │ Caddy (443/80, TLS)                     │
   (domain) │   ├─ /            → frontend:3000        │
            │   └─ /api,/health → backend:8000         │
            │ backend ─ Postgres ─ Qdrant (containers) │
            └──────────────┬───────────────────────────┘
                           └── S3 (source files), Cognito (auth)
```

## Prerequisites
- An AWS account + credentials (locally, for Terraform).
- A **domain** you control (for TLS).
- An **OpenAI API key**.
- Terraform ≥ 1.6 and the AWS CLI installed locally.

## 1. Provision AWS (Terraform)
From `infra/terraform/`:
```bash
cp prod.tfvars.example prod.tfvars   # set domain, callback/logout URLs, ssh_allow_cidr, key_name
terraform workspace new prod         # keep prod state separate from dev
terraform apply -var-file=prod.tfvars
```
This creates: the prod **Cognito** pool + client, the private **S3** bucket, and the **EC2** host
(security group, instance role with S3 + SSM access, Elastic IP). Note the outputs:
```bash
terraform output     # user_pool_id, client_id, sources_bucket, ec2_public_ip, instance_id
```

## 2. DNS
Create an **A record** for your domain pointing at `ec2_public_ip`. Caddy needs this resolvable to
issue the Let's Encrypt certificate.

## 3. Get on the host
Either SSH (if you set `key_name` and `ssh_allow_cidr`) or, with no open SSH, use Session Manager:
```bash
aws ssm start-session --target <instance_id>
```
The `user_data` script already installed Docker, the compose plugin, and the AWS CLI.

## 4. Deploy the app
```bash
sudo -iu ec2-user
cd /opt/app
git clone <your-repo-url> .        # or scp the repo here

cp .env.prod.example .env.prod && chmod 600 .env.prod
# Fill .env.prod from the Terraform outputs + your secrets:
#   DOMAIN, ACME_EMAIL, CORS_ORIGINS, NEXT_PUBLIC_API_BASE_URL  → https://<domain>
#   POSTGRES_PASSWORD + matching DATABASE_URL                   → a strong password
#   STORAGE_BACKEND=s3, S3_BUCKET=<sources_bucket>, AWS_REGION  (leave AWS keys EMPTY → instance role)
#   COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID
#   OPENAI_API_KEY
#   GUEST_TOKEN_SECRET → a long random string (the app refuses to start in prod with the default)

docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```
The backend entrypoint runs `alembic upgrade head` automatically before serving.

## 5. Verify
```bash
curl -fsS https://<domain>/health         # {"status":"ok","env":"prod"}
```
In a browser: continue as guest → ask a question → upload a source → compile. Then sanity-check the
guardrail: send chat messages rapidly as a guest and confirm you get **HTTP 429** after the burst
cap (per-scope limits are in `backend/app/core/ratelimit.py`).

## 6. Backups (cron)
Postgres holds the irreplaceable data; source files are already durable in S3, and Qdrant vectors can
be rebuilt by re-ingesting sources. Schedule the dump-to-S3 script:
```bash
crontab -e
# 0 3 * * * cd /opt/app && ./scripts/backup.sh >> /var/log/app-backup.log 2>&1
```

## Operations
- **Redeploy:** `git pull && docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build`
- **Logs:** `docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f backend`
- **Restore Postgres:** `gunzip -c pg-<stamp>.sql.gz | docker compose ... exec -T postgres psql -U app app`
- **Secrets:** keep `.env.prod` at `chmod 600`, never commit it. For stronger handling, move secrets
  to SSM Parameter Store (the instance role already allows SSM) and template them in at deploy time.
- **Teardown:** `terraform destroy -var-file=prod.tfvars` (empty the S3 bucket first; it has versioning).

## Notes
- **TLS** is fully automatic via Caddy + Let's Encrypt once DNS resolves to the host.
- **No static AWS keys** in prod: leaving `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` empty makes
  boto3 use the EC2 instance role for S3 (and Cognito) calls.
- **Tectonic** downloads its TeX bundle on the first compile (needs outbound internet once).
