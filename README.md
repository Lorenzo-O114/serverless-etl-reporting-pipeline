# Serverless ETL Reporting Pipeline

Production-grade AWS data lake platform with automated ETL pipeline, Lambda-based reporting, and real-time analytics dashboard. Built with ECS Fargate, Step Functions, and Terraform infrastructure as code.

## Architecture

```
MySQL RDS → Extract (ECS Fargate) → Transform → Partition (Parquet) → S3 Data Lake
                                                                          ↓
                                              Lambda Report ← Athena → Streamlit Dashboard
                                                   ↓
                                              Email (SES)
```

### Key Components

- **ETL Pipeline (ECS Fargate)**: Scheduled extraction from MySQL RDS with incremental state management, data transformation, and time-partitioned Parquet storage
- **Lambda Report Generator**: Automated daily HTML reports with Step Functions orchestration and SES email delivery
- **Analytics Dashboard**: Interactive Streamlit dashboard with 1-hour caching for cost optimization
- **Infrastructure as Code**: Complete Terraform modules for S3 data lake, ECS cluster, Lambda functions, and EventBridge scheduling
- **Data Lake**: Time-partitioned Parquet files (year/month/day) with AWS Glue catalog integration

## Features

- Incremental ETL with state management (processes only new transactions)
- Serverless architecture (ECS Fargate + Lambda)
- Cost-optimized Parquet storage with time partitioning
- Automated daily reports with email delivery at 9:30 AM UTC
- Real-time dashboard with revenue metrics, truck performance, and time-based analysis
- AWS Secrets Manager integration for secure credential management
- Error handling with automatic retries (Step Functions)
- CloudWatch logging and monitoring

## Tech Stack

**AWS Services**: S3, ECS Fargate, Lambda, Step Functions, Athena, Glue, SES, EventBridge, Secrets Manager, CloudWatch

**Languages & Tools**: Python 3.13, Terraform, Docker, Streamlit, Pandas, PyArrow, AWS Wrangler

**Data Format**: Parquet (time-partitioned)

## Project Structure

```
serverless-etl-reporting-pipeline/
├── pipeline/
│   ├── ETL/
│   │   ├── extract.py              # RDS incremental extraction
│   │   ├── transform.py            # Data cleaning and normalization
│   │   ├── partition_transactions.py # Time-partitioned Parquet creation
│   │   ├── load.py                 # S3 upload (fact + dimension tables)
│   │   └── pipeline.py             # Orchestration script
│   │
│   ├── report-lambda/
│   │   ├── generate_report.py      # HTML report generation
│   │   ├── Dockerfile              # Lambda container (ARM64)
│   │   └── requirements.txt        # Lambda dependencies
│   │
│   ├── terraform_s3/
│   │   ├── main.tf                 # S3 data lake, IAM policies
│   │   └── provider.tf
│   │
│   ├── terraform_ecs/
│   │   ├── main.tf                 # ECS cluster, task def, EventBridge
│   │   ├── provider.tf
│   │   └── README.md
│   │
│   ├── terraform_lambda/
│   │   ├── main.tf                 # Lambda, Step Functions, SES
│   │   ├── provider.tf
│   │   └── README.md
│   │
│   ├── dashboard.py                # Streamlit analytics dashboard
│   ├── dockerfile                  # ETL pipeline container
│   ├── Dockerfile.dashboard        # Dashboard container
│   ├── requirements.txt            # Python dependencies
│   └── athena_queries.sql          # Pre-built SQL queries
│
├── .gitignore
├── .pylintrc                       # PEP8 enforcement
└── README.md
```

## Quick Start

### Prerequisites

- AWS CLI configured (`aws configure`)
- Terraform >= 1.0
- Docker with buildx support
- Python 3.13+

### 1. Deploy S3 Data Lake

```bash
cd pipeline/terraform_s3
terraform init
terraform apply
```

### 2. Setup Database Credentials

Store MySQL credentials in AWS Secrets Manager:

```bash
aws secretsmanager create-secret \
  --name t3/database \
  --secret-string '{"DB_HOST":"your-rds-endpoint","DB_PORT":"3306","DB_USER":"admin","DB_PASSWORD":"password","DB_NAME":"transactions"}'
```

### 3. Build and Push ETL Pipeline Image

```bash
cd pipeline
docker buildx build --platform linux/amd64 -t <your-ecr-repo>:latest --push .
```

### 4. Deploy ECS Pipeline

```bash
cd terraform_ecs
terraform init
terraform apply
# Runs every 3 hours via EventBridge
```

### 5. Deploy Lambda Report Generator

