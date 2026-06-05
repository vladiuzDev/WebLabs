import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, HTTPException, Response, Security, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.config import CALLBACK_URL, CLIENT_ID, JWT_ACCESS_SECRET, JWT_REFRESH_SECRET
from src.core.middleware import bearer_scheme, get_current_user
from src.models.password_reset import PasswordReset
from src.models.token import Token
from src.models.user import User
from src.schemas.auth import ForgotPasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest, UserResponse
from src.services.auth import (
    create_token_pair,
    decode_token,
    get_yandex_user,
    hash_password,
    hash_token,
    verify_password,
)
from src.services.cache import cache, make_key

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
async def register(body: RegisterRequest):
    existing = await User.find_one(User.email == body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    password_hash, salt = hash_password(body.password)
    user = User(email=body.email, password_hash=password_hash, salt=salt)
    await user.insert()
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
async def login(body: LoginRequest, response: Response):
    user = await User.find_one(User.email == body.email, User.deleted_at == None)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token, refresh_token = await create_token_pair(user.id)
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
async def refresh(response: Response, refresh_token: str | None = Cookie(default=None)):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    try:
        payload = decode_token(refresh_token, JWT_REFRESH_SECRET)
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token = await Token.find_one(
        Token.token_hash == hash_token(refresh_token),
        Token.is_revoked == False,
    )
    if not token:
        raise HTTPException(status_code=401, detail="Token revoked")

    token.is_revoked = True
    await token.save()

    access_token, new_refresh_token = await create_token_pair(uuid.UUID(user_id))
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
async def whoami(current_user: User = Security(get_current_user)):
    cache_key = make_key("users", "profile", str(current_user.id))
    cached = cache.get(cache_key)
    if cached is not None:
        return UserResponse.model_validate(cached)
    user_data = UserResponse.model_validate(current_user).model_dump(mode="json")
    cache.set(cache_key, user_data)
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
async def logout(
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    access_token: str | None = Cookie(default=None),
):
    token = access_token or (credentials.credentials if credentials else None)
    if token:
        db_token = await Token.find_one(Token.token_hash == hash_token(token))
        if db_token:
            db_token.is_revoked = True
            await db_token.save()
        try:
            payload = decode_token(token, JWT_ACCESS_SECRET)
            user_id = payload.get("sub")
            jti = payload.get("jti")
            if user_id and jti:
                cache.delete(make_key("auth", "user", user_id, "access", jti))
            if user_id:
                cache.delete(make_key("users", "profile", user_id))
        except Exception:
            pass
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
async def logout_all(
    response: Response,
    current_user: User = Security(get_current_user),
):
    await Token.find(
        Token.user_id == current_user.id,
        Token.is_revoked == False,
    ).update({"$set": {"is_revoked": True}})
    cache.delete_by_pattern(make_key("auth", "user", str(current_user.id), "access", "*"))
    cache.delete(make_key("users", "profile", str(current_user.id)))
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
async def yandex_login(response: Response):
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
    oauth_state: str | None = Cookie(default=None),
):
    if not oauth_state or oauth_state != state:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    yandex_data = await get_yandex_user(code)

    yandex_id = str(yandex_data.get("id"))
    email = yandex_data.get("default_email")
    first_name = yandex_data.get("first_name")
    last_name = yandex_data.get("last_name")

    user = await User.find_one(User.yandex_id == yandex_id)
    if not user:
        user = await User.find_one(User.email == email)
    if not user:
        user = User(yandex_id=yandex_id, email=email, first_name=first_name, last_name=last_name)
        await user.insert()
    else:
        user.yandex_id = yandex_id
        user.updated_at = datetime.now(timezone.utc)
        await user.save()

    access_token, refresh_token = await create_token_pair(user.id)
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
async def forgot_password(body: ForgotPasswordRequest):
    user = await User.find_one(User.email == body.email, User.deleted_at == None)
    if not user:
        return {"detail": "If email exists, reset link was sent"}

    token = secrets.token_urlsafe(32)
    reset = PasswordReset(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    await reset.insert()

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
async def reset_password(body: ResetPasswordRequest):
    reset = await PasswordReset.find_one(
        PasswordReset.token_hash == hash_token(body.token),
        PasswordReset.is_used == False,
        PasswordReset.expires_at > datetime.now(timezone.utc),
    )

    if not reset:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = await User.find_one(User.id == reset.user_id)
    password_hash, salt = hash_password(body.new_password)
    user.password_hash = password_hash
    user.salt = salt
    user.updated_at = datetime.now(timezone.utc)
    await user.save()

    reset.is_used = True
    await reset.save()

    return {"detail": "Password updated"}
