from pydantic import BaseModel, EmailStr, field_validator
from datetime import date, datetime
from typing import List, Optional

class AuditOut(BaseModel):
    id: int
    user_id: int | None
    method: str
    path: str
    query: str | None
    status_code: int
    ip: str | None
    user_agent: str | None
    created_at: datetime

class AdminUserUpdate(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None
    full_name: str | None = None
    is_active: bool | None = None
    password: str | None = None

class AdminStudentUpdate(BaseModel):
    group_id: int | None = None
    record_book: str | None = None
    insert_year: str | None = None
    course: str | None = None

class AdminAssignRoles(BaseModel):
    roles: List[str]

class RoleCreateIn(BaseModel):
    name: str
    description: str | None = None

class PermissionCreateIn(BaseModel):
    code: str
    description: str | None = None

class RolePermissionAssignIn(BaseModel):
    permissions: List[str]

class GroupCreateIn(BaseModel):
    code: str
    title: str

class TeacherCreateIn(BaseModel):
    full_name: str
    email: str | None = None
    phone: str | None = None
    subject: str | None = None
    user_id: int | None = None
    subdivision_id: int | None = None
    subject_ids: List[int] | None = None

class TeacherSubjectsIn(BaseModel):
    subject_ids: List[int]

class RoomCreateIn(BaseModel):
    code: str
    title: str
    capacity: int | None = None

class SubjectCreateIn(BaseModel):
    title: str
    code: Optional[str] = None
    teacher_id: Optional[int] = None
    type_id: Optional[int] = None

class SubjectAssignTeacherIn(BaseModel):
    teacher_id: int

class SubdivisionCreateIn(BaseModel):
    name: str
    type: str | None = None
    code: str | None = None
    parent_id: int | None = None

class SubdivisionAssignTeachersIn(BaseModel):
    teacher_ids: List[int]

class AdminCreateUser(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    phone: str | None = None
    birth_date: date | None = None
    avatar_url: str | None = None
    roles: list[str]

    @field_validator("full_name", "phone", "avatar_url", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        return None if isinstance(v, str) and v.strip() == "" else v

    @field_validator("birth_date", mode="before")
    @classmethod
    def parse_birth_date(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        if isinstance(v, date):
            return v
        return date.fromisoformat(v)
