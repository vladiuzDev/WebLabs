from fastapi import Cookie, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from src.core.config import JWT_ACCESS_SECRET
from src.models.token import Token
from src.models.user import User
from src.services.auth import decode_token, hash_token


def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: Session = None,
) -> User:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_token(access_token, JWT_ACCESS_SECRET)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    token = db.query(Token).filter(
        Token.token_hash == hash_token(access_token),
        Token.is_revoked == False,
    ).first()

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    user = db.query(User).filter(User.id == user_id, User.deleted_at == None).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user