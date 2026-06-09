# Infrastructure (Terraform)

This provisions the AWS resources for the app:

- **Cognito** user pool + app client (`cognito.tf`) — authentication.
- **S3** private bucket for uploaded source files (`s3.tf`).
- **EC2** single host running the docker-compose prod stack, with a security group, an
  **instance role** (S3 access + SSM Session Manager), and an **Elastic IP** (`ec2.tf`).

Postgres and Qdrant are **not** AWS resources — they run as containers on the EC2 host
(`docker-compose.prod.yml`). The end-to-end deploy steps live in [`docs/DEPLOY.md`](../../docs/DEPLOY.md).

> **State:** by default state is the local `terraform.tfstate`. For prod, copy `backend.tf.example`
> to `backend.tf` to store state in S3 with locking.

## Create the dev Cognito pool

```
terraform init
terraform apply -var-file=dev.tfvars
```

Then copy the outputs into the root `.env`:

| Output         | Environment variable    |
| -------------- | ----------------------- |
| `user_pool_id` | `COGNITO_USER_POOL_ID`  |
| `client_id`    | `COGNITO_CLIENT_ID`     |
| `aws_region`   | `AWS_REGION`            |

The app client is created without a secret, so `COGNITO_CLIENT_SECRET` stays empty.

## Prod (Cognito + S3 + EC2)

Use a separate state (workspace or the S3 backend) and `prod.tfvars`:

```
cp prod.tfvars.example prod.tfvars   # set domain, callback/logout URLs, ssh_allow_cidr, key_name
terraform workspace new prod
terraform apply -var-file=prod.tfvars
```

Key outputs → where they go:

| Output           | Used for                                             |
| ---------------- | ---------------------------------------------------- |
| `user_pool_id`   | `COGNITO_USER_POOL_ID` in `.env.prod`                |
| `client_id`      | `COGNITO_CLIENT_ID` in `.env.prod`                   |
| `sources_bucket` | `S3_BUCKET` in `.env.prod`                            |
| `ec2_public_ip`  | DNS **A record** for your domain                     |
| `instance_id`    | `aws ssm start-session --target <id>` to shell in    |
