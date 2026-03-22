"""Shared FastAPI dependencies for the PWA routers."""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

from telegram_mailing_help.db.dao import UserState
from telegram_mailing_help.pwa.auth import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)

# Module-level references set by PwaServer.__init__
_dao = None
_prep = None
_appConfig = None


def get_dao():
    return _dao


def get_prep():
    return _prep


def get_appConfig():
    return _appConfig


def get_current_pwa_user(credentials=Depends(bearer_scheme)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    jwt_secret = _dao.getValueFromStorage("pwa_jwt_secret")
    user_id = decode_access_token(credentials.credentials, jwt_secret)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = _dao.getUserById(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if user.state == UserState.BLOCKED.value:
        raise HTTPException(status_code=403, detail="Account blocked")
    return user
