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

# --- Phase 5: production host (EC2) + source storage (S3) -------------------------------------

variable "domain" {
  description = "Public domain the app is served on (informational; used for outputs/notes)"
  type        = string
  default     = ""
}

variable "instance_type" {
  description = "EC2 instance type for the all-in-one host"
  type        = string
  default     = "t3.small"
}

variable "ssh_allow_cidr" {
  description = "CIDR allowed to reach SSH (port 22). Restrict to your IP; SSM works without SSH."
  type        = string
  default     = "0.0.0.0/0"
}

variable "key_name" {
  description = "Existing EC2 key pair name for SSH (optional; leave empty to use SSM only)"
  type        = string
  default     = ""
}

variable "sources_bucket_name" {
  description = "S3 bucket name for source files (optional; derived from account id if empty)"
  type        = string
  default     = ""
}
