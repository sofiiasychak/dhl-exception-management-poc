import hmac
import os
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.features.webhooks.service import WebhookService


router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class ResolutionChoice(BaseModel):
    case_id: str
    option_type: str
    slot: str | None = None


@router.post("/odd")
def resolution_choice(
    payload: ResolutionChoice,
    x_webhook_secret: Annotated[str | None, Header()] = None,
):
    expected = os.getenv("WEBHOOK_SHARED_SECRET", "")
    if not expected or not x_webhook_secret or not hmac.compare_digest(x_webhook_secret, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook secret.")
    return WebhookService().record_choice(
        payload.case_id, payload.option_type, payload.slot
    )
