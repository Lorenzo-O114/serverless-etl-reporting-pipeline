# ============================================================
# ECR Repository for Lambda Container Image
# ============================================================

resource "aws_ecr_repository" "report_lambda" {
  name                 = "c20-lorenzo-report-lambda"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = false
  }

  tags = {
    Name    = "T3 Report Lambda"
    Project = "T3 Data Migration"
  }
}

# ============================================================
# CloudWatch Log Group
# ============================================================

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/c20-lorenzo-report-generator"
  retention_in_days = 7

  tags = {
    Name    = "T3 Report Generator Logs"
    Project = "T3 Data Migration"
  }
}

# ============================================================
# IAM Role - Lambda Execution Role
# ============================================================

resource "aws_iam_role" "lambda_execution" {
  name = "c20-lorenzo-report-generator-role-qy6vxyr7"
  path = "/service-role/"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = {
    Name    = "T3 Report Lambda Role"
    Project = "T3 Data Migration"
  }
}

# Attach basic Lambda execution policy (for CloudWatch Logs)
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# S3 access for reading data and writing reports
resource "aws_iam_role_policy" "lambda_s3" {
  name = "s3AccessPolicy"
  role = aws_iam_role.lambda_execution.id

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

# ============================================================
# Lambda Function (Container Image)
# ============================================================

resource "aws_lambda_function" "report_generator" {
  function_name = "c20-lorenzo-report-generator"
  role          = aws_iam_role.lambda_execution.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.report_lambda.repository_url}:latest"

  timeout     = 300  # 5 minutes
  memory_size = 512  # MB

  environment {
    variables = {
      S3_BUCKET = "c20-lorenzo-t3-data-lake"
    }
  }

  tags = {
    Name    = "T3 Daily Report Generator"
    Project = "T3 Data Migration"
  }
}

# ============================================================
# CloudWatch Log Group for Step Functions
# ============================================================

resource "aws_cloudwatch_log_group" "step_functions" {
  name              = "/aws/stepfunctions/c20-lorenzo-report-pipeline"
  retention_in_days = 7

  tags = {
    Name    = "T3 Report Pipeline Step Functions Logs"
    Project = "T3 Data Migration"
  }
}

# ============================================================
# IAM Role - Step Functions Execution Role
# ============================================================

resource "aws_iam_role" "step_functions_execution" {
  name = "c20-lorenzo-report-pipeline-sfn-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "states.amazonaws.com"
      }
    }]
  })

  tags = {
    Name    = "T3 Report Pipeline Step Functions Role"
    Project = "T3 Data Migration"
  }
}

# Step Functions policy - invoke Lambda, send SES emails, CloudWatch logs
resource "aws_iam_role_policy" "step_functions_policy" {
  name = "step-functions-execution-policy"
  role = aws_iam_role.step_functions_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = aws_lambda_function.report_generator.arn
      },
      {
        Effect = "Allow"
        Action = [
          "ses:SendEmail",
          "ses:SendRawEmail"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

# ============================================================
# Step Functions State Machine
# ============================================================

resource "aws_sfn_state_machine" "report_pipeline" {
  name     = "c20-lorenzo-report-pipeline"
  role_arn = aws_iam_role.step_functions_execution.arn

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.step_functions.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  definition = jsonencode({
    Comment = "T3 Daily Report Pipeline - Generate report and send via email"
    StartAt = "GenerateReport"
    States = {
      GenerateReport = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.report_generator.function_name
          Payload = {
            "triggerSource" = "stepfunctions"
          }
        }
        ResultPath = "$.lambdaResult"
        Next       = "ParseLambdaOutput"
        Retry = [
          {
            ErrorEquals     = ["Lambda.ServiceException", "Lambda.TooManyRequestsException"]
            IntervalSeconds = 2
            MaxAttempts     = 3
            BackoffRate     = 2
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "ReportGenerationFailed"
          }
        ]
      }
      ParseLambdaOutput = {
        Type = "Pass"
        Parameters = {
          "reportData.$" = "States.StringToJson($.lambdaResult.Payload.body)"
        }
        ResultPath = "$.parsedData"
        Next       = "SendEmailViaSES"
      }
      SendEmailViaSES = {
        Type     = "Task"
        Resource = "arn:aws:states:::aws-sdk:ses:sendEmail"
        Parameters = {
          Destination = {
            ToAddresses = ["trainee.lorenzo.okpewo@sigmalabs.co.uk"]
          }
          Message = {
            Body = {
              Html = {
                Charset    = "UTF-8"
                "Data.$" = "$.parsedData.reportData.html_content"
              }
            }
            Subject = {
              Charset    = "UTF-8"
              "Data.$" = "States.Format('T3 Daily Report - {} - £{} Revenue', $.parsedData.reportData.date, $.parsedData.reportData.total_revenue)"
            }
          }
          Source = "sl-coaches@proton.me"
        }
        ResultPath = "$.emailResult"
        End        = true
        Retry = [
          {
            ErrorEquals     = ["Ses.ServiceException"]
            IntervalSeconds = 2
            MaxAttempts     = 3
            BackoffRate     = 2
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "EmailSendFailed"
          }
        ]
      }
      ReportGenerationFailed = {
        Type  = "Fail"
        Error = "ReportGenerationError"
        Cause = "Failed to generate the daily report"
      }
      EmailSendFailed = {
        Type  = "Fail"
        Error = "EmailSendError"
        Cause = "Failed to send the email via SES"
      }
    }
  })

  tags = {
    Name    = "T3 Report Pipeline"
    Project = "T3 Data Migration"
  }
}

