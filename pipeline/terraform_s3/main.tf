# This file tells Terraform to create an S3 bucket for our data lake

# Configure AWS as our cloud provider
# This tells Terraform we want to create resources in AWS
provider "aws" {
  region = "eu-west-2"  # London region (change if needed)
}

# Create an S3 bucket
# Think of this as creating a folder in the cloud to store files
resource "aws_s3_bucket" "t3_data_lake" {
  # Bucket name - MUST be globally unique across ALL of AWS
  # Change "your-name" to something unique to you
  bucket = "c20-lorenzo-t3-data-lake"
  
  # Tags help you identify and organize resources
  tags = {
    Name        = "T3 Data Lake"
    Project     = "Data Migration"
    Environment = "Production"
  }
}

# Enable versioning on the bucket
# This keeps old versions of files if you accidentally overwrite them
resource "aws_s3_bucket_versioning" "t3_versioning" {
  bucket = aws_s3_bucket.t3_data_lake.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

# Output the bucket name so we can use it in our Python scripts
# After running terraform apply, this will print the bucket name
output "bucket_name" {
  value       = aws_s3_bucket.t3_data_lake.bucket
  description = "Name of the S3 bucket"
}

output "bucket_arn" {
  value       = aws_s3_bucket.t3_data_lake.arn
  description = "ARN of the S3 bucket (unique identifier)"
}

# IAM policy to allow reading secrets from Secrets Manager
resource "aws_iam_policy" "secrets_access" {
  name        = "t3-secrets-manager-access"
  description = "Allow access to T3 database secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:eu-west-2:*:secret:t3/database-*"
      }
    ]
  })
}

# ========== AWS GLUE RESOURCES ==========

# Create Glue Database
# This is like a schema that organizes your tables
resource "aws_glue_catalog_database" "t3_database" {
  name        = "c20-lorenzo-t3-trucks"
  description = "Database for T3 food truck transaction data"
}

# IAM Role for Glue Crawler
# The crawler needs permissions to read S3 and write to Glue catalog
resource "aws_iam_role" "glue_crawler_role" {
  name = "AWSGlueServiceRole-t3"

  # This policy allows Glue service to assume this role
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# Attach AWS managed policy for Glue service
resource "aws_iam_role_policy_attachment" "glue_service_policy" {
  role       = aws_iam_role.glue_crawler_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Custom policy to allow Glue to read from our S3 bucket
resource "aws_iam_role_policy" "glue_s3_policy" {
  name = "AWSGlueServiceRole-c20-lorenzo"
  role = aws_iam_role.glue_crawler_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.t3_data_lake.arn,
          "${aws_s3_bucket.t3_data_lake.arn}/*"
        ]
      }
    ]
  })
}

# Create Glue Crawler
# This automatically discovers schema from parquet files in S3
resource "aws_glue_crawler" "t3_crawler" {
  name          = "c20-lorenzo-t3-crawler"
  role          = aws_iam_role.glue_crawler_role.arn
  database_name = aws_glue_catalog_database.t3_database.name

  # Crawl the entire S3 bucket
  s3_target {
    path = "s3://${aws_s3_bucket.t3_data_lake.bucket}/"
  }

  # Configuration to handle partitioned data
  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "UPDATE_IN_DATABASE"
  }

  tags = {
    Name    = "T3 Data Lake Crawler"
    Project = "Data Migration"
  }
}

# Output the Glue database name
output "glue_database_name" {
  value       = aws_glue_catalog_database.t3_database.name
  description = "Name of the Glue database"
}

# Output the crawler name
output "glue_crawler_name" {
  value       = aws_glue_crawler.t3_crawler.name
  description = "Name of the Glue crawler"
}