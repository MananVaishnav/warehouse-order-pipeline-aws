data "aws_caller_identity" "current" {}

data "archive_file" "worker" {
  type        = "zip"
  source_dir  = "${path.module}/../worker"
  output_path = "${path.module}/build/worker.zip"
}

resource "aws_iam_role" "worker" {
  name = "${var.project}-worker-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "worker" {
  name = "${var.project}-worker-policy"
  role = aws_iam_role.worker.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadAndUpdateStockAndOrders"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:ConditionCheckItem"]
        Resource = [aws_dynamodb_table.inventory.arn, aws_dynamodb_table.orders.arn]
      },
      {
        Sid      = "ConsumeOrderQueue"
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:ChangeMessageVisibility"]
        Resource = aws_sqs_queue.orders.arn
      },
      {
        Sid      = "SendLowStockEvents"
        Effect   = "Allow"
        Action   = "events:PutEvents"
        Resource = aws_cloudwatch_event_bus.warehouse.arn
      },
      {
        Sid      = "WriteLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.worker.arn}:*"
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/aws/lambda/${var.project}-worker"
  retention_in_days = 7
}

resource "aws_lambda_function" "worker" {
  function_name    = "${var.project}-worker"
  role             = aws_iam_role.worker.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.worker.output_path
  source_code_hash = data.archive_file.worker.output_base64sha256
  timeout          = 10
  memory_size      = 256

  environment {
    variables = {
      INVENTORY_TABLE = aws_dynamodb_table.inventory.name
      ORDERS_TABLE    = aws_dynamodb_table.orders.name
      EVENT_BUS       = aws_cloudwatch_event_bus.warehouse.name
    }
  }

  depends_on = [aws_cloudwatch_log_group.worker, aws_iam_role_policy.worker]
}

resource "aws_lambda_event_source_mapping" "orders" {
  event_source_arn                   = aws_sqs_queue.orders.arn
  function_name                      = aws_lambda_function.worker.arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 1
  function_response_types            = ["ReportBatchItemFailures"]
}
