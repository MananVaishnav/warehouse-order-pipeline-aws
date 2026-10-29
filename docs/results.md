# Results

Everything on this page was checked by me on the live stack in AWS `ap-south-1` (Mumbai). Screenshots are in [`screenshots/`](screenshots/).

## Test setup

| Part | Setting |
| --- | --- |
| Region | ap-south-1, 2 Availability Zones |
| API | FastAPI (Python 3.12) on ECS Fargate, 2 tasks, 0.25 vCPU / 0.5 GB each, behind an Application Load Balancer |
| Queue | SQS, visibility timeout 60 s, `maxReceiveCount` 3, then a dead-letter queue |
| Worker | Python 3.12 Lambda, 256 MB, batch size 10, batch window 1 s, partial batch failures on |
| Database | DynamoDB on-demand, 2 tables (inventory, orders), point-in-time recovery on |
| Alerts | EventBridge (low stock) and 6 CloudWatch alarms, sent to email through SNS |

## 1. Functional checks

| Check | How | Result |
| --- | --- | --- |
| Worker unit tests (AWS mocked with moto) | `pytest -q`, locally and in every pipeline run | 4 / 4 pass |
| Order goes from `PENDING` to `FULFILLED` | POST an order, then GET it | ✅ Passed, 2026-10-28 |
| Not enough stock: order rejected, stock unchanged | Unit test `test_order_rejected_when_not_enough_stock` | ✅ Passed |
| The same message twice takes stock only once | Unit test `test_same_message_twice_takes_stock_only_once` | ✅ Passed |
| A bad message fails only itself, not the batch | Unit test `test_bad_message_is_reported_as_failure` | ✅ Passed |
| Low stock sends an email | Ordered until stock went under the threshold | ✅ Passed, 2026-10-28: SKU-0002 at stock 14 (threshold 15), email received |
| API through the load balancer | `/health` returns 200, 2 healthy targets in 2 AZs, order becomes `FULFILLED` | ✅ Passed, 2026-10-28 |

## 2. Poison message, dead-letter queue and alarm

**What I did:** sent a message that isn't valid JSON to the orders queue. The worker reported it as a failed item on each try. After 3 tries SQS moved it to the dead-letter queue, and the `warehouse-dlq-not-empty` alarm emailed me.

```bash
Q=$(terraform -chdir=infra output -raw orders_queue_url)
aws sqs send-message --queue-url "$Q" --message-body 'this-is-not-json'
```

| Date | DLQ data point | Alarm state ALARM | Email |
| --- | --- | --- | --- |
| 2026-10-28 | 15:28 UTC | 15:30:45 UTC | Received |

Screenshots: [`cw-alarms.png`](screenshots/cw-alarms.png), [`dlq-email.jpeg`](screenshots/dlq-email.jpeg)

## 3. CI/CD pipeline

| Date | Run | Test job | Deploy job | Total | Result |
| --- | --- | --- | --- | --- | --- |
| 2026-10-29 | `ci-cd` #2 (commit `d2ebe31`) | 33 s | 3 min 53 s | 3 min 58 s | ✅ Success: image pushed to ECR with the commit SHA tag, ECS rolled to a new task definition, `/health` smoke test passed |

Screenshots: [`github-actions1.png`](screenshots/github-actions1.png), [`github-actions2.png`](screenshots/github-actions2.png)

## 4. Planned measurements

These tests aren't done yet. I'll add their results here when they are, as the median of 3 runs with the date and settings:

- **Load test (Locust):** orders per minute, p50 and p99 API latency, error rate, and a check that no orders were lost
- **Order placed to `FULFILLED`:** end-to-end time
- **API task killed:** time until 2 healthy tasks again, and failed requests during that time
- **Bad deploy:** time for the ECS circuit breaker to roll back, and failed requests during the deploy
