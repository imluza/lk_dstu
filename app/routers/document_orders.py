import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.deps import get_db, get_current_user, require_role_any
from app.core.config import settings
from app.models.user import User
from app.models.grade import Student as StudentModel
from app.models.document_order import DocumentOrder
from app.schemas.document_order import DocumentOrderCreate, DocumentOrderUpdate, DocumentOrderOut

router = APIRouter(prefix="/document_orders", tags=["document_orders"])

def save_admin_file(order_id: int, file: UploadFile) -> str:
    """Сохраняет готовый документ, прикрепляемый администратором"""
    ext = os.path.splitext(file.filename or "")[1] or ".pdf"
    rel_dir = os.path.join("document_orders", "ready")
    abs_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    fname = f"{order_id}_{uuid.uuid4().hex}{ext}"
    abs_path = os.path.join(abs_dir, fname)
    with open(abs_path, "wb") as f:
        f.write(file.file.read())
    return os.path.join(rel_dir, fname).replace("\\", "/")

@router.post("/", response_model=DocumentOrderOut,
             dependencies=[Depends(require_role_any(["student"]))])
async def create_document_order(
    data: DocumentOrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """📨 Создать заказ на документ (только студент)"""
    student = db.scalar(select(StudentModel).where(StudentModel.user_id == user.id))
    if not student:
        raise HTTPException(403, "Only students can create document orders")

    order = DocumentOrder(
        student_id=student.id,
        document_type=data.document_type.strip(),
        comment_student=data.comment_student,
        delivery_method=data.delivery_method,
        copies_count=data.copies_count,

    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.get("/my", response_model=list[DocumentOrderOut],
             dependencies=[Depends(require_role_any(["student"]))])
async def my_document_orders(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """📋 Мои заказы"""
    student = db.scalar(select(StudentModel).where(StudentModel.user_id == user.id))
    if not student:
        raise HTTPException(403, "Only students can view their orders")

    items = db.scalars(
        select(DocumentOrder)
        .where(DocumentOrder.student_id == student.id)
        .order_by(DocumentOrder.created_at.desc())
    ).all()
    return items

@router.get("/all", response_model=list[DocumentOrderOut],
             dependencies=[Depends(require_role_any(["administrator", "director"]))])
async def list_all_orders(
    db: Session = Depends(get_db),
    status: Optional[str] = None,
):
    """🧾 Все заказы студентов (для администрации)"""
    stmt = select(DocumentOrder)
    if status:
        stmt = stmt.where(DocumentOrder.status == status)
    items = db.scalars(stmt.order_by(DocumentOrder.created_at.desc())).all()
    return items


@router.post("/{order_id}/patch", response_model=DocumentOrderOut,
              dependencies=[Depends(require_role_any(["administrator", "director"]))])
async def update_order(
    order_id: int,
    data: DocumentOrderUpdate = Body(...),
    db: Session = Depends(get_db),
):
    """✏️ Обновить заказ (статус, комментарий)"""
    order = db.get(DocumentOrder, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    print(f"status={data.status} comment_admin={data.comment_admin}")

    if data.status:
        order.status = data.status
    if data.comment_admin:
        order.comment_admin = data.comment_admin

    db.commit()
    db.refresh(order)
    return order

@router.post("/{order_id}/student_approve", response_model=DocumentOrderOut,
              dependencies=[Depends(require_role_any(["student"]))])
async def student_approve_order(
    order_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    order = db.get(DocumentOrder, order_id)
    student = db.scalar(select(StudentModel).where(StudentModel.user_id == me.id))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.student_id != student.id:
        raise HTTPException(status_code=403, detail="Not your order")

    if order.status != "ready":
        raise HTTPException(status_code=400, detail="Order is not ready for approval")

    order.status = "student_approved"
    db.commit()
    db.refresh(order)
    return order

@router.post("/{order_id}/delete",
               dependencies=[Depends(require_role_any(["student", "administrator", "director"]))])
async def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """🗑️ Удалить заказ:
    - студент может удалить только свой новый заказ;
    - админ/директор — любой.
    """
    order = db.get(DocumentOrder, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    student = db.scalar(select(StudentModel).where(StudentModel.user_id == user.id))

    if student:
        if order.student_id != student.id:
            raise HTTPException(403, "Cannot delete other students' orders")
        if order.status != "new":
            raise HTTPException(403, "Order already processed")

    if order.result_file:
        abs_path = os.path.join(settings.MEDIA_ROOT, order.result_file)
        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except Exception:
                pass

    db.delete(order)
    db.commit()
    return {"status": "deleted", "id": order_id}
