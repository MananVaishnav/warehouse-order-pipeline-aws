# Results

I measured every number on this page myself, on the stack in this repo, in AWS `ap-south-1` (Mumbai). Each timing is the **median of 3 runs** unless it says otherwise. Raw output from each run is in [`results/`](results/), and screenshots are in [`screenshots/`](screenshots/).

> Fill in every `___` after you run the test. If a number isn't measured yet, leave it as `___`. Never estimate.

## Test setup

| Part | Setting |
| --- | --- |
| Region | ap-south-1, 2 Availability Zones |
| API | FastAPI (Python 3.12) on ECS Fargate, 2 tasks, 0.25 vCPU / 0.5 GB each, behind an Application Load Balancer |
| Queue | SQS, visibility timeout 60 s, `maxReceiveCount` 3, then a dead-letter queue |
| Worker | Python 3.12 Lambda, 256 MB, batch size 10, batch window 1 s, partial batch failures on |
| Database | DynamoDB on-demand, 2 tables (inventory, orders), point-in-time recovery on |
| Alerts | EventBridge (low stock) and 6 CloudWatch alarms, sent to email through SNS |
| Load tool | Locust ___ (version), run from ___ (laptop / WSL, location) |

## Summary

| Test | Result | Runs | Date |
| --- | --- | --- | --- |
| Throughput through the ALB | ___ orders/min, ___ % errors | 3 | ___ |
| API latency at that load | p50 ___ ms, p99 ___ ms | 3 | ___ |
| Order placed to `FULFILLED` | p50 ___ s | 3 | ___ |
| One API task killed | healthy again in ___ s, ___ orders lost | 3 | ___ |
| Poison message | in DLQ after 3 tries in ___ min, alarm email ___ min later | 3 | ___ |
| Bad deploy | rolled back automatically in ___ min, ___ failed requests | 1 | ___ |
| Low-stock alert | event to email in ___ s | 3 | ___ |

## 1. Functional checks

| Check | How | Result |
| --- | --- | --- |
| Unit tests (worker logic, mocked AWS with moto) | `pytest -q` | ___ / 4 passed |
| Order goes from `PENDING` to `FULFILLED` | POST an order, then GET it | Passed on 2026-10-28 |
| Order for more than the stock is rejected | Order `qty` larger than the stock | ___ |
| The same message twice takes stock only once | Send the same order message twice | Covered by unit test |
| Low stock sends an email | Order until stock drops under 15 | Passed on 2026-10-28 (SKU-0002, stock 14) |
| API through the load balancer | `/health` returns 200, 2 healthy targets, order becomes `FULFILLED` | Passed on 2026-10-28 |
| Same `Idempotency-Key` twice creates one order | POST twice with the same header | ___ |

## 2. Load test

**Command** (from the repo root):

```bash
ALB=$(terraform -chdir=infra output -raw alb_dns_name)
locust -f tests/load/locustfile.py --headless -u 50 -r 10 -t 3m \
  --host "http://$ALB" \
  --csv docs/results/locust-run1 --html docs/results/locust-run1.html
```

| Run | Users | Duration | Requests/s | Orders/min | p50 (ms) | p99 (ms) | Errors % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 50 | 3 min | ___ | ___ | ___ | ___ | ___ |
| 2 | 50 | 3 min | ___ | ___ | ___ | ___ | ___ |
| 3 | 50 | 3 min | ___ | ___ | ___ | ___ | ___ |
| **Median** | | | ___ | ___ | ___ | ___ | ___ |

**After the test:**

- DLQ messages: ___ (should be 0)
- Orders still `PENDING` after 2 minutes: ___ (should be 0)
- Highest queue age on the dashboard: ___ s

## 3. API task failure and recovery

**What I did:** stopped one of the 2 API tasks while orders kept coming in, then timed how long until 2 healthy targets came back.

```bash
TG=$(terraform -chdir=infra output -raw target_group_arn)
TASK=$(aws ecs list-tasks --cluster warehouse-cluster --service-name warehouse-api \
  --query 'taskArns[0]' --output text)

date +%T
aws ecs stop-task --cluster warehouse-cluster --task "$TASK" --reason "recovery test"

# Run this in a second terminal and note the time it shows 2 x healthy
while true; do date +%T; aws elbv2 describe-target-health --target-group-arn "$TG" \
  --query 'TargetHealthDescriptions[].TargetHealth.State' --output text; sleep 5; done
```

