# T3 Report Pipeline - Automated Email Delivery

Automated daily report generation and email delivery using AWS Lambda, Step Functions, and SES.

## Architecture

```
EventBridge (9:30 AM UTC) → Step Functions → Lambda (Generate Report) → SES (Send Email)
```

**Components:** Lambda (HTML report generation) | Step Functions (orchestration) | SES (email delivery) | EventBridge (daily trigger at 9:30 AM UTC)

## Setup

### 1. Verify Email Addresses
```bash
aws ses verify-email-identity --email-address sl-coaches@proton.me --region eu-west-2
aws ses verify-email-identity --email-address trainee.lorenzo.okpewo@sigmalabs.co.uk --region eu-west-2
```

### 2. Build and Push Docker Image (ARM64)
```bash
cd pipeline/report-lambda
aws ecr get-login-password --region eu-west-2 | docker login --username AWS --password-stdin 129033205317.dkr.ecr.eu-west-2.amazonaws.com
docker buildx build --platform linux/arm64 --provenance=false --sbom=false -t 129033205317.dkr.ecr.eu-west-2.amazonaws.com/c20-lorenzo-report-lambda:latest --push .
```

### 3. Deploy Infrastructure
```bash
cd ../terraform_lambda
terraform init
terraform apply
```

**Creates:** Lambda function, Step Functions state machine, ECR repository, IAM roles, EventBridge rule (9:30 AM UTC daily), CloudWatch log groups

## Operations

### Manual Execution
```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:eu-west-2:129033205317:stateMachine:c20-lorenzo-report-pipeline \
  --name manual-test-$(date +%s)
```

### Monitoring
```bash
# Stream logs
aws logs tail /aws/lambda/c20-lorenzo-report-generator --follow
aws logs tail /aws/stepfunctions/c20-lorenzo-report-pipeline --follow

# Check schedule
aws events describe-rule --name c20-lorenzo-daily-report
```

### Update Lambda Code
```bash
cd pipeline/report-lambda
docker buildx build --platform linux/arm64 --provenance=false --sbom=false -t 129033205317.dkr.ecr.eu-west-2.amazonaws.com/c20-lorenzo-report-lambda:latest --push .
aws lambda update-function-code --function-name c20-lorenzo-report-generator \
  --image-uri 129033205317.dkr.ecr.eu-west-2.amazonaws.com/c20-lorenzo-report-lambda:latest
```

## Troubleshooting

**Email not received:** Check SES verification, spam folder, and Step Functions logs
**Lambda errors:** `aws logs tail /aws/lambda/c20-lorenzo-report-generator --since 30m --filter-pattern ERROR`
**Architecture error:** Ensure Docker image is built for `linux/arm64` (not `amd64`)
**No data:** Check S3 for yesterday's transactions: `aws s3 ls s3://c20-lorenzo-t3-data-lake/transactions/`

## Email Details
- **Subject:** T3 Daily Report - YYYY-MM-DD - £X,XXX.XX Revenue
- **From:** sl-coaches@proton.me
- **To:** trainee.lorenzo.okpewo@sigmalabs.co.uk
- **Schedule:** Daily at 9:30 AM UTC, reporting previous day's transactions
- **Retry:** 3 attempts with exponential backoff
