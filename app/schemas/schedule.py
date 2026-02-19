from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional

class LessonCreate(BaseModel):
    group_code: str
    room_code: str
    starts_at: datetime
    ends_at: datetime
    lesson_type: Optional[str] = None
    notes: Optional[str] = None

    subject_id: Optional[int] = None
    teacher_id: Optional[int] = None

    subject_title: Optional[str] = None
    teacher_full_name: Optional[str] = None
    teacher_email: Optional[str] = None
    teacher_phone: Optional[str] = None
    teacher_subject: Optional[str] = None

    lesson_number: Optional[int] = None

    @field_validator("subject_title", mode="before")
    @classmethod
    def normalize_str(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("teacher_full_name", "teacher_email", "teacher_phone", "teacher_subject", mode="before")
    @classmethod
    def normalize_opt_str(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("subject_id")
    @classmethod
    def _check_subject(cls, v, info):
        other = info.data.get("subject_title")
        if v is None and not other:
            raise ValueError("either subject_id or subject_title is required")
        return v


class LessonTimeCreate(BaseModel):
    lesson_number: int
    start: str
    end: str

class LessonUpdate(BaseModel):
    group_code: Optional[str] = None
    subject_id: Optional[int] = None
    subject_title: Optional[str] = None
    teacher_id: Optional[int] = None
    teacher_full_name: Optional[str] = None
    teacher_email: Optional[str] = None
    teacher_phone: Optional[str] = None
    teacher_subject: Optional[str] = None
    room_code: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    lesson_type: Optional[str] = None
    notes: Optional[str] = None
    lesson_number: Optional[int] = None


class LessonOut(BaseModel):
    id: int
    group: str
    subject: str
    teacher: Optional[str] = None
    room: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    lesson_type: Optional[str] = None
    notes: Optional[str] = None
    lesson_number: Optional[int] = None
