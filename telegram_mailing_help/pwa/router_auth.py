import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from telegram_mailing_help.db.dao import User, UserState
from telegram_mailing_help.pwa.auth import hash_password, verify_password, create_access_token
from telegram_mailing_help.pwa.deps import get_current_pwa_user, _dao as _module_dao

router = APIRouter()


def _dao():
    from telegram_mailing_help.pwa import deps
    return deps._dao


def _push_broadcaster():
    from telegram_mailing_help.pwa import server as pwa_server
    return pwa_server._push_broadcaster


def _jwt_secret():
    return _dao().getValueFromStorage("pwa_jwt_secret")


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest):
    dao = _dao()
    if not body.email or not body.password or not body.name:
        raise HTTPException(status_code=400, detail="name, email and password are required")
    if dao.getUserByEmail(body.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        id=None,
        telegram_id=None,
        name=body.name,
        state=UserState.NEW.value,
        created=datetime.now().isoformat(),
        email=body.email,
        password_hash=hash_password(body.password),
        pwa_last_login=datetime.now().isoformat(),
    )
    dao.saveUser(user)
    # Notify admin via push
    broadcaster = _push_broadcaster()
    if broadcaster:
        broadcaster.notify_new_user(user)
    token = create_access_token(user.id, _jwt_secret())
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    dao = _dao()
    user = dao.getUserByEmail(body.email)
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.state == UserState.BLOCKED.value:
        raise HTTPException(status_code=403, detail="Account blocked")
    # Update last login
    user.pwa_last_login = datetime.now().isoformat()
    dao.saveUser(user)
    token = create_access_token(user.id, _jwt_secret())
    return TokenResponse(access_token=token)


@router.get("/me")
def me(current_user: User = Depends(get_current_pwa_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "state": current_user.state,
        "has_telegram": current_user.telegram_id is not None,
        "created": current_user.created,
    }


@router.post("/telegram-link/generate")
def generate_link_token(current_user: User = Depends(get_current_pwa_user)):
    dao = _dao()
    token = secrets.token_hex(3).upper()  # 6-char hex string
    dao.createTelegramLinkToken(current_user.id, token)
    return {
        "token": token,
        "instruction": f"Отправьте боту команду: /link {token}"
    }
