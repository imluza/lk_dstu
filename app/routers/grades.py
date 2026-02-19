from fastapi import APIRouter, Depends, HTTPException, Response, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from datetime import datetime
from openpyxl import Workbook
from io import BytesIO

from app.core.deps import get_db, require_permission, get_current_user, is_admin
from app.schemas.grade import GradeCreate, GradeOut, GradeUpdate, FinalGradeIn, FinalGradePatch, GradeTypeFinal, GradeType
from app.models.grade import Grade, Student
from app.models.schedule import Lesson, Teacher, Subject, teacher_subjects
from app.models.role import Role, user_roles
from app.models.user import User
from app.models.schedule import Group

router = APIRouter(prefix="/grades", tags=["grades"])

def user_has_role(db: Session, user_id: int, role_name: str) -> bool:
    """Проверка роли пользователя."""
    q = (
        select(Role)
        .join(user_roles, Role.id == user_roles.c.role_id)
        .where(user_roles.c.user_id == user_id, Role.name == role_name)
    )
    return db.scalar(q) is not None

@router.post("/{grade_id}", response_model=GradeOut, dependencies=[Depends(require_permission("grades:update"))])
def update_grade(
    grade_id: int,
    payload: GradeUpdate,
    db: Session = Depends(get_db),
    me = Depends(get_current_user),
):
    grade = db.get(Grade, grade_id)
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")

    is_admin_user = is_admin(me, db)
    is_director = user_has_role(db, me.id, "director")
    is_teacher = user_has_role(db, me.id, "teacher")

    if is_teacher and not (is_admin_user or is_director):
        teacher_profile = db.scalar(select(Teacher).where(Teacher.user_id == me.id))
        if not teacher_profile:
            raise HTTPException(status_code=403, detail="Teacher profile not found")

        if grade.teacher_id != teacher_profile.id:
            lesson = db.get(Lesson, grade.lesson_id)
            if not lesson or teacher_profile not in lesson.teachers:
                raise HTTPException(status_code=403, detail="Cannot edit grade of another teacher")


        if payload.value not in GradeTypeFinal and payload.value is not None:
            raise HTTPException(status_code=400, detail="Недопустимая оценка")

        if any([payload.subject_id is not None, payload.lesson_id is not None, payload.teacher_id is not None]):
            raise HTTPException(status_code=403, detail="Teacher cannot change subject/lesson/teacher fields")

        if payload.grade_type is not None:
            grade.grade_type = payload.grade_type
        if payload.value is not None:
            grade.value = payload.value
        if payload.comment is not None:
            grade.comment = payload.comment
        if payload.graded_at is not None:
            grade.graded_at = payload.graded_at

    else:
        if payload.teacher_id is not None:
            grade.teacher_id = payload.teacher_id

        if payload.subject_id is not None:
            grade.subject_id = payload.subject_id

        if payload.lesson_id is not None:
            lesson = db.get(Lesson, payload.lesson_id)
            if not lesson:
                raise HTTPException(status_code=400, detail="Lesson not found")
            student = db.get(Student, grade.student_id)
            if student and student.group_id != lesson.group_id:
                raise HTTPException(status_code=400, detail="Student is not in the new lesson's group")
            grade.lesson_id = payload.lesson_id

        if payload.grade_type is not None:
            grade.grade_type = payload.grade_type
        if payload.value is not None:
            grade.value = payload.value
        if payload.comment is not None:
            grade.comment = payload.comment
        if payload.graded_at is not None:
            grade.graded_at = payload.graded_at

    db.commit()
    db.refresh(grade)

    return GradeOut(
        id=grade.id,
        student_id=grade.student_id,
        subject_id=grade.subject_id,
        teacher_id=grade.teacher_id,
        lesson_id=grade.lesson_id,
        grade_type=grade.grade_type,
        value=grade.value,
        graded_at=grade.graded_at,
        comment=grade.comment,
    )

