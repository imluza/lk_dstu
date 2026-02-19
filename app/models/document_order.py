from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

OrderStatusEnum = Enum(
    "new",
    "in_progress",
    "ready",
    "rejected",
    "student_approved",
    name="document_order_status_enum"
)

class DocumentOrder(Base):
    __tablename__ = "document_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)

    document_type: Mapped[str] = mapped_column(String(255))
    comment_student: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_method: Mapped[str] = mapped_column(String(255))
    copies_count: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(OrderStatusEnum, default="in_progress")
    comment_admin: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_file: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = relationship("Student", back_populates="document_orders")
