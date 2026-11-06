from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.rules import Role
from app.features.communication.service import CommunicationService
from app.security import AuthenticatedUser, roles_required


router = APIRouter(prefix="/api/communication", tags=["communication"])


@router.get("/queues/{queue_name}")
def list_queue(
    queue_name: str,
    _user: Annotated[AuthenticatedUser, Depends(roles_required(Role.SUPPORT))],
):
    try:
        return CommunicationService().list_queue(queue_name)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