@router.post("", response_model=GradeOut, dependencies=[Depends(require_permission("grades:create"))])
def create_grade(payload: GradeCreate, db: Session = Depends(get_db), me=Depends(get_current_user)):
    student = db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(status_code=400, detail="Student not found")

    lesson = db.get(Lesson, payload.lesson_id)
    if not lesson:
        raise HTTPException(status_code=400, detail="Lesson not found")

    if payload.value not in GradeType:
        raise HTTPException(status_code=400, detail="Недопустимая оценка")

    if student.group_id != lesson.group_id:
        raise HTTPException(status_code=400, detail="Student is not in the lesson's group")

    subj_id = lesson.subject_id
    teacher_profile = db.scalar(select(Teacher).where(Teacher.user_id == me.id))

    is_admin_user = is_admin(me, db)
    is_director_user = user_has_role(db, me.id, "director")
    is_teacher_user = user_has_role(db, me.id, "teacher")

    final_teacher_id = None
    modified_by_admin_id = None

    if payload.grade_type and payload.grade_type.lower() in ["итог", "final", "exam", "зачет"]:
        existing_final = db.scalar(
            select(Grade).where(
                Grade.student_id == student.id,
                Grade.subject_id == subj_id,
                Grade.grade_type.in_(["итог", "final", "exam", "зачет"])
            )
        )
        if existing_final:
            raise HTTPException(status_code=400, detail="Final grade already exists for this subject and student")

    if is_teacher_user and not (is_admin_user or is_director_user):
        if not teacher_profile:
            raise HTTPException(status_code=403, detail="Teacher profile not found")
        if payload.teacher_id != teacher_profile.id:
            raise HTTPException(status_code=403, detail="Teacher can grade only as self")
        if teacher_profile not in lesson.teachers and lesson.teacher_id != teacher_profile.id:
            raise HTTPException(status_code=403, detail="Teacher is not assigned to this lesson")
        is_linked = db.scalar(
            select(teacher_subjects).where(
                teacher_subjects.c.teacher_id == teacher_profile.id,
                teacher_subjects.c.subject_id == subj_id
            )
        )
        if not is_linked and lesson.teacher_id != teacher_profile.id:
            raise HTTPException(status_code=403, detail="Teacher is not assigned to this subject")

        final_teacher_id = teacher_profile.id

    else:
        if payload.teacher_id:
            final_teacher_id = payload.teacher_id
        else:
            final_teacher_id = None
            modified_by_admin_id = me.id

    grade = Grade(
        student_id=student.id,
        subject_id=subj_id,
        teacher_id=final_teacher_id,
        lesson_id=lesson.id,
        grade_type=payload.grade_type,
        value=payload.value,
        graded_at=payload.graded_at or datetime.utcnow(),
        comment=payload.comment,
        modified_by_admin_id=modified_by_admin_id
    )
    db.add(grade)
    db.commit()
    db.refresh(grade)

    return GradeOut(
        id=grade.id,
        student_id=grade.student_id,
        subject_id=grade.subject_id,
        teacher_id=grade.teacher_id,
        lesson_id=grade.lesson_id,
        grade_type=grade.grade_type,
        value=grade.value,
        graded_at=grade.graded_at,
        comment=grade.comment,
        modified_by_admin_id=grade.modified_by_admin_id
    )

@router.get("", response_model=list[GradeOut], dependencies=[Depends(require_permission("grades:read"))])
def list_grades(
    db: Session = Depends(get_db),
    me=Depends(get_current_user),
    grade_type: str | None = None
):
    q = select(Grade)
    if grade_type:
        q = q.where(Grade.grade_type.ilike(f"%{grade_type}%"))
    if user_has_role(db, me.id, "teacher") and not (is_admin(me, db) or user_has_role(db, me.id, "director")):
        teacher_profile = db.scalar(select(Teacher).where(Teacher.user_id == me.id))
        if not teacher_profile:
            raise HTTPException(status_code=403, detail="Teacher profile not found")
        q = q.where(Grade.teacher_id == teacher_profile.id)

    grades = db.scalars(q).all()
    return [
        GradeOut(
            id=g.id,
            student_id=g.student_id,
            subject_id=g.subject_id,
            teacher_id=g.teacher_id,
            lesson_id=g.lesson_id,
            grade_type=g.grade_type,
            value=g.value,
            graded_at=g.graded_at,
            comment=g.comment
        )
        for g in grades
    ]

