from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.rules import Priority, Role, RuleViolation
from app.features.cases.service import CaseService
from app.security import AuthenticatedUser, roles_required


router = APIRouter(prefix="/api/cases", tags=["cases"])


class PriorityUpdate(BaseModel):
    priority: Priority
    reason: str = Field(min_length=1, max_length=500)


class OwnerUpdate(BaseModel):
    owner_id: str


class ActionAssignment(BaseModel):
    action_type: str = Field(min_length=1, max_length=80)
    assignee_id: str
    action_date: date | None = None


class ResolveRequest(BaseModel):
    outcome: str = Field(min_length=1, max_length=200)
    root_cause: str = Field(min_length=1, max_length=200)
    send_confirmation: bool = True


class ReopenRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class EscalationRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)


def _http_error(error: Exception):
    if isinstance(error, KeyError):
        raise HTTPException(status_code=404, detail=str(error).strip("'")) from error
    if isinstance(error, PermissionError):
        raise HTTPException(status_code=403, detail=str(error)) from error
    if isinstance(error, RuleViolation):
        raise HTTPException(status_code=422, detail=str(error)) from error
    raise error


@router.get("")
def list_cases(
    user: Annotated[AuthenticatedUser, Depends(roles_required(Role.OPS))],
    tab: Literal["mine", "unassigned", "overdue", "all_open"] = "mine",
    exception_type: str | None = None,
    priority: str | None = None,
    region: str | None = None,
    status: str | None = None,
):
    try:
        return CaseService().list_cases(
            user, tab=tab, exception_type=exception_type,
            priority=priority, region=region, status=status,
        )
    except RuleViolation as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/users")
def list_users(
    _user: Annotated[AuthenticatedUser, Depends(roles_required(Role.OPS))],
):
    return CaseService().repository.list_users()


@router.get("/{case_id}")
def get_case(
    case_id: str,
    user: Annotated[AuthenticatedUser, Depends(
        roles_required(Role.OPS, Role.SUPPORT, Role.COURIER, Role.DEPOT)
    )],
):
    try:
        case = CaseService().case_detail(case_id, user)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return case


@router.post("/{case_id}/priority")
def update_priority(
    case_id: str,
    payload: PriorityUpdate,
    user: Annotated[AuthenticatedUser, Depends(roles_required(Role.OPS))],
):
    try:
        return CaseService().update_priority(case_id, payload.priority, payload.reason, user)
    except (KeyError, PermissionError, RuleViolation) as error:
        _http_error(error)


@router.post("/{case_id}/owner")
def reassign_owner(
    case_id: str,
    payload: OwnerUpdate,
    user: Annotated[AuthenticatedUser, Depends(roles_required(Role.OPS))],
):
    try:
        return CaseService().reassign_owner(case_id, payload.owner_id, user)
    except (KeyError, PermissionError, RuleViolation) as error:
        _http_error(error)


@router.post("/{case_id}/actions")
def assign_action(
    case_id: str,
    payload: ActionAssignment,
    user: Annotated[AuthenticatedUser, Depends(roles_required(Role.OPS))],
):
    try:
        return CaseService().assign_action(
            case_id, payload.action_type, payload.assignee_id, user,
            date_value=payload.action_date.isoformat() if payload.action_date else None,
        )
    except (KeyError, PermissionError, RuleViolation) as error:
        _http_error(error)


@router.post("/{case_id}/resolve")
def resolve_case(
    case_id: str,
    payload: ResolveRequest,
    user: Annotated[AuthenticatedUser, Depends(roles_required(Role.OPS))],
):
    try:
        return CaseService().resolve_case(
            case_id, payload.outcome, payload.root_cause,
            payload.send_confirmation, user,
        )
    except (KeyError, PermissionError, RuleViolation) as error:
        _http_error(error)


@router.post("/{case_id}/reopen")
def reopen_case(
    case_id: str,
    payload: ReopenRequest,
    user: Annotated[AuthenticatedUser, Depends(roles_required(Role.OPS))],
):
    try:
        return CaseService().reopen_case(case_id, payload.reason, user)
    except (KeyError, PermissionError, RuleViolation) as error:
        _http_error(error)


@router.post("/{case_id}/escalate")
def escalate_case(
    case_id: str,
    payload: EscalationRequest,
    user: Annotated[AuthenticatedUser, Depends(
        roles_required(Role.SUPPORT, Role.COURIER, Role.DEPOT)
    )],
):
    try:
        return CaseService().escalate(case_id, payload.message, user)
    except (KeyError, PermissionError, RuleViolation) as error:
        _http_error(error)
