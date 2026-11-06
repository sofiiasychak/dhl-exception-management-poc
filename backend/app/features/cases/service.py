from app.features.cases.repository import CaseRepository
from app.security import AuthenticatedUser


class CaseService:
    def __init__(self, repository: CaseRepository | None = None):
        self.repository = repository or CaseRepository()

    def list_cases(self, user: AuthenticatedUser):
        return self.repository.list_ops_cases(owner_id=user.user_id)

    def case_detail(self, case_id: str):
        items = self.repository.get_case(case_id)
        case = next((item for item in items if item.get("SK") == "META"), None)
        if case is None:
            return None
        case["timeline"] = [item for item in items if item.get("entity_type") == "timeline"]
        case["actions"] = [item for item in items if item.get("entity_type") == "action"]
        case["messages"] = [item for item in items if item.get("entity_type") == "message"]
        return case