# ============================================================
# Lambda Permission - Allow Step Functions to Invoke Lambda
# ============================================================

resource "aws_lambda_permission" "allow_step_functions" {
  statement_id  = "AllowExecutionFromStepFunctions"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.report_generator.function_name
  principal     = "states.amazonaws.com"
  source_arn    = aws_sfn_state_machine.report_pipeline.arn
}

# ============================================================
# EventBridge Rule - Daily at 9:30am UTC
# ============================================================

resource "aws_cloudwatch_event_rule" "daily_report" {
  name                = "c20-lorenzo-daily-report"
  description         = "Trigger T3 report pipeline daily at 9:30am UTC"
  schedule_expression = "cron(30 9 * * ? *)"

  tags = {
    Name    = "T3 Daily Report Schedule"
    Project = "T3 Data Migration"
  }
}

# ============================================================
# EventBridge Target - Connect Rule to Step Functions
# ============================================================

resource "aws_cloudwatch_event_target" "step_functions" {
  rule      = aws_cloudwatch_event_rule.daily_report.name
  target_id = "TriggerReportPipeline"
  arn       = aws_sfn_state_machine.report_pipeline.arn
  role_arn  = aws_iam_role.eventbridge_execution.arn
}

# ============================================================
# IAM Role - EventBridge Execution Role
# ============================================================

resource "aws_iam_role" "eventbridge_execution" {
  name = "c20-lorenzo-eventbridge-sfn-role"

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

  tags = {
    Name    = "T3 EventBridge Step Functions Role"
    Project = "T3 Data Migration"
  }
}

# EventBridge policy - start Step Functions execution
resource "aws_iam_role_policy" "eventbridge_policy" {
  name = "eventbridge-start-execution-policy"
  role = aws_iam_role.eventbridge_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "states:StartExecution"
      Resource = aws_sfn_state_machine.report_pipeline.arn
    }]
  })
}

# ============================================================
# Outputs
# ============================================================

output "lambda_function_name" {
  value       = aws_lambda_function.report_generator.function_name
  description = "Name of the Lambda function"
}

output "lambda_function_arn" {
  value       = aws_lambda_function.report_generator.arn
  description = "ARN of the Lambda function"
}

output "step_functions_arn" {
  value       = aws_sfn_state_machine.report_pipeline.arn
  description = "ARN of the Step Functions state machine"
}

output "step_functions_name" {
  value       = aws_sfn_state_machine.report_pipeline.name
  description = "Name of the Step Functions state machine"
}

output "ecr_repository_url" {
  value       = aws_ecr_repository.report_lambda.repository_url
  description = "ECR repository URL for Lambda image"
}

output "eventbridge_rule_name" {
  value       = aws_cloudwatch_event_rule.daily_report.name
  description = "Name of the EventBridge rule"
}

output "schedule" {
  value       = aws_cloudwatch_event_rule.daily_report.schedule_expression
  description = "Schedule expression for the pipeline trigger (UTC)"
}