| Run | Stopped at | 2 healthy again at | Recovery (s) | Failed requests during test | Orders lost |
| --- | --- | --- | --- | --- | --- |
| 1 | ___ | ___ | ___ | ___ | ___ |
| 2 | ___ | ___ | ___ | ___ | ___ |
| 3 | ___ | ___ | ___ | ___ | ___ |

## 4. Poison message, DLQ and alarm

**What I did:** sent a message that isn't valid JSON. The worker reports it as a failed item 3 times, SQS moves it to the DLQ, and the `warehouse-dlq-not-empty` alarm emails me.

```bash
Q=$(terraform -chdir=infra output -raw orders_queue_url)
DLQ=$(terraform -chdir=infra output -raw orders_dlq_url)
date +%T
aws sqs send-message --queue-url "$Q" --message-body 'this-is-not-json'
aws sqs get-queue-attributes --queue-url "$DLQ" --attribute-names ApproximateNumberOfMessages
aws sqs purge-queue --queue-url "$DLQ"     # afterwards, so the alarm goes back to OK
```

| Run | Sent at | In DLQ at | ALARM email at | OK email after purge at |
| --- | --- | --- | --- | --- |
| 1 | ___ | ___ | ___ | ___ |
| 2 | ___ | ___ | ___ | ___ |
| 3 | ___ | ___ | ___ | ___ |

**Other orders in the same batch:** ___ (expected: all `FULFILLED`, because of partial batch failures)

## 5. Bad deploy and automatic rollback

**What I did:** deployed a version whose `/health` check fails. The ECS deployment circuit breaker should stop the rollout and go back to the last working version, while the old tasks keep serving traffic.

| Started at | Circuit breaker triggered at | Back on old version at | Failed requests during deploy |
| --- | --- | --- | --- |
| ___ | ___ | ___ | ___ |

## 6. Alarms fired in tests

| Alarm | How I triggered it | ALARM email | OK email |
| --- | --- | --- | --- |
| `warehouse-dlq-not-empty` | Poison message (section 4) | ___ | ___ |
| `warehouse-queue-oldest-message` | Disabled the Lambda trigger for 4 min while sending orders | ___ | ___ |
| `warehouse-worker-errors` | ___ | ___ | ___ |
| `warehouse-api-5xx` | ___ | ___ | ___ |
| `warehouse-api-p99-latency` | ___ | ___ | ___ |
| `warehouse-unhealthy-targets` | Bad deploy (section 5) | ___ | ___ |

## What broke while building it, and how I fixed it

| Problem | Cause | Fix |
| --- | --- | --- |
| `terraform apply` failed creating the SQS trigger for the Lambda (`lambda:TagResource` AccessDenied) | Terraform `default_tags` tag the event source mapping when it's created, and my least-privilege IAM user had no permission to tag it | Allowed tag and read actions only on `event-source-mapping` ARNs, not on all of Lambda |
| `docker build` failed in WSL with "Network is unreachable" during `pip install` | The Docker build network couldn't reach the internet from WSL | Built with `--network=host` |
| The container started but `/health` hung | The WSL network interface has MTU 1400 while the Docker bridge uses 1500, so larger packets to AWS were dropped | Set `"mtu": 1400` in `/etc/docker/daemon.json`. Also added short boto3 timeouts so `/health` returns 503 fast instead of hanging |
| One push showed 3 entries in ECR | Docker adds an image index and a build record (provenance) by default | Built with `--platform linux/amd64 --provenance=false --sbom=false` and used versioned, immutable tags (`v1`, `v2`) instead of `latest` |
| Creating subnets, the route table and security groups failed (`UnauthorizedOperation`) | With tag-based IAM, `CreateSubnet` is checked against the new subnet (request tag) and also the existing VPC (resource tag). My policy only covered the first | Added a statement allowing these actions only inside VPCs tagged `project=warehouse`, instead of opening it to every VPC |
| Creating the load balancer failed (`ec2:GetSecurityGroupsForVpc`) | The ALB calls a read-only action that isn't part of `ec2:Describe*` | Added that one read action |

## Known limits

- **Order saved but the queue send fails.** The API writes the order, then sends it to SQS. If the send fails, the order stays `PENDING`. A fix would be a transactional outbox (DynamoDB Streams to SQS) or a job that re-queues old `PENDING` orders.
- **Public subnets, no NAT Gateway.** I did this to save cost. The tasks accept traffic only from the load balancer's security group, but private subnets with VPC endpoints would be the production setup.
- **HTTP only.** HTTPS needs a domain and an ACM certificate.
