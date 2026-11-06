from boto3.dynamodb.conditions import Key

from app.storage import get_table


class CaseRepository:
    def __init__(self, table=None):
        self.table = table or get_table()

    def list_ops_cases(self, owner_id: str | None = None):
        partition = f"OPS#OWNER#{owner_id}" if owner_id else "OPS#ALL#OPEN"
        response = self.table.query(
            IndexName="GSI1",
            KeyConditionExpression=Key("GSI1PK").eq(partition),
        )
        return response.get("Items", [])

    def get_case(self, case_id: str):
        response = self.table.query(
            KeyConditionExpression=Key("PK").eq(f"CASE#{case_id}"),
        )
        return response.get("Items", [])

    def find_open_case(self, shipment_id: str, exception_type: str):
        response = self.table.query(
            IndexName="GSI3",
            KeyConditionExpression=(
                Key("GSI3PK").eq(f"SHIPMENT#{shipment_id}")
                & Key("GSI3SK").begins_with(f"CASE#{exception_type}#OPEN#")
            ),
            Limit=1,
        )
        return response.get("Items", [])

    def get_shipment(self, shipment_id: str):
        response = self.table.get_item(
            Key={"PK": f"SHIPMENT#{shipment_id}", "SK": "META"}
        )
        return response.get("Item")
