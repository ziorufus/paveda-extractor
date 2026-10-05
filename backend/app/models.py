from sqlalchemy import Boolean, Column, ForeignKey, Integer, JSON, LargeBinary, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, deferred, mapped_column, relationship

from .database import Base, UTCDateTime, utcnow

project_users = Table(
    "project_users",
    Base.metadata,
    Column("project_id", ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

set_projects = Table(
    "set_projects",
    Base.metadata,
    Column("set_id", ForeignKey("project_sets.id", ondelete="CASCADE"), primary_key=True),
    Column("project_id", ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    # The first user to log in: always admin, cannot be demoted or deleted
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at = mapped_column(UTCDateTime, default=utcnow)
    last_login_at = mapped_column(UTCDateTime, nullable=True)

    projects: Mapped[list["Project"]] = relationship(secondary=project_users, back_populates="users")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Key used by the converter and by the old config.json sets (e.g. "old-norse.xlsx")
    excel_filename: Mapped[str] = mapped_column(String(255), unique=True)
    # CLDF language ID ("ID" in config.json); usually, but not always, the Glottocode
    language_id: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    glottocode: Mapped[str | None] = mapped_column(String(64))
    glottolog_name: Mapped[str | None] = mapped_column(String(255))
    family: Mapped[str | None] = mapped_column(String(255))
    iso639p3code: Mapped[str | None] = mapped_column(String(16))
    macroarea: Mapped[str | None] = mapped_column(String(64))
    # Kept as strings so the CSV output matches what was entered ("38.0" stays "38.0")
    latitude: Mapped[str | None] = mapped_column(String(32))
    longitude: Mapped[str | None] = mapped_column(String(32))
    contributors: Mapped[str | None] = mapped_column(Text)
    created_at = mapped_column(UTCDateTime, default=utcnow)
    updated_at = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    users: Mapped[list[User]] = relationship(secondary=project_users, back_populates="projects")
    sets: Mapped[list["ProjectSet"]] = relationship(secondary=set_projects, back_populates="projects")
    versions: Mapped[list["ProjectVersion"]] = relationship(
        back_populates="project",
        order_by="ProjectVersion.number.desc()",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Project attribute -> key expected by the converter (CLDF languages.csv columns)
    LANGUAGE_FIELDS = {
        "language_id": "ID",
        "name": "Name",
        "glottocode": "Glottocode",
        "glottolog_name": "Glottolog_Name",
        "family": "Family",
        "iso639p3code": "ISO639P3code",
        "macroarea": "Macroarea",
        "latitude": "Latitude",
        "longitude": "Longitude",
        "contributors": "contributors",
    }

    def to_language_dict(self):
        return {key: getattr(self, attr) for attr, key in self.LANGUAGE_FIELDS.items() if getattr(self, attr) is not None}


class ProjectVersion(Base):
    __tablename__ = "project_versions"
    __table_args__ = (UniqueConstraint("project_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = mapped_column(UTCDateTime, default=utcnow)
    original_filename: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[int] = mapped_column(Integer)
    excel_file: Mapped[bytes] = deferred(mapped_column(LargeBinary))
    log: Mapped[str | None] = deferred(mapped_column(Text, nullable=True))
    # True: conversion ran; False: conversion raised an exception; None: not checked (imported at first startup)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    statistics = mapped_column(JSON, nullable=True)

    project: Mapped[Project] = relationship(back_populates="versions")
    user: Mapped[User | None] = relationship()


class ProjectSet(Base):
    __tablename__ = "project_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(Text)

    projects: Mapped[list[Project]] = relationship(
        secondary=set_projects, back_populates="sets", order_by="Project.name"
    )
