from datetime import datetime, timezone
from uuid import uuid4

from app.storage import get_table


class WebhookRepository:
    def __init__(self, table=None):
        self.table = table or get_table()

    def record_choice(self, case_id: str, option_type: str, slot: str | None):
        item = {
            "PK": f"CASE#{case_id}",
            "SK": f"TL#{datetime.now(timezone.utc).isoformat()}#{uuid4().hex}",
            "entity_type": "timeline",
            "event": "resolution_option_recorded",
            "option_type": option_type,
            "slot": slot,
            "actor": "system",
        }
        self.table.put_item(Item=item)
        return item
