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

output "sources_bucket" {
  description = "S3 bucket for source files (set as S3_BUCKET)"
  value       = aws_s3_bucket.sources.id
}

output "ec2_public_ip" {
  description = "Elastic IP of the app host (point your domain's A record here)"
  value       = aws_eip.app.public_ip
}

output "instance_id" {
  description = "EC2 instance id (for SSM Session Manager)"
  value       = aws_instance.app.id
}
