import json
import os
import time
import uuid

import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

ORDERS_TABLE = os.environ["ORDERS_TABLE"]
QUEUE_URL = os.environ["QUEUE_URL"]

ddb = boto3.client("dynamodb")
sqs = boto3.client("sqs")

app = FastAPI(title="Warehouse Order API")


class OrderIn(BaseModel):
    sku: str = Field(pattern=r"^SKU-\d{4}$")
    qty: int = Field(ge=1, le=100)


@app.post("/orders", status_code=202)
def create_order(order: OrderIn, idempotency_key: str | None = Header(default=None, max_length=64)):
    # A retried request with the same Idempotency-Key returns the first order instead of creating a new one
    order_id = idempotency_key or str(uuid.uuid4())
    try:
        ddb.put_item(
            TableName=ORDERS_TABLE,
            Item={
                "order_id": {"S": order_id},
                "sku": {"S": order.sku},
                "qty": {"N": str(order.qty)},
                "status": {"S": "PENDING"},
                "created_at": {"N": str(int(time.time()))},
            },
            ConditionExpression="attribute_not_exists(order_id)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return get_order(order_id)
        raise

    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps({"order_id": order_id, "sku": order.sku, "qty": order.qty}),
    )
    return {"order_id": order_id, "status": "PENDING"}


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    item = ddb.get_item(TableName=ORDERS_TABLE, Key={"order_id": {"S": order_id}}).get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "order_id": order_id,
        "sku": item["sku"]["S"],
        "qty": int(item["qty"]["N"]),
        "status": item["status"]["S"],
    }


@app.get("/health")
def health():
    try:
        ddb.describe_table(TableName=ORDERS_TABLE)
    except Exception:
        raise HTTPException(status_code=503, detail="Cannot reach DynamoDB")
    return {"status": "ok"}
