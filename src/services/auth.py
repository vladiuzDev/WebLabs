import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import httpx
from jose import jwt
from sqlalchemy.orm import Session

from src.core.config import (
    ACCESS_TOKEN_EXPIRE_SECONDS,
    CLIENT_ID,
    CLIENT_SECRET,
    JWT_ACCESS_SECRET,
    JWT_REFRESH_SECRET,
)
from src.models.token import Token
from src.models.user import User
from src.services.cache import cache, make_key


def generate_salt() -> str:
    return bcrypt.gensalt().decode()


def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if salt is None:
        salt = generate_salt()
    hashed = bcrypt.hashpw(password.encode(), salt.encode()).decode()
    return hashed, salt


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_jwt(data: dict, secret: str, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(to_encode, secret, algorithm="HS256")


def create_token_pair(user_id: uuid.UUID, db: Session) -> tuple[str, str]:
    jti = str(uuid.uuid4())

    access_token = create_jwt(
        {"sub": str(user_id), "type": "access", "jti": jti},
        JWT_ACCESS_SECRET,
        timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS),
    )
    refresh_token = create_jwt(
        {"sub": str(user_id), "type": "refresh"},
        JWT_REFRESH_SECRET,
        timedelta(days=7),
    )

    db.add(Token(
        user_id=user_id,
        token_hash=hash_token(access_token),
        token_type="access",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS),
    ))
    db.add(Token(
        user_id=user_id,
        token_hash=hash_token(refresh_token),
        token_type="refresh",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    ))
    db.commit()

    # Store JTI in Redis: wp:auth:user:{userId}:access:{jti}
    redis_key = make_key("auth", "user", str(user_id), "access", jti)
    cache.set(redis_key, str(user_id), ttl=ACCESS_TOKEN_EXPIRE_SECONDS)

    return access_token, refresh_token


def decode_token(token: str, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=["HS256"])


async def get_yandex_user(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth.yandex.ru/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )
        token_data = token_resp.json()
        access_token = token_data["access_token"]

        user_resp = await client.get(
            "https://login.yandex.ru/info",
            headers={"Authorization": f"OAuth {access_token}"},
        )
        return user_resp.json()
