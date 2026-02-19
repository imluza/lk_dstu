from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os
import tempfile
from app.core.deps import get_db, require_role_any
from app.services.user_importer import import_users_from_excel

router = APIRouter(prefix="/admin/users/import", tags=["admin-users"])

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "static", "users_template.xlsx")
EXPORT_DIR = "exports"

@router.get("/template")
def download_template():
    """Скачать шаблон Excel для импорта расписания."""
    if not os.path.exists(TEMPLATE_PATH):
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    return FileResponse(
        TEMPLATE_PATH,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="Шаблон Импорта пользователей.xlsx"
    )

@router.post("/")
async def import_users(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(require_role_any(["administrator", "director"]))
):
    """📥 Импорт пользователей из Excel и возврат Excel с логинами и паролями"""
    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(400, "Неверный формат файла (требуется .xls или .xlsx)")

    os.makedirs(EXPORT_DIR, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        export_path = import_users_from_excel(db, tmp_path, EXPORT_DIR)
    finally:
        os.remove(tmp_path)

    if not os.path.exists(export_path):
        raise HTTPException(500, "Ошибка при создании Excel")

    return FileResponse(
        export_path,
        filename="результат_импорта.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
