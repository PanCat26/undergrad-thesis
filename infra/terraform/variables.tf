variable "aws_region" {
  description = "AWS region for the Cognito user pool"
  type        = string
  default     = "eu-central-1"
}

variable "environment" {
  description = "Environment name, used to namespace resources (e.g. dev, prod)"
  type        = string
}

variable "callback_urls" {
  description = "Allowed OAuth callback URLs for the app client"
  type        = list(string)
  default     = ["http://localhost:3000"]
}

variable "logout_urls" {
  description = "Allowed logout URLs for the app client"
  type        = list(string)
  default     = ["http://localhost:3000"]
}
