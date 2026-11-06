from app.features.cases.repository import CaseRepository


class CommunicationRepository:
    def __init__(self, cases: CaseRepository | None = None):
        self.cases = cases or CaseRepository()

    def list_queue(self, queue_name: str):
        return self.cases.list_queue("GSI2", f"SUPPORT#{queue_name}")
