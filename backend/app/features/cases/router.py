from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.rules import Role
from app.features.cases.service import CaseService
from app.security import AuthenticatedUser, roles_required


router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("")
def list_cases(
    user: Annotated[AuthenticatedUser, Depends(roles_required(Role.OPS))],
):
    return CaseService().list_cases(user)


@router.get("/{case_id}")
def get_case(
    case_id: str,
    _user: Annotated[AuthenticatedUser, Depends(roles_required(Role.OPS, Role.SUPPORT))],
):
    case = CaseService().case_detail(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return case
