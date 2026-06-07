output "user_pool_id" {
  description = "Cognito user pool id (set as COGNITO_USER_POOL_ID)"
  value       = aws_cognito_user_pool.this.id
}

output "client_id" {
  description = "Cognito app client id (set as COGNITO_CLIENT_ID)"
  value       = aws_cognito_user_pool_client.this.id
}

output "aws_region" {
  description = "Region the pool was created in (set as AWS_REGION)"
  value       = var.aws_region
}
