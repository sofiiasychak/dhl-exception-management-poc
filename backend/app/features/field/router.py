from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.rules import Role
from app.features.field.service import FieldService
from app.security import AuthenticatedUser, roles_required


router = APIRouter(prefix="/api/field", tags=["field"])


@router.get("/actions")
def list_actions(
    user: Annotated[
        AuthenticatedUser,
        Depends(roles_required(Role.COURIER, Role.DEPOT)),
    ],
    day: Annotated[date, Query()] = date.today(),
):
    return FieldService().list_actions(user, day)
