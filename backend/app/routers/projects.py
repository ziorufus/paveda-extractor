import re
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload, undefer

from ..app_config import get_app_config
from ..auth import get_accessible_project, get_current_user, require_admin
from ..converter import check_excel
from ..database import get_db
from ..models import Project, ProjectVersion, User, project_users
from ..schemas import ProjectCreate, ProjectUpdate, VersionDetail, VersionOut
from ..serializers import project_out

router = APIRouter(tags=["projects"])

EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}
EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def attachment_headers(filename):
    ascii_name = filename.encode("ascii", "replace").decode().replace('"', "")
    return {"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"}


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "language"


def unique_excel_filename(db, name, exclude_id=None):
    base = slugify(name)
    candidate, counter = f"{base}.xlsx", 2
    while True:
        existing = db.scalar(select(Project).where(Project.excel_filename == candidate))
        if existing is None or existing.id == exclude_id:
            return candidate
        candidate, counter = f"{base}-{counter}.xlsx", counter + 1


def apply_project_fields(db, project, payload):
    data = payload.model_dump(exclude_unset=True)
    user_ids = data.pop("user_ids", None)

    for field in ("name", "language_id"):
        if field in data and data[field] is None:
            raise HTTPException(status_code=422, detail=f"'{field}' cannot be empty")
    if data.get("language_id"):
        existing = db.scalar(select(Project).where(Project.language_id == data["language_id"]))
        if existing is not None and existing.id != project.id:
            raise HTTPException(status_code=409, detail=f"Language ID '{data['language_id']}' is already used by {existing.name}")
    if "excel_filename" in data:
        if data["excel_filename"] is None:
            data["excel_filename"] = unique_excel_filename(db, data.get("name") or project.name, project.id)
        else:
            if not data["excel_filename"].lower().endswith(tuple(EXCEL_EXTENSIONS)):
                data["excel_filename"] += ".xlsx"
            existing = db.scalar(select(Project).where(Project.excel_filename == data["excel_filename"]))
            if existing is not None and existing.id != project.id:
                raise HTTPException(status_code=409, detail=f"File key '{data['excel_filename']}' is already used by {existing.name}")

    for field, value in data.items():
        setattr(project, field, value)
    if user_ids is not None:
        users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
        if len(users) != len(set(user_ids)):
            raise HTTPException(status_code=400, detail="Unknown user ID")
        project.users = list(users)


# Projects


@router.get("/projects")
def list_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(Project).options(selectinload(Project.versions).selectinload(ProjectVersion.user), selectinload(Project.users))
    if not user.is_admin:
        query = query.join(project_users).where(project_users.c.user_id == user.id)
    projects = db.scalars(query.order_by(Project.name)).all()
    return [project_out(project, include_users=user.is_admin) for project in projects]


@router.post("/projects", status_code=201, dependencies=[Depends(require_admin)])
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=payload.name, language_id=payload.language_id)
    apply_project_fields(db, project, payload)
    if not project.excel_filename:
        project.excel_filename = unique_excel_filename(db, project.name)
    db.add(project)
    db.commit()
    return project_out(project)


@router.get("/projects/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = get_accessible_project(project_id, user, db)
    return project_out(project, include_users=user.is_admin)


@router.patch("/projects/{project_id}", dependencies=[Depends(require_admin)])
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    apply_project_fields(db, project, payload)
    db.commit()
    return project_out(project)


@router.delete("/projects/{project_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()


# Versions


def get_accessible_version(version_id, user, db, *options):
    version = db.get(ProjectVersion, version_id, options=list(options))
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    get_accessible_project(version.project_id, user, db)
    return version


@router.get("/projects/{project_id}/versions", response_model=list[VersionOut])
def list_versions(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_accessible_project(project_id, user, db).versions


@router.post("/projects/{project_id}/versions", status_code=201, response_model=VersionDetail)
async def upload_version(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = await run_in_threadpool(get_accessible_project, project_id, user, db)
    filename = Path(file.filename or "upload.xlsx").name
    if Path(filename).suffix.lower() not in EXCEL_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Please upload an Excel file (.xlsx, .xlsm or .xls)")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")

    result = await run_in_threadpool(check_excel, get_app_config(), project, data)

    def save():
        number = (db.scalar(select(func.max(ProjectVersion.number)).where(ProjectVersion.project_id == project.id)) or 0) + 1
        version = ProjectVersion(
            project_id=project.id,
            number=number,
            user_id=user.id,
            original_filename=filename,
            file_size=len(data),
            excel_file=data,
            log=result.log,
            success=result.success,
            error_count=result.error_count,
            warning_count=result.warning_count,
            statistics=result.statistics,
        )
        db.add(version)
        db.commit()
        db.refresh(version, ["user"])
        return version

    return await run_in_threadpool(save)


@router.get("/versions/{version_id}", response_model=VersionDetail)
def get_version(version_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_accessible_version(version_id, user, db, undefer(ProjectVersion.log))


@router.get("/versions/{version_id}/excel")
def download_excel(version_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    version = get_accessible_version(version_id, user, db, undefer(ProjectVersion.excel_file))
    return Response(version.excel_file, media_type=EXCEL_MEDIA_TYPE, headers=attachment_headers(version.original_filename))


@router.get("/versions/{version_id}/log")
def download_log(version_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    version = get_accessible_version(version_id, user, db, undefer(ProjectVersion.log))
    filename = f"{Path(version.project.excel_filename).stem}-v{version.number}-log.txt"
    return Response(version.log or "", media_type="text/plain; charset=utf-8", headers=attachment_headers(filename))


@router.delete("/versions/{version_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_version(version_id: int, db: Session = Depends(get_db)):
    version = db.get(ProjectVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    db.delete(version)
    db.commit()
