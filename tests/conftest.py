import importlib
import os
import sys

import boto3
import pytest
from moto import mock_aws

os.environ.update({
    "AWS_DEFAULT_REGION": "ap-south-1",
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "INVENTORY_TABLE": "warehouse-inventory",
    "ORDERS_TABLE": "warehouse-orders",
    "EVENT_BUS": "warehouse-bus",
})
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "worker"))


@pytest.fixture
def aws():
    with mock_aws():
        ddb = boto3.client("dynamodb")
        for name, key in [("warehouse-inventory", "sku"), ("warehouse-orders", "order_id")]:
            ddb.create_table(
                TableName=name,
                KeySchema=[{"AttributeName": key, "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": key, "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
        boto3.client("events").create_event_bus(Name="warehouse-bus")

        import handler
        importlib.reload(handler)  # create the boto3 clients inside the mock
        yield ddb, handler
