from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import admin_credentials, cfg, env, jwt_secret
from app.database import get_db
from app.logging_config import get_logger
from app.models import User

logger = get_logger("jobportal.auth")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        logger.exception("password verify failed")
        return False


def create_access_token(username: str) -> str:
    hours = int(cfg("auth", "jwt_expire_hours", default=72) or 72)
    expire = datetime.utcnow() + timedelta(hours=hours)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, jwt_secret(), algorithms=[ALGORITHM])
        sub = payload.get("sub")
        return str(sub) if sub else None
    except JWTError:
        return None
    except Exception:
        logger.exception("token decode failed")
        return None


def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    username = decode_token(credentials.credentials)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    try:
        user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    except Exception:
        logger.exception("admin lookup failed")
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    if not user or not user.is_admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin access required")
    return user


def ensure_admin_user(db: Session) -> None:
    """Create the bootstrap admin and migrate any legacy plaintext password."""
    try:
        username = env("ADMIN_USERNAME") or "admin"
        existing = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if existing:
            if not pwd_context.identify(existing.password_hash):
                existing.password_hash = hash_password(existing.password_hash)
                db.commit()
                logger.warning("legacy admin password migrated to a one-way hash")
            return
        _, password = admin_credentials()
        from uuid import uuid4

        user = User(
            id=str(uuid4()),
            username=username,
            password_hash=hash_password(password),
            is_admin=True,
            created_at=datetime.utcnow(),
        )
        db.add(user)
        db.commit()
        logger.info("admin user created username=%s", username)
    except Exception:
        db.rollback()
        logger.exception("ensure_admin_user failed")
