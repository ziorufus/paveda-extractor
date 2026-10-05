import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from ..app_config import get_app_config
from ..auth import require_admin
from ..converter import convert
from ..database import get_db, utcnow
from ..models import Project, ProjectVersion
from ..schemas import ExportRequest

router = APIRouter(prefix="/export", tags=["export"], dependencies=[Depends(require_admin)])


def exportable_version(project):
    """Latest version whose conversion did not fail (versions are ordered newest first)."""
    return next((version for version in project.versions if version.success is not False), None)


def collect_languages(db, project_ids):
    projects = db.scalars(select(Project).where(Project.id.in_(project_ids)).order_by(Project.excel_filename)).all()
    if len(projects) != len(set(project_ids)):
        raise HTTPException(status_code=400, detail="Unknown project ID")

    languages, versions, missing = [], {}, []
    for project in projects:
        version = exportable_version(project)
        if version is None:
            missing.append(project.name)
            continue
        excel_bytes = db.scalar(select(ProjectVersion.excel_file).where(ProjectVersion.id == version.id))
        languages.append((project.to_language_dict(), project.excel_filename, excel_bytes))
        versions[project.excel_filename] = {
            "project": project.name,
            "version": version.number,
            "uploaded_at": version.created_at.isoformat(),
            "uploaded_by": version.user.email if version.user else None,
            "original_filename": version.original_filename,
        }
    if missing:
        raise HTTPException(status_code=400, detail=f"No usable Excel version for: {', '.join(missing)}")
    return languages, versions


@router.post("")
async def export(payload: ExportRequest, db: Session = Depends(get_db)):
    languages, versions = await run_in_threadpool(collect_languages, db, payload.project_ids)

    temp_dir = Path(tempfile.mkdtemp(prefix="valpal-export-"))
    output_dir = temp_dir / "output"
    result = await run_in_threadpool(convert, get_app_config(), languages, output_dir)
    if not result.success:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail={"message": "Conversion failed", "log": result.log})

    timestamp = utcnow().strftime("%Y%m%d-%H%M%S")
    zip_path = temp_dir / "export.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("log.txt", result.log)
        archive.writestr("summary.json", json.dumps({"versions": versions, "statistics": result.statistics}, indent=2, ensure_ascii=False))
        for file_path in sorted(path for path in output_dir.iterdir() if path.is_file()):
            archive.write(file_path, arcname=file_path.name)

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"valpal-export-{timestamp}.zip",
        background=BackgroundTask(shutil.rmtree, temp_dir, ignore_errors=True),
    )
