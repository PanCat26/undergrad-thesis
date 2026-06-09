data "aws_caller_identity" "current" {}

locals {
  # Bucket names are globally unique; suffix with the account id unless overridden.
  sources_bucket = var.sources_bucket_name != "" ? var.sources_bucket_name : "${local.name_prefix}-sources-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket" "sources" {
  bucket = local.sources_bucket
}

resource "aws_s3_bucket_public_access_block" "sources" {
  bucket                  = aws_s3_bucket.sources.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "sources" {
  bucket = aws_s3_bucket.sources.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "sources" {
  bucket = aws_s3_bucket.sources.id
  versioning_configuration {
    status = "Enabled"
  }
}
