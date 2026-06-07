# Infrastructure (Terraform)

Currently this provisions the AWS Cognito user pool and app client used for authentication.
Full production infrastructure (S3, RDS, Qdrant Cloud references, EC2) is added in Phase 5.

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

## Prod pool

Use a separate state (workspace or backend) and `prod.tfvars`:

```
cp prod.tfvars.example prod.tfvars   # edit callback/logout URLs
terraform workspace new prod
terraform apply -var-file=prod.tfvars
```
