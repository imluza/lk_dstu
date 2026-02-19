from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

OrderStatus = Literal["new", "in_progress", "ready", "rejected", "student_approved"]

class DocumentOrderCreate(BaseModel):
    document_type: str = Field(..., description="Тип справки")
    delivery_method: str = Field(..., description="Как получить справку")
    copies_count: int = Field(..., description="Кол-во экземпляров")
    comment_student: Optional[str] = Field(None, description="Комментарий студента")

class DocumentOrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    comment_admin: Optional[str] = None

class DocumentOrderOut(BaseModel):
    id: int
    student_id: int
    document_type: str
    copies_count: int
    delivery_method: str
    comment_student: Optional[str]
    status: OrderStatus
    comment_admin: Optional[str]
    result_file: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
