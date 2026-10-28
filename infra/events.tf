resource "aws_cloudwatch_event_bus" "warehouse" {
  name = "${var.project}-bus"
}

resource "aws_cloudwatch_event_rule" "low_stock" {
  name           = "${var.project}-lowstock"
  event_bus_name = aws_cloudwatch_event_bus.warehouse.name
  event_pattern = jsonencode({
    source        = ["warehouse.inventory"]
    "detail-type" = ["LowStock"]
  })
}

resource "aws_cloudwatch_event_target" "low_stock_email" {
  rule           = aws_cloudwatch_event_rule.low_stock.name
  event_bus_name = aws_cloudwatch_event_bus.warehouse.name
  target_id      = "alerts-topic"
  arn            = aws_sns_topic.alerts.arn

  input_transformer {
    input_paths = {
      sku       = "$.detail.sku"
      stock     = "$.detail.stock"
      threshold = "$.detail.threshold"
    }
    input_template = "\"Low stock: <sku> has <stock> units left (threshold <threshold>). Please restock.\""
  }
}

# Lets EventBridge (low stock) and CloudWatch alarms publish to the topic
resource "aws_sns_topic_policy" "alerts" {
  arn = aws_sns_topic.alerts.arn
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowLowStockRule"
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "sns:Publish"
        Resource  = aws_sns_topic.alerts.arn
        Condition = { ArnEquals = { "aws:SourceArn" = aws_cloudwatch_event_rule.low_stock.arn } }
      },
      {
        Sid       = "AllowProjectAlarms"
        Effect    = "Allow"
        Principal = { Service = "cloudwatch.amazonaws.com" }
        Action    = "sns:Publish"
        Resource  = aws_sns_topic.alerts.arn
        Condition = {
          ArnLike = {
            "aws:SourceArn" = "arn:aws:cloudwatch:${var.region}:${data.aws_caller_identity.current.account_id}:alarm:${var.project}-*"
          }
        }
      }
    ]
  })
}
