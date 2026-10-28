import random

import boto3

TABLE = "warehouse-inventory"
REGION = "ap-south-1"

table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE)

with table.batch_writer() as batch:
    for i in range(1, 51):
        batch.put_item(Item={
            "sku": f"SKU-{i:04d}",
            "stock": random.randint(20, 200),
            "threshold": 15,
        })

print("Seeded 50 SKUs")
