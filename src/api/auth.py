import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.core.config import CLIENT_ID, CALLBACK_URL, JWT_REFRESH_SECRET
from src.core.database import get_db
from src.core.middleware import get_current_user
from src.models.password_reset import PasswordReset
from src.models.token import Token
from src.models.user import User
from src.schemas.auth import LoginRequest, RegisterRequest, UserResponse, ForgotPasswordRequest, ResetPasswordRequest
from src.services.auth import (
    create_token_pair,
    decode_token,
    get_yandex_user,
    hash_password,
    hash_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    password_hash, salt = hash_password(body.password)
    user = User(email=body.email, password_hash=password_hash, salt=salt)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email, User.deleted_at == None).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token, refresh_token = create_token_pair(user.id, db)
    response.set_cookie("access_token", access_token, httponly=True, samesite="lax")
    response.set_cookie("refresh_token", refresh_token, httponly=True, samesite="lax")
    return {"detail": "Logged in"}


@router.post("/refresh")
def refresh(response: Response, refresh_token: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    try:
        payload = decode_token(refresh_token, JWT_REFRESH_SECRET)
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token = db.query(Token).filter(
        Token.token_hash == hash_token(refresh_token),
        Token.is_revoked == False,
    ).first()
    if not token:
        raise HTTPException(status_code=401, detail="Token revoked")

    token.is_revoked = True
    db.commit()

    access_token, new_refresh_token = create_token_pair(user_id, db)
    response.set_cookie("access_token", access_token, httponly=True, samesite="lax")
    response.set_cookie("refresh_token", new_refresh_token, httponly=True, samesite="lax")
    return {"detail": "Tokens refreshed"}


@router.get("/whoami", response_model=UserResponse)
def whoami(db: Session = Depends(get_db), access_token: str | None = Cookie(default=None)):
    return get_current_user(access_token=access_token, db=db)


@router.post("/logout")
def logout(response: Response, access_token: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    if access_token:
        token = db.query(Token).filter(Token.token_hash == hash_token(access_token)).first()
        if token:
            token.is_revoked = True
            db.commit()
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"detail": "Logged out"}


@router.post("/logout-all")
def logout_all(response: Response, access_token: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    user = get_current_user(access_token=access_token, db=db)
    db.query(Token).filter(Token.user_id == user.id, Token.is_revoked == False).update({"is_revoked": True})
    db.commit()
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"detail": "All sessions terminated"}


@router.get("/oauth/yandex")
def yandex_login(response: Response):
    state = secrets.token_urlsafe(16)
    response.set_cookie("oauth_state", state, httponly=True, samesite="lax")
    url = (
        f"https://oauth.yandex.ru/authorize"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={CALLBACK_URL}"
        f"&state={state}"
    )
    return RedirectResponse(url)


@router.get("/oauth/yandex/callback")
async def yandex_callback(
    code: str,
    state: str,
    response: Response,
    db: Session = Depends(get_db),
    oauth_state: str | None = Cookie(default=None),
):
    if not oauth_state or oauth_state != state:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    yandex_data = await get_yandex_user(code)

    yandex_id = str(yandex_data.get("id"))
    email = yandex_data.get("default_email")
    first_name = yandex_data.get("first_name")
    last_name = yandex_data.get("last_name")

    user = db.query(User).filter(User.yandex_id == yandex_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(yandex_id=yandex_id, email=email, first_name=first_name, last_name=last_name)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.yandex_id = yandex_id
        db.commit()

    access_token, refresh_token = create_token_pair(user.id, db)
    response.set_cookie("access_token", access_token, httponly=True, samesite="none", secure=False)
    response.set_cookie("refresh_token", refresh_token, httponly=True, samesite="none", secure=False)
    response.delete_cookie("oauth_state")

    from src.schemas.auth import UserResponse
    return UserResponse.model_validate(user)


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email, User.deleted_at == None).first()
    if not user:
        return {"detail": "If email exists, reset link was sent"}

    token = secrets.token_urlsafe(32)
    reset = PasswordReset(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(reset)
    db.commit()

    return {"detail": "Reset token generated", "reset_token": token}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    reset = db.query(PasswordReset).filter(
        PasswordReset.token_hash == hash_token(body.token),
        PasswordReset.is_used == False,
        PasswordReset.expires_at > datetime.now(timezone.utc),
    ).first()

    if not reset:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == reset.user_id).first()
    password_hash, salt = hash_password(body.new_password)
    user.password_hash = password_hash
    user.salt = salt
    reset.is_used = True
    db.commit()

    return {"detail": "Password updated"}