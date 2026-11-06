from datetime import date

from app.features.field.repository import FieldRepository
from app.security import AuthenticatedUser


class FieldService:
    def __init__(self, repository: FieldRepository | None = None):
        self.repository = repository or FieldRepository()

    def list_actions(self, user: AuthenticatedUser, day: date):
        return self.repository.list_actions(user.user_id, day.isoformat())
