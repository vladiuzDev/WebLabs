from fastapi import Cookie, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from src.core.config import JWT_ACCESS_SECRET
from src.core.database import get_db
from src.models.token import Token
from src.models.user import User
from src.services.auth import decode_token, hash_token
from src.services.cache import cache, make_key

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = access_token
    if not token and credentials:
        token = credentials.credentials

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_token(token, JWT_ACCESS_SECRET)
        user_id = payload.get("sub")
        jti = payload.get("jti")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # --- Token validation: Redis (primary) → DB (fallback) ---
    if jti:
        redis_key = make_key("auth", "user", user_id, "access", jti)
        exists = cache.check_exists(redis_key)
        if exists is False:
            # Redis available but JTI not found → token was revoked
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")
        elif exists is None:
            # Redis unavailable → fall back to DB hash check
            _check_db_token(token, db)
        # exists is True → valid, proceed
    else:
        # Old token without JTI (pre-lab5) → DB only
        _check_db_token(token, db)

    user = db.query(User).filter(User.id == user_id, User.deleted_at == None).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


def _check_db_token(token: str, db: Session) -> None:
    db_token = db.query(Token).filter(
        Token.token_hash == hash_token(token),
        Token.is_revoked == False,
    ).first()
    if not db_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")
