from boto3.dynamodb.conditions import Attr, Key

from app.storage import get_table


class CaseRepository:
    def __init__(self, table=None):
        self.table = table or get_table()

    def list_ops_cases(self, owner_id: str | None = None, tab: str = "mine"):
        partition = {
            "mine": f"OPS#OWNER#{owner_id}",
            "unassigned": "OPS#ALL#OPEN",
            "overdue": "OPS#ALL#OPEN",
            "all_open": "OPS#ALL#OPEN",
        }[tab]
        response = self.table.query(
            IndexName="GSI1",
            KeyConditionExpression=Key("GSI1PK").eq(partition),
        )
        return response.get("Items", [])

    def list_queue(self, index: str, partition: str):
        response = self.table.query(
            IndexName=index,
            KeyConditionExpression=Key(f"{index}PK").eq(partition),
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

    def get_user(self, user_id: str):
        response = self.table.get_item(Key={"PK": f"USER#{user_id}", "SK": "META"})
        return response.get("Item")

    def list_users(self, role: str | None = None):
        kwargs = {"FilterExpression": Attr("entity_type").eq("user")}
        if role:
            kwargs["FilterExpression"] = Attr("entity_type").eq("user") & Attr("role").eq(role)
        response = self.table.scan(**kwargs)
        return response.get("Items", [])

    def next_case_id(self):
        response = self.table.update_item(
            Key={"PK": "SYSTEM#CASE_COUNTER", "SK": "META"},
            UpdateExpression="SET next_case_number = next_case_number + :one",
            ExpressionAttributeValues={":one": 1},
            ReturnValues="UPDATED_OLD",
        )
        number = response["Attributes"]["next_case_number"]
        return f"EX-{number}"

    def put_item(self, item: dict):
        self.table.put_item(Item=item)

    def delete_item(self, pk: str, sk: str):
        self.table.delete_item(Key={"PK": pk, "SK": sk})

    def remove_case(self, case_id: str):
        for item in self.get_case(case_id):
            self.delete_item(item["PK"], item["SK"])

    def query_field_actions(self, user_id: str, day: str):
        response = self.table.query(
            IndexName="GSI3",
            KeyConditionExpression=Key("GSI3PK").eq(f"FIELD#{user_id}#{day}"),
        )
        return response.get("Items", [])

    def find_route_action(self, shipment_id: str, assignee_id: str, day: str):
        actions = self.query_field_actions(assignee_id, day)
        return next(
            (action for action in actions if action.get("shipment_id") == shipment_id
             and action.get("action_type") in {"Delivery", "Redelivery"}
             and action.get("status") not in {"done", "cancelled"}),
            None,
        )

    def lookup_shipments(self, shipment_id: str):
        return self.get_shipment(shipment_id)
