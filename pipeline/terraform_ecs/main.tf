# ============================================================
# ECS Cluster
# ============================================================

resource "aws_ecs_cluster" "pipeline" {
  name = "c20-lorenzo-t3-pipeline"
  
  tags = {
    Name    = "T3 Pipeline Cluster"
    Project = "T3 Data Migration"
  }
}

# ============================================================
# Dashboard Cluster (Separate from Pipeline)
# ============================================================

resource "aws_ecs_cluster" "dashboard" {
  name = "c20-lorenzo-t3-cluster"
  
  tags = {
    Name    = "T3 Dashboard Cluster"
    Project = "T3 Data Migration"
  }
}

# ============================================================
# ECR Repository - Stores your Docker images
# ============================================================

resource "aws_ecr_repository" "pipeline" {
  name                 = "c20-lorenzo-pipeline"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = false
  }
}

# ============================================================
# CloudWatch Log Group - Stores pipeline logs
# ============================================================

resource "aws_cloudwatch_log_group" "pipeline" {
  name              = "/ecs/c20-lorenzo-t3-pipeline"
  retention_in_days = 7
}

# ============================================================
# IAM Role - Task Execution Role (for ECS to start container)
# ============================================================

resource "aws_iam_role" "task_execution_role" {
  name = "c20-lorenzo-t3-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "task_execution_role_policy" {
  role       = aws_iam_role.task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow execution role to read secrets
resource "aws_iam_role_policy" "task_execution_secrets" {
  name = "secrets-access"
  role = aws_iam_role.task_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = "arn:aws:secretsmanager:eu-west-2:129033205317:secret:t3/database*"
    }]
  })
}

# ============================================================
# IAM Role - Task Role (for your Python code to access AWS)
# ============================================================

resource "aws_iam_role" "task_role" {
  name = "c20-lorenzo-t3-pipeline-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

# S3 access for data lake and state file
resource "aws_iam_role_policy" "task_role_s3" {
  name = "s3-access"
  role = aws_iam_role.task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ]
      Resource = [
        "arn:aws:s3:::c20-lorenzo-t3-data-lake",
        "arn:aws:s3:::c20-lorenzo-t3-data-lake/*"
      ]
    }]
  })
}

# Secrets Manager access for database credentials
resource "aws_iam_role_policy" "task_role_secrets" {
  name = "secrets-access"
  role = aws_iam_role.task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = "arn:aws:secretsmanager:eu-west-2:129033205317:secret:t3/database*"
    }]
  })
}

# ============================================================
# ECS Task Definition - Defines how to run your container
# ============================================================

resource "aws_ecs_task_definition" "pipeline" {
  family                   = "c20-lorenzo-t3-pipeline"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.task_execution_role.arn
  task_role_arn            = aws_iam_role.task_role.arn

  container_definitions = jsonencode([{
    name  = "t3-pipeline"
    image = "129033205317.dkr.ecr.eu-west-2.amazonaws.com/c20-lorenzo-pipeline:latest"

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.pipeline.name
        "awslogs-region"        = "eu-west-2"
        "awslogs-stream-prefix" = "ecs"
      }
    }

    essential = true
  }])
}

# ============================================================
# EventBridge Rule - Triggers pipeline every 3 hours
# ============================================================

resource "aws_cloudwatch_event_rule" "pipeline_schedule" {
  name                = "c20-lorenzo-t3-pipeline"
  description         = "Trigger C20 Lorenzo T3 pipeline every 3 hours"
  schedule_expression = "cron(0 */3 * * ? *)"
}

# ============================================================
# IAM Role - EventBridge Role (to trigger ECS tasks)
# ============================================================

resource "aws_iam_role" "eventbridge_role" {
  name = "c20-lorenzo-eventbridge"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "events.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_ecs" {
  name = "ecs-task-execution"
  role = aws_iam_role.eventbridge_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:RunTask"
        ]
        Resource = "arn:aws:ecs:eu-west-2:129033205317:task-definition/c20-lorenzo-t3-pipeline:*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          aws_iam_role.task_execution_role.arn,
          aws_iam_role.task_role.arn
        ]
      }
    ]
  })
}

# ============================================================
# EventBridge Target - Connects rule to ECS task
# ============================================================

resource "aws_cloudwatch_event_target" "pipeline" {
  rule     = aws_cloudwatch_event_rule.pipeline_schedule.name
  arn      = aws_ecs_cluster.pipeline.arn
  role_arn = aws_iam_role.eventbridge_role.arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.pipeline.arn
    launch_type         = "FARGATE"
    platform_version    = "LATEST"

    network_configuration {
      subnets = [
        "subnet-0c2e92c1b7b782543",
        "subnet-00c68b4e0ee285460",
        "subnet-0c47ef6fc81ba084a"
      ]
      security_groups  = ["sg-03c1565f34202b102"]
      assign_public_ip = true
    }
  }
}

# ============================================================
# DASHBOARD RESOURCES
# ============================================================

# Dashboard ECR Repository
resource "aws_ecr_repository" "dashboard" {
  name                 = "c20-lorenzo-t3-dashboard"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = false
  }
}

# Dashboard CloudWatch Log Group
resource "aws_cloudwatch_log_group" "dashboard" {
  name              = "/ecs/c20-lorenzo-t3-dashboard"
  retention_in_days = 7
}

# Dashboard Task Definition
resource "aws_ecs_task_definition" "dashboard" {
  family                   = "c20-lorenzo-t3-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = "arn:aws:iam::129033205317:role/ecsTaskExecutionRole"
  task_role_arn            = aws_iam_role.task_role.arn

  container_definitions = jsonencode([{
    name  = "c20-lorenzo-t3-dashboard-container" 
    image = "129033205317.dkr.ecr.eu-west-2.amazonaws.com/c20-lorenzo-t3-dashboard:latest"

    portMappings = [{
      containerPort = 8501
      hostPort      = 8501
      protocol      = "tcp"
    }]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.dashboard.name
        "awslogs-region"        = "eu-west-2"
        "awslogs-stream-prefix" = "ecs"
      }
    }

    essential = true
  }])
}

# Dashboard ECS Service
resource "aws_ecs_service" "dashboard" {
  name            = "c20-lorenzo-t3-task-service-2cuq5tdv" 
  cluster         = aws_ecs_cluster.dashboard.arn
  task_definition = aws_ecs_task_definition.dashboard.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets = [
      "subnet-0c2e92c1b7b782543",
      "subnet-00c68b4e0ee285460",
      "subnet-0c47ef6fc81ba084a"
    ]
    security_groups  = ["sg-033d41b73fcabf945"]  
    assign_public_ip = true
  }

  # Allow external changes without Terraform interference
  lifecycle {
    ignore_changes = [desired_count]
  }
}

# Outputs for Dashboard
output "dashboard_service_name" {
  value       = aws_ecs_service.dashboard.name
  description = "Name of the dashboard ECS service"
}

output "dashboard_ecr_url" {
  value       = aws_ecr_repository.dashboard.repository_url
  description = "ECR repository URL for dashboard image"
}