@router.post(
    "/final",
    response_model=GradeOut,
    dependencies=[Depends(require_permission("grades:create"))],
)
def create_or_update_final_grade(
    payload: FinalGradeIn,
    db: Session = Depends(get_db),
    me=Depends(get_current_user),
):
    """
    Создаёт или обновляет итоговую оценку по предмету.
    Админ, директор или преподаватель (ведущий предмет) могут вызвать.
    """
    student = db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    subject = db.get(Subject, payload.subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    if payload.value not in GradeTypeFinal:
        raise HTTPException(status_code=400, detail="Недопустимая оценка")

    teacher_profile = db.scalar(select(Teacher).where(Teacher.user_id == me.id))
    is_admin_user = is_admin(me, db)
    is_director = db.scalar(
        select(Role)
        .join(user_roles, Role.id == user_roles.c.role_id)
        .where(user_roles.c.user_id == me.id, Role.name == "director")
    )

    if not (is_admin_user or is_director or teacher_profile):
        raise HTTPException(status_code=403, detail="Access denied")

    if teacher_profile and not (is_admin_user or is_director):
        is_linked = db.scalar(
            select(teacher_subjects).where(
                teacher_subjects.c.teacher_id == teacher_profile.id,
                teacher_subjects.c.subject_id == payload.subject_id
            )
        )
        if not is_linked:
            raise HTTPException(status_code=403, detail="Teacher not linked to this subject")

    existing_final = db.scalar(
        select(Grade).where(
            Grade.student_id == payload.student_id,
            Grade.subject_id == payload.subject_id,
            Grade.grade_type.in_(["итог", "final", "exam", "зачет"])
        )
    )

    if existing_final:
        existing_final.value = payload.value
        existing_final.comment = payload.comment
        existing_final.graded_at = datetime.utcnow()
        db.commit()
        db.refresh(existing_final)
        return GradeOut(
            id=existing_final.id,
            student_id=existing_final.student_id,
            subject_id=existing_final.subject_id,
            teacher_id=existing_final.teacher_id,
            lesson_id=existing_final.lesson_id,
            grade_type=existing_final.grade_type,
            value=existing_final.value,
            graded_at=existing_final.graded_at,
            comment=existing_final.comment,
            modified_by_admin_id=existing_final.modified_by_admin_id,
        )

    final_grade = Grade(
        student_id=payload.student_id,
        subject_id=payload.subject_id,
        teacher_id=teacher_profile.id if teacher_profile else None,
        lesson_id=None,
        grade_type="final",
        value=payload.value,
        graded_at=datetime.utcnow(),
        comment=payload.comment,
        modified_by_admin_id=me.id if (is_admin_user or is_director) else None,
    )

    db.add(final_grade)
    db.commit()
    db.refresh(final_grade)

    return GradeOut(
        id=final_grade.id,
        student_id=final_grade.student_id,
        subject_id=final_grade.subject_id,
        teacher_id=final_grade.teacher_id,
        lesson_id=final_grade.lesson_id,
        grade_type=final_grade.grade_type,
        value=final_grade.value,
        graded_at=final_grade.graded_at,
        comment=final_grade.comment,
        modified_by_admin_id=final_grade.modified_by_admin_id,
    )

@router.post(
    "/final/{student_id}/{subject_id}",
    response_model=GradeOut,
    dependencies=[Depends(require_permission("grades:update"))],
)
def patch_final_grade(
    student_id: int,
    subject_id: int,
    payload: FinalGradePatch,
    db: Session = Depends(get_db),
    me=Depends(get_current_user),
):
    """
    Обновляет итоговую оценку (value, comment).
    Доступно админу, директору и преподавателю (если он связан с предметом).
    """
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    if payload.value not in GradeTypeFinal and payload.value is not None:
        raise HTTPException(status_code=400, detail="Недопустимая оценка")

    teacher_profile = db.scalar(select(Teacher).where(Teacher.user_id == me.id))
    is_admin_user = is_admin(me, db)
    is_director = db.scalar(
        select(Role)
        .join(user_roles, Role.id == user_roles.c.role_id)
        .where(user_roles.c.user_id == me.id, Role.name == "director")
    )

    if not (is_admin_user or is_director or teacher_profile):
        raise HTTPException(status_code=403, detail="Access denied")

    if teacher_profile and not (is_admin_user or is_director):
        is_linked = db.scalar(
            select(teacher_subjects).where(
                teacher_subjects.c.teacher_id == teacher_profile.id,
                teacher_subjects.c.subject_id == subject_id,
            )
        )
        if not is_linked:
            raise HTTPException(status_code=403, detail="Teacher not linked to this subject")

    final_grade = db.scalar(
        select(Grade).where(
            Grade.student_id == student_id,
            Grade.subject_id == subject_id,
            Grade.grade_type.in_(["итог", "final", "exam", "зачет"])
        )
    )

    if not final_grade:
        raise HTTPException(status_code=404, detail="Final grade not found")

    if payload.value is not None:
        final_grade.value = payload.value
    if payload.comment is not None:
        final_grade.comment = payload.comment

    final_grade.graded_at = datetime.utcnow()
    if is_admin_user or is_director:
        final_grade.modified_by_admin_id = me.id

    db.commit()
    db.refresh(final_grade)

    return GradeOut(
        id=final_grade.id,
        student_id=final_grade.student_id,
        subject_id=final_grade.subject_id,
        teacher_id=final_grade.teacher_id,
        lesson_id=final_grade.lesson_id,
        grade_type=final_grade.grade_type,
        value=final_grade.value,
        graded_at=final_grade.graded_at,
        comment=final_grade.comment,
        modified_by_admin_id=final_grade.modified_by_admin_id,
    )

@router.get("/export", dependencies=[Depends(require_permission("grades:read"))])
def export_grades_excel(
    db: Session = Depends(get_db),
    from_date: datetime | None = Query(None, description="Начало периода (включительно)"),
    to_date: datetime | None = Query(None, description="Конец периода (включительно)"),
    teacher_id: int | None = Query(None, description="ID преподавателя"),
    subject_id: int | None = Query(None, description="ID предмета"),
    grade_type: str | None = Query(None, description="Тип оценки (например 'итог', 'текущая')"),
):
    """
    📘 Выгрузка ведомостей по всем предметам в Excel.
    Фильтры: по дате, предмету, преподавателю, типу оценки.
    Каждый лист — отдельная группа.
    """
    groups = db.scalars(select(Group)).all()
    if not groups:
        raise HTTPException(status_code=404, detail="No groups found")

    wb = Workbook()
    wb.remove(wb.active)

    for group in groups:
        ws = wb.create_sheet(title=f"{group.code or group.name}")
        ws.append([
            "№", "ФИО студента", "Предмет", "Тип оценки",
            "Оценка", "Комментарий", "Преподаватель", "Дата выставления"
        ])

        students = db.scalars(select(Student).where(Student.group_id == group.id)).all()
        row_num = 1

        for student in students:
            q = select(Grade).join(Subject, Subject.id == Grade.subject_id)
            q = q.where(Grade.student_id == student.id)

            if from_date:
                q = q.where(Grade.graded_at >= from_date)
            if to_date:
                q = q.where(Grade.graded_at <= to_date)
            if teacher_id:
                q = q.where(Grade.teacher_id == teacher_id)
            if subject_id:
                q = q.where(Grade.subject_id == subject_id)
            if grade_type:
                q = q.where(Grade.grade_type.ilike(f"%{grade_type}%"))

            grades = db.scalars(q).all()
            if not grades:
                continue

            student_user = db.get(User, student.user_id)
            student_name = student_user.full_name or "—"

            for g in grades:
                teacher_name = ""
                if g.teacher_id:
                    teacher = db.get(Teacher, g.teacher_id)
                    if teacher and teacher.full_name:
                        teacher_name = teacher.full_name
                    elif teacher and teacher.user_id:
                        u = db.get(User, teacher.user_id)
                        teacher_name = u.full_name or ""

                ws.append([
                    row_num,
                    student_name,
                    g.subject.title if g.subject else "",
                    "Итоговая" if g.grade_type == "final" else"",
                    g.value,
                    g.comment or "",
                    teacher_name,
                    g.graded_at.strftime("%d.%m.%Y %H:%M") if g.graded_at else "",
                ])
                row_num += 1

        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = max_len + 2

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    filename = f"vedomost_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"

    return Response(
        content=stream.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
