from boto3.dynamodb.conditions import Key

from app.storage import get_table


class CommunicationRepository:
    def __init__(self, table=None):
        self.table = table or get_table()

    def list_queue(self, queue_name: str):
        response = self.table.query(
            IndexName="GSI2",
            KeyConditionExpression=Key("GSI2PK").eq(f"SUPPORT#{queue_name}"),
        )
        return response.get("Items", [])
