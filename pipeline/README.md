# T3 Data Migration Project
## Overview
Migration of T3's transaction data from MySQL RDS to AWS S3 data lake architecture for cost reduction and scalability.

## Quick Start
### Prerequisites

    pip install -r requirements.txt
    aws configure  # Set up AWS credentials

### Run Pipeline

    # Local execution
    python3 pipeline.py

    # Docker execution
    docker buildx build -t t3-pipeline .
    docker run -v ~/.aws:/root/.aws:ro -v $(pwd)/data:/app/data t3-pipeline

## Run Dashboard

Local

    streamlit run dashboard.py

Docker

    docker buildx build -f Dockerfile.dashboard -t t3-dashboard .
    docker run -p 8501:8501 -v ~/.aws:/root/.aws:ro t3-dashboard
Access at http://localhost:8501

## Deploy Infrastructure

    cd terraform
    terraform init
    terraform apply

## Project Structure

    ├── ETL/
    │   ├── extract.py                # Extract from MySQL RDS
    │   ├── transform.py              # Clean data
    │   ├── partition_transactions.py # Create time-partitioned parquet
    │   └── load.py                   # Upload to S3
    ├── dashboard.py                  # Streamlit dashboard
    ├── Dockerfile                    # Pipeline container
    ├── Dockerfile.dashboard          # Dashboard container
    ├── terraform/main.tf             # Infrastructure as code
    └── data/                         # Local data storage

## Stakeholder Insights
__Hiram (CFO)__ - S3 saves ~70% vs RDS, Athena pay-per-query, peak hours identified (11am-2pm, 5pm-7pm)

__Miranda (Culinary)__ - Dashboard shows truck performance, pricing insights, optimal positioning times

__Alexander (Tech)__ - S3 + Glue + Athena + Streamlit on ECS, Docker + Terraform, Secrets Manager for credentials

## Key Features
- Time-partitioned Parquet files for efficient queries
- AWS Glue crawler for automated schema discovery
- Interactive dashboard with filters and caching
- Automated data quality checks
- Production-ready containerized deployment
## AWS Resources
- S3 bucket (data lake)
- Glue Database and Crawler
- Secrets Manager (t3/database)
- IAM roles and policies
- ECR repository (dashboard image)
- ECS service (dashboard hosting)
