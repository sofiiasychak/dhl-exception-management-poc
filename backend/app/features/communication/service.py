from app.features.communication.repository import CommunicationRepository


class CommunicationService:
    def __init__(self, repository: CommunicationRepository | None = None):
        self.repository = repository or CommunicationRepository()

    def list_queue(self, queue_name: str):
        if queue_name not in {"not_informed", "waiting_for_customer", "confirm_resolution"}:
            raise ValueError("Unknown Support queue.")
        return self.repository.list_queue(queue_name)
