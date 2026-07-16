from datetime import datetime, timedelta, timezone
from hashlib import sha256

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings
from .errors import api_error


security = HTTPBearer(auto_error=False)


def authenticate(username: str, password: str) -> bool:
    return username == settings.admin_username and sha256(password.encode()).hexdigest() == settings.admin_password_hash


def create_token() -> str:
    payload = {"sub": settings.admin_username, "exp": datetime.now(timezone.utc) + timedelta(hours=8)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def require_admin(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> str:
    if credentials is None:
        raise api_error(401, "authentication_required", "Administrator authentication is required.")
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise api_error(401, "invalid_token", "The administrator token is invalid or expired.") from exc
    if payload.get("sub") != settings.admin_username:
        raise api_error(401, "invalid_token", "The administrator token is invalid or expired.")
    return settings.admin_username

