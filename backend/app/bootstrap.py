"""First-startup initialisation: creates the tables and imports the languages from config.json."""

import logging
from pathlib import Path

from sqlalchemy import func, select

from .app_config import get_app_config
from .database import Base, SessionLocal, engine
from .models import Project, ProjectSet, ProjectVersion

logger = logging.getLogger(__name__)


def project_from_language(language, excel_filename):
    values = {attr: language.get(key) for attr, key in Project.LANGUAGE_FIELDS.items()}
    for attr in ("latitude", "longitude"):
        if values[attr] is not None:
            values[attr] = str(values[attr])
    return Project(excel_filename=excel_filename, **values)


def iter_config_languages(languages):
    if isinstance(languages, dict):
        yield from languages.items()
    else:
        for language in languages:
            yield language["excel_filename"], language


def init_db():
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        if db.scalar(select(func.count(Project.id))) > 0:
            return

        config = get_app_config()
        excel_folder = Path(config["excel_folder"])
        projects = {}
        for excel_filename, language in iter_config_languages(config["languages"]):
            project = project_from_language(language, excel_filename)
            excel_path = excel_folder / excel_filename
            if excel_path.is_file():
                data = excel_path.read_bytes()
                project.versions.append(
                    ProjectVersion(
                        number=1,
                        original_filename=excel_filename,
                        file_size=len(data),
                        excel_file=data,
                        log=f"Imported from {excel_path} at first startup: conversion not run.",
                        success=None,
                    )
                )
            db.add(project)
            projects[excel_filename] = project

        for set_name, excel_filenames in config.get("sets", {}).items():
            members = [projects[name] for name in excel_filenames if name in projects]
            db.add(ProjectSet(name=set_name, projects=members))

        db.commit()
        imported = sum(1 for project in projects.values() if project.versions)
        logger.info("First startup: imported %d languages (%d with an Excel file)", len(projects), imported)
