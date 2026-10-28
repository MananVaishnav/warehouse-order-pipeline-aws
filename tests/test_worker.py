import json


def put_stock(ddb, sku, stock, threshold=15):
    ddb.put_item(TableName="warehouse-inventory", Item={
        "sku": {"S": sku}, "stock": {"N": str(stock)}, "threshold": {"N": str(threshold)}})


def put_order(ddb, order_id, sku, qty):
    ddb.put_item(TableName="warehouse-orders", Item={
        "order_id": {"S": order_id}, "sku": {"S": sku},
        "qty": {"N": str(qty)}, "status": {"S": "PENDING"}})


def sqs_event(*messages):
    return {"Records": [{"messageId": f"m{i}", "body": json.dumps(m)} for i, m in enumerate(messages)]}


def stock_of(ddb, sku):
    return int(ddb.get_item(TableName="warehouse-inventory", Key={"sku": {"S": sku}})["Item"]["stock"]["N"])


def status_of(ddb, order_id):
    return ddb.get_item(TableName="warehouse-orders", Key={"order_id": {"S": order_id}})["Item"]["status"]["S"]


def test_order_is_fulfilled_and_stock_goes_down(aws):
    ddb, worker = aws
    put_stock(ddb, "SKU-1", 10)
    put_order(ddb, "o1", "SKU-1", 3)

    result = worker.handler(sqs_event({"order_id": "o1", "sku": "SKU-1", "qty": 3}), None)

    assert result == {"batchItemFailures": []}
    assert stock_of(ddb, "SKU-1") == 7
    assert status_of(ddb, "o1") == "FULFILLED"


def test_order_rejected_when_not_enough_stock(aws):
    ddb, worker = aws
    put_stock(ddb, "SKU-1", 2)
    put_order(ddb, "o1", "SKU-1", 5)

    worker.handler(sqs_event({"order_id": "o1", "sku": "SKU-1", "qty": 5}), None)

    assert stock_of(ddb, "SKU-1") == 2
    assert status_of(ddb, "o1") == "REJECTED_OUT_OF_STOCK"


def test_same_message_twice_takes_stock_only_once(aws):
    ddb, worker = aws
    put_stock(ddb, "SKU-1", 10)
    put_order(ddb, "o1", "SKU-1", 3)
    msg = {"order_id": "o1", "sku": "SKU-1", "qty": 3}

    worker.handler(sqs_event(msg), None)
    worker.handler(sqs_event(msg), None)

    assert stock_of(ddb, "SKU-1") == 7


def test_bad_message_is_reported_as_failure(aws):
    _, worker = aws
    result = worker.handler(sqs_event({"bad": True}), None)
    assert result == {"batchItemFailures": [{"itemIdentifier": "m0"}]}
