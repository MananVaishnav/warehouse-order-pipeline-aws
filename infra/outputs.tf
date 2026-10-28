output "inventory_table" { value = aws_dynamodb_table.inventory.name }
output "orders_table" { value = aws_dynamodb_table.orders.name }
output "orders_queue_url" { value = aws_sqs_queue.orders.url }
output "orders_dlq_url" { value = aws_sqs_queue.orders_dlq.url }
output "alerts_topic_arn" { value = aws_sns_topic.alerts.arn }
