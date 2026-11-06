from app.core.rules import RuleViolation
from app.features.communication.repository import CommunicationRepository


class CommunicationService:
    QUEUES = {"not_informed", "waiting_for_customer", "confirm_resolution"}

    def __init__(self, repository: CommunicationRepository | None = None):
        self.repository = repository or CommunicationRepository()

    def list_queue(self, queue_name: str):
        if queue_name not in self.QUEUES:
            raise RuleViolation("Unknown Support queue.")
        return self.repository.list_queue(queue_name)
