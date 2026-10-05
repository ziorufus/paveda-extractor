from datetime import timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db, utcnow
from .models import Project, User
from .settings import get_settings

JWT_ALGORITHM = "HS256"

bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(user):
    settings = get_settings()
    now = utcnow()
    payload = {"sub": str(user.id), "iat": now, "exp": now + timedelta(hours=settings.token_expire_hours)}
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(credentials.credentials, get_settings().secret_key, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


def require_admin(user: User = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator privileges required")
    return user


def can_access_project(user, project):
    return user.is_admin or any(member.id == user.id for member in project.users)


def get_accessible_project(project_id, user, db):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not can_access_project(user, project):
        raise HTTPException(status_code=403, detail="You are not assigned to this project")
    return project
