from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, List

GradeType =[
    "1", "2", "3", "4", "5", "Н", "Б", "О", "У", "н", "б", "о", "у"
]

GradeTypeFinal = [
    "1", "2", "3", "4", "5"
]

class GradeCreate(BaseModel):
    student_id: int
    teacher_id: int | None = None
    lesson_id: int
    grade_type: str
    value: str
    graded_at: datetime
    comment: str | None = None

class GradeUpdate(BaseModel):
    grade_type: Optional[str] = None
    value: Optional[str] = None
    comment: Optional[str] = None
    graded_at: Optional[datetime] = None
    subject_id: Optional[int] = None
    lesson_id: Optional[int] = None
    teacher_id: Optional[int] = None

class FinalGradeIn(BaseModel):
    student_id: int
    subject_id: int
    value: str
    comment: str | None = None

class GradeOut(BaseModel):
    id: int
    student_id: int
    subject_id: int
    teacher_id: int | None
    lesson_id: int | None
    grade_type: str
    value: str
    graded_at: datetime
    comment: str | None
    modified_by_admin_id: int | None = None


class FinalGradePatch(BaseModel):
    value: str | None = None
    comment: str | None = None
