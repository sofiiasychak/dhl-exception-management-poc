from app.features.cases.service import CaseService


class WebhookService:
    def __init__(self, case_service=None):
        self.case_service = case_service or CaseService()

    def record_choice(self, case_id: str, option_type: str, slot: str | None):
        return self.case_service.record_choice(case_id, option_type, slot)
