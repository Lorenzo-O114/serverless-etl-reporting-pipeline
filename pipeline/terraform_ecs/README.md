# T3 ETL Pipeline - ECS Deployment

Automated ETL pipeline running on AWS ECS Fargate every 3 hours via EventBridge.

---

## Prerequisites

- AWS CLI configured
- Terraform installed
- Docker installed
- AWS permissions: ECS, ECR, IAM, EventBridge, CloudWatch, S3, Secrets Manager

---

## Quick Deploy

### 1. Build and Push Image
```bash
docker buildx build --platform linux/amd64 \
  -t 129033205317.dkr.ecr.eu-west-2.amazonaws.com/c20-lorenzo-pipeline:latest \
  --push .
```

### 2. Deploy Infrastructure
```bash
cd terraform_ecs
terraform init
terraform plan
terraform apply
```

---

## Manual Test Run
```bash
# Run task manually
aws ecs run-task \
  --cluster c20-lorenzo-t3-pipeline \
  --task-definition c20-lorenzo-t3-pipeline \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-0c2e92c1b7b782543],securityGroups=[sg-03c1565f34202b102],assignPublicIp=ENABLED}"

# Watch logs
aws logs tail /ecs/c20-lorenzo-t3-pipeline --follow
```

---

## Monitoring
```bash
# Check schedule
aws events describe-rule --name c20-lorenzo-t3-pipeline

# View logs
aws logs tail /ecs/c20-lorenzo-t3-pipeline --since 1h

# Check state
aws s3 cp s3://c20-lorenzo-t3-data-lake/pipeline-state/last_run.txt -
```

---

## How It Works

1. EventBridge triggers ECS task every 3 hours
2. Task reads last processed timestamp from S3
3. Extracts new data from RDS (incremental)
4. Transforms and uploads to S3 Data Lake
5. Updates state file with latest timestamp
6. Task stops (pay-per-use)

**State file:** `s3://c20-lorenzo-t3-data-lake/pipeline-state/last_run.txt`

---

## Troubleshooting

**Task won't start:** Check ECR image exists and Task Definition has correct image URI  
**Permission errors:** Verify IAM roles have S3, RDS, Secrets Manager access  
**No new data:** Expected if trucks haven't reported since last run  
**Missing data:** Reset state file to earlier timestamp and re-run

---

## Terraform Resources Created

- ECR Repository: `c20-lorenzo-pipeline`
- ECS Task Definition: `c20-lorenzo-t3-pipeline`
- CloudWatch Log Group: `/ecs/c20-lorenzo-t3-pipeline`
- EventBridge Rule: `c20-lorenzo-t3-pipeline` (every 3 hours)
- 3 IAM Roles (Task Execution, Task, EventBridge)