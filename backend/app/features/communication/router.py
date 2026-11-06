from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.rules import Role, RuleViolation
from app.features.cases.service import CaseService
from app.features.communication.service import CommunicationService
from app.features.webhooks.service import WebhookService
from app.security import AuthenticatedUser, roles_required


router = APIRouter(prefix="/api/communication", tags=["communication"])


class MessageRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=100)
    channel: str = Field(min_length=1, max_length=60)
    body: str = Field(min_length=1, max_length=5000)


class SimulatorChoice(BaseModel):
    case_id: str
    option_type: str
    slot: str | None = None


@router.get("/queues/{queue_name}")
def list_queue(
    queue_name: str,
    user: Annotated[AuthenticatedUser, Depends(roles_required(Role.SUPPORT))],
):
    try:
        items = CommunicationService().list_queue(queue_name)
        return [CaseService().case_detail(item["case_id"], user) for item in items]
    except RuleViolation as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/shipments/{shipment_id}")
def lookup_shipment(
    shipment_id: str,
    _user: Annotated[AuthenticatedUser, Depends(roles_required(Role.SUPPORT))],
):
    shipment = CaseService().lookup_shipment(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found.")
    return shipment


@router.post("/cases/{case_id}/messages")
def send_message(
    case_id: str,
    payload: MessageRequest,
    user: Annotated[AuthenticatedUser, Depends(roles_required(Role.SUPPORT))],
):
    try:
        return CaseService().send_message(
            case_id, payload.template_id, payload.channel, payload.body, user
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Case not found.") from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuleViolation as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/simulator/waiting")
def simulator_waiting(
    user: Annotated[AuthenticatedUser, Depends(roles_required(Role.SUPPORT))],
):
    return CaseService().support_queue(user, "waiting_for_customer")


@router.post("/simulator/choice")
def simulator_choice(
    payload: SimulatorChoice,
    _user: Annotated[AuthenticatedUser, Depends(roles_required(Role.SUPPORT))],
):
    if payload.option_type not in {"redelivery", "pickup_point"}:
        raise HTTPException(status_code=422, detail="Unsupported resolution option.")
    if payload.option_type == "redelivery" and not payload.slot:
        raise HTTPException(status_code=422, detail="Select a redelivery slot.")
    try:
        return WebhookService().record_choice(
            payload.case_id, payload.option_type, payload.slot
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Case not found.") from error
