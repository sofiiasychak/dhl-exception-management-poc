from boto3.dynamodb.conditions import Key

from app.storage import get_table


class FieldRepository:
    def __init__(self, table=None):
        self.table = table or get_table()

    def list_actions(self, user_id: str, day: str):
        response = self.table.query(
            IndexName="GSI3",
            KeyConditionExpression=Key("GSI3PK").eq(f"FIELD#{user_id}#{day}"),
        )
        return response.get("Items", [])
