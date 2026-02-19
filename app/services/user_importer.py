import pandas as pd
import secrets
import csv
import os
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.user import User
from app.models.grade import Student
from app.models.profile import Director, AdminProfile
from app.models.schedule import Teacher
from app.models.role import Role, user_roles
from app.models.schedule import Group
from app.core.security import hash_password


def get_or_create(db, model, where: dict, defaults: dict = {}):
    inst = db.scalar(select(model).filter_by(**where))
    if inst:
        return inst
    inst = model(**where, **defaults)
    db.add(inst)
    db.flush()
    return inst


def import_users_from_excel(db: Session, file_path: str, export_dir: str = "exports"):
    """Импорт пользователей из Excel + экспорт CSV с логинами и паролями"""
    df = pd.read_excel(file_path).fillna("")
    os.makedirs(export_dir, exist_ok=True)
    csv_path = os.path.join(export_dir, "imported_users.csv")

    created, skipped = 0, 0
    export_data = []

    for _, row in df.iterrows():
        full_name = str(row["ФИО"]).strip()
        email = str(row["Электронная почта"]).strip().lower()
        role_name = str(row["Роль"]).strip().lower()

        if not full_name or not email or not role_name:
            skipped += 1
            continue

        if db.scalar(select(User).where(User.email == email)):
            skipped += 1
            continue

        raw_password = secrets.token_urlsafe(8)
        password_hash = hash_password(raw_password)

        user = User(
            email=email,
            full_name=full_name,
            phone=row["Телефон"] or None,
            birth_date=row["Дата рождения"] or None,
            password_hash=password_hash,
            is_active=True,
        )
        db.add(user)
        db.flush()

        mapping = {
            "студент": "student",
            "преподаватель": "teacher",
            "директор": "director",
            "администратор": "administrator"
        }
        role_name_eng = mapping.get(role_name, "student")

        role = db.scalar(select(Role).where(Role.name == role_name_eng))
        if not role:
            role = Role(name=role_name_eng, description=f"Auto-created from import")
            db.add(role)
            db.flush()

        db.execute(user_roles.insert().values(user_id=user.id, role_id=role.id))

        if role_name_eng == "student":
            group_raw = str(row["Группа"]).strip()
            if not group_raw:
                raise ValueError(f"Укажите группу для студента: {full_name}")

            parts = [p.strip() for p in group_raw.split(",", 1) if p.strip()]
            if len(parts) == 2:
                group_code, group_title = parts
            else:
                group_code = parts[0]
                group_title = parts[0]

            group = get_or_create(
                db,
                Group,
                {"code": group_code},
                {"title": group_title}
            )
            db.add(Student(user_id=user.id, group_id=group.id))

        elif role_name_eng == "teacher":
            subject = str(row["Предмет"]).strip() or None
            db.add(Teacher(
                user_id=user.id,
                full_name=full_name,
                email=email,
                phone=row["Телефон"] or None,
                subject=subject
            ))


        elif role_name_eng == "director":
            db.add(Director(
                user_id=user.id,
                full_name=full_name,
                email=email,
                phone=row["Телефон"] or None,
            ))

        elif role_name_eng == "administrator":
            db.add(AdminProfile(user_id=user.id))

        export_data.append({
            "ФИО": full_name,
            "Email": email,
            "Роль": role_name,
            "Пароль": raw_password
        })

        created += 1

    db.commit()

    os.makedirs(export_dir, exist_ok=True)
    export_path = os.path.join(export_dir, "результат_импорта.xlsx")

    df_export = pd.DataFrame(export_data)
    df_export.to_excel(export_path, index=False)

    print(f"✅ Импорт завершён: {created} создано, {skipped} пропущено")
    print(f"📁 Excel сохранён: {export_path}")
    return export_path