```bash
cd pipeline/report-lambda
docker buildx build --platform linux/arm64 -t <your-ecr-repo>/report-lambda:latest --push .

cd ../terraform_lambda
terraform init
terraform apply
# Sends daily reports at 9:30 AM UTC
```

### 6. Run Dashboard Locally

```bash
cd pipeline
pip install -r requirements.txt
streamlit run dashboard.py
# Access at http://localhost:8501
```

Or with Docker:

```bash
docker buildx build -f Dockerfile.dashboard -t dashboard .
docker run -p 8501:8501 -v ~/.aws:/root/.aws:ro dashboard
```

## Usage

### Manual Pipeline Execution

```bash
# Run ETL pipeline locally
cd pipeline/ETL
python pipeline.py

# Trigger ECS task
aws ecs run-task \
  --cluster <cluster-name> \
  --task-definition <task-name> \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[<subnet-id>],securityGroups=[<sg-id>],assignPublicIp=ENABLED}"
```

### Trigger Report Generation

```bash
aws stepfunctions start-execution \
  --state-machine-arn <state-machine-arn> \
  --name manual-test-$(date +%s)
```

### Query Data Lake with Athena

```sql
-- Example: Daily revenue by truck
SELECT
    DATE(timestamp) as date,
    truck_name,
    SUM(total) as daily_revenue
FROM t3_data_lake.transactions t
JOIN t3_data_lake.dim_trucks dt ON t.truck_id = dt.truck_id
WHERE year = 2024 AND month = 10
GROUP BY DATE(timestamp), truck_name
ORDER BY date DESC, daily_revenue DESC;
```

More queries available in `pipeline/athena_queries.sql`

## Monitoring

```bash
# View ECS pipeline logs
aws logs tail /ecs/<task-name> --follow

# View Lambda logs
aws logs tail /aws/lambda/<function-name> --follow

# Check pipeline state
aws s3 cp s3://<bucket-name>/pipeline-state/last_run.txt -

# List generated reports
aws s3 ls s3://<bucket-name>/reports/
```

## Data Lake Structure

```
s3://<bucket-name>/
├── transactions/
│   └── year=YYYY/month=M/day=D/*.parquet  # Time-partitioned fact table
├── dim_trucks/*.parquet                    # Truck dimension table
├── dim_payment_methods/*.parquet           # Payment methods dimension
├── pipeline-state/
│   └── last_run.txt                        # Incremental extraction state
└── reports/
    └── daily-report-YYYY-MM-DD.html        # Generated reports
```

## Configuration

### Environment Variables

- **ECS Pipeline**: Uses IAM role for AWS credentials
- **Lambda**: ARM64 architecture, 512MB memory, 5-minute timeout
- **Dashboard**: 1-hour cache TTL for Athena queries

### Customization

- **ETL Schedule**: Modify EventBridge cron in `terraform_ecs/main.tf` (default: every 3 hours)
- **Report Schedule**: Modify EventBridge cron in `terraform_lambda/main.tf` (default: 9:30 AM UTC daily)
- **Email Recipients**: Update SES configuration in `terraform_lambda/main.tf`

## Cost Optimization

- Parquet format reduces storage by ~70% vs CSV
- Time partitioning minimizes Athena scan costs
- Incremental extraction (state-based) reduces processing time
- Dashboard caching reduces Athena query frequency
- Serverless architecture (pay-per-execution)

**Estimated Monthly Cost**: < $10 (1M transactions, daily reports)

## Troubleshooting

### Pipeline Not Running

```bash
# Check EventBridge schedule
aws events describe-rule --name <rule-name>

# Check ECS task status
aws ecs describe-tasks --cluster <cluster-name> --tasks <task-arn>
```

### Email Not Received

- Verify SES email addresses in AWS Console (sandbox mode requires verification)
- Check Step Functions execution logs
- Check spam folder

### No Data in Dashboard

```bash
# Verify Glue crawler ran successfully
aws glue get-crawler --name <crawler-name>

# Check S3 for recent data
aws s3 ls s3://<bucket-name>/transactions/year=2024/ --recursive
```

## Development

### Code Quality

- PEP8 style guide enforced via `.pylintrc`
- All functions follow single responsibility principle
- Comprehensive error handling with logging

### Testing Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run ETL steps individually
cd pipeline/ETL
python extract.py
python transform.py
python partition_transactions.py
python load.py
```

## License

MIT License - Feel free to use this project as a reference for your own data lake implementations.

## Acknowledgments

Built as part of a data engineering coursework project demonstrating production-grade AWS architecture, infrastructure as code, and serverless computing best practices.
