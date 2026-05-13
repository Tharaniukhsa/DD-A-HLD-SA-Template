terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "eu-west-2"
}

# Generated from Confluence architecture page
resource "aws_s3_bucket" "data_lake" {
  bucket = "ukhsa-data-lake"
}

resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_kms_key" "data_key" {
  description = "KMS key for data solution"
}

# Components discovered: 9
# Datasets discovered: 3
# Data lake pattern present: false
