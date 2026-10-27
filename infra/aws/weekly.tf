variable "weekly_training_end_date" {
  type        = string
  description = "Existing EC2 stop deadline, UTC. Weekly training never extends it."
}

resource "aws_iam_role" "collector_ssm" {
  name = "capstone-traffic-ec2-ssm"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole"
  }] })
}

resource "aws_iam_role_policy_attachment" "collector_ssm" {
  role       = aws_iam_role.collector_ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "collector_ssm" {
  name = "capstone-traffic-ec2-ssm"
  role = aws_iam_role.collector_ssm.name
}

resource "aws_ssm_document" "weekly_training" {
  name          = "capstone-traffic-weekly-train"
  document_type = "Command"
  content = jsonencode({
    schemaVersion = "2.2", description = "Run the fixed bounded weekly traffic training job",
    mainSteps = [{ action = "aws:runShellScript", name = "train", inputs = {
      timeoutSeconds = "1200",
      runCommand     = ["/usr/bin/python3 /opt/capstone-traffic/fl-real/infra/aws/weekly/run_train.py"]
    } }]
  })
}

resource "aws_cloudwatch_log_group" "weekly_training" {
  name              = "/aws/lambda/capstone-traffic-weekly-train"
  retention_in_days = 14
}

resource "aws_iam_role" "weekly_lambda" {
  name = "capstone-traffic-weekly-lambda"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole"
  }] })
}

resource "aws_iam_role_policy" "weekly_lambda" {
  role = aws_iam_role.weekly_lambda.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["ssm:SendCommand"], Resource = [
    aws_instance.collector.arn, aws_ssm_document.weekly_training.arn] },
    { Effect = "Allow", Action = ["ec2:DescribeInstances"], Resource = "*" },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"],
    Resource = "${aws_cloudwatch_log_group.weekly_training.arn}:*" }
  ] })
}

resource "aws_lambda_function" "weekly_training" {
  function_name                  = "capstone-traffic-weekly-train"
  role                           = aws_iam_role.weekly_lambda.arn
  handler                        = "handler.handler"
  runtime                        = "python3.12"
  architectures                  = ["x86_64"]
  filename                       = "${path.module}/.state/weekly-trigger.zip"
  source_code_hash               = filebase64sha256("${path.module}/.state/weekly-trigger.zip")
  timeout                        = 30
  memory_size                    = 128
  reserved_concurrent_executions = 1
  environment {
    variables = {
      INSTANCE_ID  = aws_instance.collector.id
      SSM_DOCUMENT = aws_ssm_document.weekly_training.name
      END_DATE     = var.weekly_training_end_date
    }
  }
  depends_on = [aws_iam_role_policy.weekly_lambda]
}

resource "aws_iam_role" "weekly_scheduler" {
  name = "capstone-traffic-weekly-scheduler"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "scheduler.amazonaws.com" }, Action = "sts:AssumeRole",
    Condition = { StringEquals = { "aws:SourceAccount" = var.account_id },
    ArnEquals = { "aws:SourceArn" = "arn:aws:scheduler:${var.region}:${var.account_id}:schedule-group/default" } }
  }] })
}

resource "aws_iam_role_policy" "weekly_scheduler" {
  role = aws_iam_role.weekly_scheduler.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = ["lambda:InvokeFunction"], Resource = aws_lambda_function.weekly_training.arn
  }] })
}

resource "aws_scheduler_schedule" "weekly_training" {
  name                         = "capstone-traffic-weekly-train"
  description                  = "Monday 02:00 Vietnam time; bounded training on existing EC2"
  schedule_expression          = "cron(0 2 ? * MON *)"
  schedule_expression_timezone = "Asia/Ho_Chi_Minh"
  end_date                     = var.weekly_training_end_date
  state                        = "ENABLED"
  flexible_time_window { mode = "OFF" }
  target {
    arn      = aws_lambda_function.weekly_training.arn
    role_arn = aws_iam_role.weekly_scheduler.arn
    input    = jsonencode({ source = "weekly-scheduler" })
    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 1
    }
  }
  depends_on = [aws_iam_role_policy.weekly_scheduler]
}

output "weekly_lambda_name" { value = aws_lambda_function.weekly_training.function_name }
output "weekly_schedule_name" { value = aws_scheduler_schedule.weekly_training.name }
