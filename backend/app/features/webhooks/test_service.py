from app.features.webhooks.service import WebhookService


class FakeCaseService:
    def record_choice(self, case_id, option_type, slot):
        return {"case_id": case_id, "option_type": option_type, "slot": slot}


def test_webhook_records_customer_choice():
    result = WebhookService(
        case_service=FakeCaseService()
    ).record_choice(
        "EX-1", "redelivery", "2026-11-10T09:00"
    )
    assert result["option_type"] == "redelivery"
