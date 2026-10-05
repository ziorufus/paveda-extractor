from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..auth import require_admin
from ..database import get_db
from ..models import Project, User
from ..schemas import UserCreate, UserUpdate
from ..serializers import user_out

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])


def load_projects(db, project_ids):
    projects = db.scalars(select(Project).where(Project.id.in_(project_ids))).all()
    if len(projects) != len(set(project_ids)):
        raise HTTPException(status_code=400, detail="Unknown project ID")
    return list(projects)


def check_email_free(db, email, user_id=None):
    existing = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if existing is not None and existing.id != user_id:
        raise HTTPException(status_code=409, detail=f"A user with e-mail {email} already exists")


def get_user_or_404(db, user_id):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("")
def list_users(db: Session = Depends(get_db)):
    users = db.scalars(select(User).options(selectinload(User.projects)).order_by(User.name, User.email)).all()
    return [user_out(user) for user in users]


@router.post("", status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    email = payload.email.lower()
    check_email_free(db, email)
    user = User(email=email, name=payload.name.strip(), is_admin=payload.is_admin, projects=load_projects(db, payload.project_ids))
    db.add(user)
    db.commit()
    return user_out(user)


@router.patch("/{user_id}")
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    user = get_user_or_404(db, user_id)
    if payload.email is not None:
        email = payload.email.lower()
        check_email_free(db, email, user.id)
        user.email = email
    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.is_admin is not None:
        if user.is_owner and not payload.is_admin:
            raise HTTPException(status_code=400, detail="The first administrator cannot be demoted")
        user.is_admin = payload.is_admin
    if payload.project_ids is not None:
        user.projects = load_projects(db, payload.project_ids)
    db.commit()
    return user_out(user)


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), current: User = Depends(require_admin)):
    user = get_user_or_404(db, user_id)
    if user.is_owner:
        raise HTTPException(status_code=400, detail="The first administrator cannot be deleted")
    if user.id == current.id:
        raise HTTPException(status_code=400, detail="You cannot delete yourself")
    db.delete(user)
    db.commit()
