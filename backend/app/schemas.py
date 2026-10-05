from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Users


class UserBrief(ORMModel):
    id: int
    email: str
    name: str


class UserOut(UserBrief):
    is_admin: bool
    is_owner: bool
    created_at: datetime
    last_login_at: datetime | None
    project_ids: list[int] = []


class UserCreate(BaseModel):
    email: EmailStr
    name: str = ""
    is_admin: bool = False
    project_ids: list[int] = []


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    name: str | None = None
    is_admin: bool | None = None
    project_ids: list[int] | None = None


# Versions


class VersionOut(ORMModel):
    id: int
    project_id: int
    number: int
    created_at: datetime
    user: UserBrief | None
    original_filename: str
    file_size: int
    success: bool | None
    error_count: int
    warning_count: int


class VersionDetail(VersionOut):
    log: str | None
    statistics: dict | None


# Projects


def _blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class ProjectFields(BaseModel):
    name: str | None = None
    language_id: str | None = None
    excel_filename: str | None = None
    glottocode: str | None = None
    glottolog_name: str | None = None
    family: str | None = None
    iso639p3code: str | None = None
    macroarea: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    contributors: str | None = None
    user_ids: list[int] | None = None

    @field_validator("*", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        return _blank_to_none(value)

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def numeric_coordinate(cls, value):
        value = _blank_to_none(value)
        if value is None:
            return None
        value = str(value)
        try:
            float(value)
        except ValueError as exc:
            raise ValueError("must be a number") from exc
        return value


class ProjectCreate(ProjectFields):
    name: str
    language_id: str


class ProjectUpdate(ProjectFields):
    pass


class ProjectOut(ORMModel):
    id: int
    name: str
    language_id: str
    excel_filename: str
    glottocode: str | None
    glottolog_name: str | None
    family: str | None
    iso639p3code: str | None
    macroarea: str | None
    latitude: str | None
    longitude: str | None
    contributors: str | None
    created_at: datetime
    updated_at: datetime
    user_ids: list[int] = []
    version_count: int = 0
    latest_version: VersionOut | None = None


# Sets


class SetFields(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    project_ids: list[int] | None = None


class SetCreate(SetFields):
    name: str = Field(min_length=1)
    project_ids: list[int] = []


class SetOut(ORMModel):
    id: int
    name: str
    description: str | None
    project_ids: list[int]


# Export


class ExportRequest(BaseModel):
    project_ids: list[int] = Field(min_length=1)
