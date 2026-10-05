from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import require_admin
from ..database import get_db
from ..models import Project, ProjectSet
from ..schemas import SetCreate, SetFields
from ..serializers import set_out

router = APIRouter(prefix="/sets", tags=["sets"], dependencies=[Depends(require_admin)])


def apply_set_fields(db, project_set, payload):
    data = payload.model_dump(exclude_unset=True)
    if data.get("name") is not None:
        name = data["name"].strip()
        existing = db.scalar(select(ProjectSet).where(ProjectSet.name == name))
        if existing is not None and existing.id != project_set.id:
            raise HTTPException(status_code=409, detail=f"A set named '{name}' already exists")
        project_set.name = name
    if "description" in data:
        project_set.description = (data["description"] or "").strip() or None
    if data.get("project_ids") is not None:
        projects = db.scalars(select(Project).where(Project.id.in_(data["project_ids"]))).all()
        if len(projects) != len(set(data["project_ids"])):
            raise HTTPException(status_code=400, detail="Unknown project ID")
        project_set.projects = list(projects)


def get_set_or_404(db, set_id):
    project_set = db.get(ProjectSet, set_id)
    if project_set is None:
        raise HTTPException(status_code=404, detail="Set not found")
    return project_set


@router.get("")
def list_sets(db: Session = Depends(get_db)):
    sets = db.scalars(select(ProjectSet).options(selectinload(ProjectSet.projects)).order_by(ProjectSet.name)).all()
    return [set_out(project_set) for project_set in sets]


@router.post("", status_code=201)
def create_set(payload: SetCreate, db: Session = Depends(get_db)):
    project_set = ProjectSet()
    apply_set_fields(db, project_set, payload)
    db.add(project_set)
    db.commit()
    return set_out(project_set)


@router.patch("/{set_id}")
def update_set(set_id: int, payload: SetFields, db: Session = Depends(get_db)):
    project_set = get_set_or_404(db, set_id)
    apply_set_fields(db, project_set, payload)
    db.commit()
    return set_out(project_set)


@router.delete("/{set_id}", status_code=204)
def delete_set(set_id: int, db: Session = Depends(get_db)):
    db.delete(get_set_or_404(db, set_id))
    db.commit()
