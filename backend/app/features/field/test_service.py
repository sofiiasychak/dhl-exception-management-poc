from datetime import date

from app.features.field.service import FieldService
from app.security import AuthenticatedUser
from app.core.rules import Role


class FakeFieldRepository:
    def list_actions(self, user_id, day):
        return [{"assignee_id": user_id, "date": day}]


def test_field_service_requests_only_the_authenticated_user():
    user = AuthenticatedUser("thomas-a", Role.COURIER)
    assert FieldService(FakeFieldRepository()).list_actions(
        user, date(2026, 11, 6)
    ) == [{"assignee_id": "thomas-a", "date": "2026-11-06"}]
