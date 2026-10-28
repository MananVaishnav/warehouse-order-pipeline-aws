output "inventory_table" { value = aws_dynamodb_table.inventory.name }
output "orders_table" { value = aws_dynamodb_table.orders.name }
output "orders_queue_url" { value = aws_sqs_queue.orders.url }
output "orders_dlq_url" { value = aws_sqs_queue.orders_dlq.url }
output "alerts_topic_arn" { value = aws_sns_topic.alerts.arn }
output "worker_function" { value = aws_lambda_function.worker.function_name }
output "event_bus" { value = aws_cloudwatch_event_bus.warehouse.name }
output "ecr_repository_url" { value = aws_ecr_repository.api.repository_url }
output "alb_dns_name" { value = aws_lb.api.dns_name }
output "target_group_arn" { value = aws_lb_target_group.api.arn }
output "ecs_cluster" { value = aws_ecs_cluster.main.name }
output "ecs_service" { value = aws_ecs_service.api.name }

