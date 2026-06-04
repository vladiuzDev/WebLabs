import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, Security, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.core.config import CLIENT_ID, CALLBACK_URL, JWT_REFRESH_SECRET
from src.core.database import get_db
from src.core.middleware import bearer_scheme, get_current_user
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

router = APIRouter(prefix="/auth", tags=["Auth"])

_401 = {
    "description": "Unauthorized",
    "content": {"application/json": {"example": {"detail": "Not authenticated"}}},
}
_400 = {
    "description": "Bad Request — validation or logic error",
    "content": {"application/json": {"example": {"detail": "Invalid or expired token"}}},
}
_409 = {
    "description": "Conflict — resource already exists",
    "content": {"application/json": {"example": {"detail": "Email already registered"}}},
}


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    summary="Register a new user",
    description="Creates a new account using email and password. Password must be at least 8 characters with 1 uppercase letter and 1 digit.",
    responses={
        201: {
            "description": "User created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "email": "user@example.com",
                        "first_name": None,
                        "last_name": None,
                    }
                }
            },
        },
        400: _400,
        409: _409,
    },
)
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


@router.post(
    "/login",
    summary="Login with email and password",
    description=(
        "Authenticates the user and sets **HttpOnly cookies** (`access_token`, `refresh_token`). "
        "After a successful login the browser will automatically send cookies with every subsequent request, "
        "including requests from Swagger UI (same origin). "
        "To test protected endpoints in Swagger UI you can also copy the token value and use the **Authorize** button (Bearer)."
    ),
    responses={
        200: {
            "description": "Login successful — HttpOnly cookies are set",
            "content": {"application/json": {"example": {"detail": "Logged in"}}},
        },
        401: {
            "description": "Invalid email or password",
            "content": {"application/json": {"example": {"detail": "Invalid credentials"}}},
        },
        400: _400,
    },
)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email, User.deleted_at == None).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token, refresh_token = create_token_pair(user.id, db)
    response.set_cookie("access_token", access_token, httponly=True, samesite="lax")
    response.set_cookie("refresh_token", refresh_token, httponly=True, samesite="lax")
    return {"detail": "Logged in"}


@router.post(
    "/refresh",
    summary="Refresh access token",
    description=(
        "Exchanges a valid **refresh_token** cookie for a new token pair. "
        "The old refresh token is revoked immediately."
    ),
    responses={
        200: {
            "description": "Tokens refreshed — new HttpOnly cookies are set",
            "content": {"application/json": {"example": {"detail": "Tokens refreshed"}}},
        },
        401: {
            "description": "Missing, invalid or revoked refresh token",
            "content": {"application/json": {"example": {"detail": "Invalid refresh token"}}},
        },
    },
)
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


@router.get(
    "/whoami",
    response_model=UserResponse,
    summary="Get current authenticated user",
    description=(
        "Returns the profile of the currently authenticated user. "
        "Requires a valid `access_token` cookie **or** a Bearer token in the `Authorization` header."
    ),
    responses={
        200: {
            "description": "Authenticated user profile",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "email": "user@example.com",
                        "first_name": "John",
                        "last_name": "Doe",
                    }
                }
            },
        },
        401: _401,
    },
)
def whoami(current_user: User = Depends(get_current_user)):
    return current_user


@router.post(
    "/logout",
    summary="Logout current session",
    description="Revokes the current access token and clears auth cookies.",
    responses={
        200: {
            "description": "Logged out successfully",
            "content": {"application/json": {"example": {"detail": "Logged out"}}},
        },
    },
)
def logout(
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    token = access_token or (credentials.credentials if credentials else None)
    if token:
        db_token = db.query(Token).filter(Token.token_hash == hash_token(token)).first()
        if db_token:
            db_token.is_revoked = True
            db.commit()
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"detail": "Logged out"}


@router.post(
    "/logout-all",
    summary="Logout all sessions",
    description=(
        "Revokes **all** active tokens for the authenticated user, terminating every session. "
        "Requires a valid `access_token` cookie or Bearer token."
    ),
    responses={
        200: {
            "description": "All sessions terminated",
            "content": {"application/json": {"example": {"detail": "All sessions terminated"}}},
        },
        401: _401,
    },
)
def logout_all(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(Token).filter(Token.user_id == current_user.id, Token.is_revoked == False).update({"is_revoked": True})
    db.commit()
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"detail": "All sessions terminated"}


@router.get(
    "/oauth/yandex",
    summary="Initiate Yandex OAuth2 login",
    description=(
        "Redirects the user to Yandex authorization page (Authorization Code flow). "
        "After successful authorization Yandex redirects back to `/auth/oauth/yandex/callback`."
    ),
    responses={
        302: {"description": "Redirect to Yandex OAuth authorization endpoint"},
    },
)
def yandex_login():
    state = secrets.token_urlsafe(16)
    url = (
        f"https://oauth.yandex.ru/authorize"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={CALLBACK_URL}"
        f"&state={state}"
    )
    redirect = RedirectResponse(url)
    redirect.set_cookie("oauth_state", state, httponly=True, samesite="lax")
    return redirect

@router.get(
    "/oauth/yandex/callback",
    response_model=UserResponse,
    summary="Yandex OAuth2 callback",
    description=(
        "Handles the authorization code returned by Yandex. "
        "Exchanges the code for tokens, creates or updates the user account, "
        "and sets HttpOnly auth cookies."
    ),
    responses={
        200: {
            "description": "OAuth login successful — user profile returned and cookies set",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "email": "yandex_user@yandex.ru",
                        "first_name": "Ivan",
                        "last_name": "Petrov",
                    }
                }
            },
        },
        400: {
            "description": "Invalid OAuth state parameter (CSRF protection)",
            "content": {"application/json": {"example": {"detail": "Invalid state parameter"}}},
        },
    },
)
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

    return UserResponse.model_validate(user)


@router.post(
    "/forgot-password",
    summary="Request a password reset token",
    description=(
        "Generates a one-time password reset token valid for **1 hour**. "
        "In a production system the token would be sent via email; "
        "here it is returned directly in the response for testing purposes."
    ),
    responses={
        200: {
            "description": "Reset token generated (or silently ignored if email not found)",
            "content": {
                "application/json": {
                    "examples": {
                        "token_generated": {
                            "summary": "Email found — token returned",
                            "value": {
                                "detail": "Reset token generated",
                                "reset_token": "v8Kx3mN9pQrL2wYjZ5tA1cE7hF4iG6uB",
                            },
                        },
                        "email_not_found": {
                            "summary": "Email not found — silent response",
                            "value": {"detail": "If email exists, reset link was sent"},
                        },
                    }
                }
            },
        },
        400: _400,
    },
)
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


@router.post(
    "/reset-password",
    summary="Reset password using a reset token",
    description=(
        "Sets a new password using the token obtained from `/auth/forgot-password`. "
        "The token is single-use and expires after 1 hour."
    ),
    responses={
        200: {
            "description": "Password updated successfully",
            "content": {"application/json": {"example": {"detail": "Password updated"}}},
        },
        400: {
            "description": "Invalid, used or expired reset token",
            "content": {"application/json": {"example": {"detail": "Invalid or expired token"}}},
        },
    },
)
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
