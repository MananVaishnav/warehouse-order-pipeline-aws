import json
import os

import boto3

ddb = boto3.client("dynamodb")
events = boto3.client("events")

INVENTORY_TABLE = os.environ["INVENTORY_TABLE"]
ORDERS_TABLE = os.environ["ORDERS_TABLE"]
EVENT_BUS = os.environ["EVENT_BUS"]


def handler(event, context):
    failures = []
    for record in event["Records"]:
        try:
            process(json.loads(record["body"]))
        except Exception as e:
            print(f"Failed message {record['messageId']}: {e}")
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}


def process(msg):
    order_id, sku, qty = msg["order_id"], msg["sku"], int(msg["qty"])

    # Take stock and mark the order FULFILLED in one transaction:
    # stock can never go below zero, and a retried message can't take stock twice.
    try:
        ddb.transact_write_items(TransactItems=[
            {"Update": {
                "TableName": INVENTORY_TABLE,
                "Key": {"sku": {"S": sku}},
                "UpdateExpression": "SET stock = stock - :q",
                "ConditionExpression": "stock >= :q",
                "ExpressionAttributeValues": {":q": {"N": str(qty)}},
            }},
            {"Update": {
                "TableName": ORDERS_TABLE,
                "Key": {"order_id": {"S": order_id}},
                "UpdateExpression": "SET #s = :fulfilled",
                "ConditionExpression": "#s = :pending",
                "ExpressionAttributeNames": {"#s": "status"},
                "ExpressionAttributeValues": {
                    ":fulfilled": {"S": "FULFILLED"},
                    ":pending": {"S": "PENDING"},
                },
            }},
        ])
    except ddb.exceptions.TransactionCanceledException as e:
        reasons = [r.get("Code") for r in e.response["CancellationReasons"]]
        if reasons[1] == "ConditionalCheckFailed":
            print(f"Order {order_id} already processed, skipping")
            return
        if reasons[0] == "ConditionalCheckFailed":
            reject(order_id)
            return
        raise

    check_low_stock(sku)


def reject(order_id):
    ddb.update_item(
        TableName=ORDERS_TABLE,
        Key={"order_id": {"S": order_id}},
        UpdateExpression="SET #s = :rejected",
        ConditionExpression="#s = :pending",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":rejected": {"S": "REJECTED_OUT_OF_STOCK"},
            ":pending": {"S": "PENDING"},
        },
    )
    print(f"Order {order_id} rejected: not enough stock")


def check_low_stock(sku):
    item = ddb.get_item(TableName=INVENTORY_TABLE, Key={"sku": {"S": sku}})["Item"]
    stock, threshold = int(item["stock"]["N"]), int(item["threshold"]["N"])
    if stock < threshold:
        events.put_events(Entries=[{
            "Source": "warehouse.inventory",
            "DetailType": "LowStock",
            "Detail": json.dumps({"sku": sku, "stock": stock, "threshold": threshold}),
            "EventBusName": EVENT_BUS,
        }])
