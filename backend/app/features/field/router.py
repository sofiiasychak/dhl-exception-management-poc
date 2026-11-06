from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.rules import Role, RuleViolation
from app.features.cases.service import CaseService
from app.photo_storage import MAX_PHOTO_BYTES, save_photo
from app.security import AuthenticatedUser, roles_required


router = APIRouter(prefix="/api/field", tags=["field"])


class UndoReport(BaseModel):
    report_id: str


@router.get("/shipments/{shipment_id}")
def get_shipment(
    shipment_id: str,
    _user: Annotated[
        AuthenticatedUser,
        Depends(roles_required(Role.COURIER, Role.DEPOT)),
    ],
):
    shipment = CaseService().lookup_shipment(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found.")
    return shipment


@router.get("/actions")
def list_actions(
    user: Annotated[
        AuthenticatedUser,
        Depends(roles_required(Role.COURIER, Role.DEPOT)),
    ],
    day: date | None = None,
):
    return CaseService().list_field_actions(user, day or date.today())


@router.post("/actions/{action_id}/complete")
def complete_action(
    action_id: str,
    user: Annotated[
        AuthenticatedUser,
        Depends(roles_required(Role.COURIER, Role.DEPOT)),
    ],
):
    try:
        return CaseService().complete_field_action(action_id, user)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error).strip("'")) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


@router.post("/reports/failed-delivery")
async def failed_delivery(
    user: Annotated[AuthenticatedUser, Depends(roles_required(Role.COURIER))],
    shipment_id: Annotated[str, Form()],
    reason: Annotated[str, Form()],
    taps_count: Annotated[int, Form()],
    duration_sec: Annotated[int, Form()],
    note: Annotated[str | None, Form()] = None,
    photo: Annotated[UploadFile | None, File()] = None,
):
    photo_keys = []
    if photo:
        try:
            photo_keys.append(save_photo(
                photo.filename or "evidence",
                photo.content_type or "",
                await photo.read(MAX_PHOTO_BYTES + 1),
            ))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        return CaseService().record_delivery_report(
            shipment_id=shipment_id,
            reason=reason,
            note=note,
            photo_keys=photo_keys,
            taps_count=taps_count,
            duration_sec=duration_sec,
            user=user,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error).strip("'")) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuleViolation as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/reports/{case_id}/undo")
def undo_report(
    case_id: str,
    payload: UndoReport,
    user: Annotated[AuthenticatedUser, Depends(roles_required(Role.COURIER))],
):
    try:
        return CaseService().undo_report(case_id, payload.report_id, user)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error).strip("'")) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuleViolation as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/reports/damage")
async def damage_report(
    user: Annotated[AuthenticatedUser, Depends(roles_required(Role.DEPOT))],
    shipment_id: Annotated[str, Form()],
    damage_types: Annotated[list[str], Form()],
    contents_checked: Annotated[bool, Form()],
    photos: Annotated[list[UploadFile], File()],
    note: Annotated[str | None, Form()] = None,
):
    photo_keys = []
    try:
        for photo in photos:
            photo_keys.append(save_photo(
                photo.filename or "evidence",
                photo.content_type or "",
                await photo.read(MAX_PHOTO_BYTES + 1),
            ))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        return CaseService().report_damage(
            shipment_id=shipment_id,
            damage_types=damage_types,
            contents_checked=contents_checked,
            note=note,
            photo_keys=photo_keys,
            user=user,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error).strip("'")) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuleViolation as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
