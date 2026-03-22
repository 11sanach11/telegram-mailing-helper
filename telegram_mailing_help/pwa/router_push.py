from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict

from telegram_mailing_help.db.dao import User, PushSubscription
from telegram_mailing_help.pwa.deps import get_current_pwa_user

router = APIRouter()


def _dao():
    from telegram_mailing_help.pwa import deps
    return deps._dao


class PushSubscribeRequest(BaseModel):
    endpoint: str
    keys: Dict[str, str]  # {"p256dh": "...", "auth": "..."}


class PushUnsubscribeRequest(BaseModel):
    endpoint: str


@router.get("/vapid-public-key")
def vapid_public_key():
    pub = _dao().getValueFromStorage("vapid_public_key")
    return {"publicKey": pub or ""}


@router.post("/subscribe")
def subscribe(
    body: PushSubscribeRequest,
    current_user: User = Depends(get_current_pwa_user),
):
    dao = _dao()
    # Upsert: remove existing subscription with same endpoint, then insert fresh
    dao.deletePushSubscriptionByEndpoint(body.endpoint)
    sub = PushSubscription(
        id=None,
        users_id=current_user.id,
        endpoint=body.endpoint,
        p256dh=body.keys.get("p256dh", ""),
        auth=body.keys.get("auth", ""),
        created=datetime.now().isoformat(),
    )
    dao.savePushSubscription(sub)
    return {"success": True}


@router.delete("/unsubscribe")
def unsubscribe(
    body: PushUnsubscribeRequest,
    current_user: User = Depends(get_current_pwa_user),
):
    _dao().deletePushSubscriptionByEndpoint(body.endpoint)
    return {"success": True}
