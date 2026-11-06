from app.features.webhooks.repository import WebhookRepository


class WebhookService:
    def __init__(self, repository: WebhookRepository | None = None):
        self.repository = repository or WebhookRepository()

    def record_choice(self, case_id: str, option_type: str, slot: str | None):
        return self.repository.record_choice(case_id, option_type, slot)
