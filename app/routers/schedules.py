from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, or_, distinct
from datetime import datetime

from app.core.deps import get_db, get_current_user, require_permission, is_admin
from app.models.schedule import Lesson, Group, Teacher, Subject, Room
from app.models.grade import Student as StudentModel, Grade
from app.models.user import User
from app.schemas.schedule import LessonCreate, LessonOut
from app.models.role import Role, user_roles
from app.schemas.schedule import LessonUpdate

router = APIRouter(prefix="/schedules", tags=["schedules"])

def get_or_create(db, model, where: dict, defaults: dict = {}):
    inst = db.scalar(select(model).filter_by(**where))
    if inst:
        return inst
    inst = model(**where, **defaults)
    db.add(inst); db.flush()
    return inst

def user_has_role(db: Session, user_id: int, role_name: str) -> bool:
    """Проверка роли пользователя."""
    q = (
        select(Role)
        .join(user_roles, Role.id == user_roles.c.role_id)
        .where(user_roles.c.user_id == user_id, Role.name == role_name)
    )
    return db.scalar(q) is not None

@router.post("/lessons", dependencies=[Depends(require_permission("schedules:create"))])
def create_lesson(payload: LessonCreate, db: Session = Depends(get_db), me=Depends(get_current_user)):
    group = get_or_create(db, Group, {"code": payload.group_code}, {"title": payload.group_code})

    if payload.subject_id is not None:
        subject = db.get(Subject, payload.subject_id)
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")
    else:
        subject = get_or_create(db, Subject, {"title": payload.subject_title})

    if payload.teacher_id is not None:
        teacher = db.get(Teacher, payload.teacher_id)
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")
    else:
        teacher = get_or_create(
            db, Teacher,
            {"full_name": payload.teacher_full_name},
            {"email": payload.teacher_email, "phone": payload.teacher_phone, "subject": payload.teacher_subject}
        )

    if subject.primary_teacher_id and subject.primary_teacher_id != teacher.id:
        raise HTTPException(status_code=400, detail="Lesson teacher must match subject's primary teacher")

    room = get_or_create(db, Room, {"code": payload.room_code}, {"title": payload.room_code})

    lesson = Lesson(
        group_id=group.id, subject_id=subject.id, teacher_id=teacher.id, room_id=room.id,
        starts_at=payload.starts_at, ends_at=payload.ends_at,
        lesson_type=payload.lesson_type, notes=payload.notes, created_by=me.id
    )
    db.add(lesson); db.commit()
    return {"id": lesson.id}

@router.post(
    "/lessons/{lesson_id}",
    dependencies=[Depends(require_permission("schedules:update"))]
)
def update_lesson(
    lesson_id: int,
    payload: LessonUpdate,
    db: Session = Depends(get_db),
    me=Depends(get_current_user),
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    if payload.group_code:
        group = get_or_create(db, Group, {"code": payload.group_code}, {"title": payload.group_code})
        lesson.group_id = group.id

    if payload.subject_id is not None:
        subject = db.get(Subject, payload.subject_id)
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")
        lesson.subject_id = subject.id
    elif payload.subject_title:
        subject = get_or_create(db, Subject, {"title": payload.subject_title})
        lesson.subject_id = subject.id

    if payload.teacher_id is not None:
        teacher = db.get(Teacher, payload.teacher_id)
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")
    elif payload.teacher_full_name:
        teacher = get_or_create(
            db, Teacher,
            {"full_name": payload.teacher_full_name},
            {"email": payload.teacher_email, "phone": payload.teacher_phone, "subject": payload.teacher_subject}
        )
    else:
        teacher = None

    if teacher:
        subject = db.get(Subject, lesson.subject_id)
        if subject and subject.primary_teacher_id and subject.primary_teacher_id != teacher.id:
            raise HTTPException(status_code=400, detail="Lesson teacher must match subject's primary teacher")
        lesson.teacher_id = teacher.id

    if payload.room_code:
        room = get_or_create(db, Room, {"code": payload.room_code}, {"title": payload.room_code})
        lesson.room_id = room.id

    if payload.starts_at is not None:
        lesson.starts_at = payload.starts_at
    if payload.ends_at is not None:
        lesson.ends_at = payload.ends_at
    if payload.lesson_type is not None:
        lesson.lesson_type = payload.lesson_type
    if payload.notes is not None:
        lesson.notes = payload.notes
    if payload.lesson_number is not None:
        lesson.lesson_number = payload.lesson_number

    db.commit()
    db.refresh(lesson)
    return {"id": lesson.id, "updated": True}

@router.get("/teachers/{teacher_id}/teaching", dependencies=[Depends(require_permission("schedules:read"))])
def teacher_teaching_overview(
    teacher_id: int,
    db: Session = Depends(get_db),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
):
    teacher = db.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    groups_stmt = (
        select(distinct(Group.id), Group.code, Group.title)
        .join(Lesson, Lesson.group_id == Group.id)
        .where(Lesson.teacher_id == teacher_id)
    )
    if date_from:
        groups_stmt = groups_stmt.where(Lesson.starts_at >= date_from)
    if date_to:
        groups_stmt = groups_stmt.where(Lesson.starts_at < date_to)
    groups_rows = db.execute(groups_stmt).all()
    groups = [{"id": gid, "code": gcode, "title": gtitle} for gid, gcode, gtitle in groups_rows]
    group_ids = [g["id"] for g in groups] or [-1]

    subj_stmt = (
        select(distinct(Group.id), Subject.id, Subject.title, Subject.code)
        .join(Lesson, Lesson.group_id == Group.id)
        .join(Subject, Subject.id == Lesson.subject_id)
        .where(Lesson.teacher_id == teacher_id, Lesson.group_id.in_(group_ids))
    )
    if date_from:
        subj_stmt = subj_stmt.where(Lesson.starts_at >= date_from)
    if date_to:
        subj_stmt = subj_stmt.where(Lesson.starts_at < date_to)
    subj_rows = db.execute(subj_stmt).all()
    subjects_by_group = {}
    for gid, sid, stitle, scode in subj_rows:
        subjects_by_group.setdefault(gid, []).append({"id": sid, "title": stitle, "code": scode})

    lesson_stmt = (
        select(Lesson)
        .where(Lesson.teacher_id == teacher_id, Lesson.group_id.in_(group_ids))
        .order_by(Lesson.starts_at)
    )
    if date_from:
        lesson_stmt = lesson_stmt.where(Lesson.starts_at >= date_from)
    if date_to:
        lesson_stmt = lesson_stmt.where(Lesson.starts_at < date_to)
    lessons = db.scalars(lesson_stmt).all()

    final_grades_stmt = (
        select(
            Grade.student_id,
            Grade.subject_id,
            Grade.value,
            StudentModel.group_id,
            User.full_name,
            Subject.title.label("subject_title"),
            Subject.code.label("subject_code"),
            Group.code.label("group_code"),
        )
        .join(StudentModel, StudentModel.id == Grade.student_id)
        .join(User, User.id == StudentModel.user_id)
        .join(Subject, Subject.id == Grade.subject_id)
        .join(Group, Group.id == StudentModel.group_id)
        .where(
            Grade.teacher_id == teacher_id,
            Grade.grade_type.in_(["итог", "final", "exam", "зачет"]),
            StudentModel.group_id.in_(group_ids)
        )
    )
    final_grades_rows = db.execute(final_grades_stmt).all()

    final_grades_by_group = {}
    for row in final_grades_rows:
        gid = row.group_id
        sid = row.subject_id
        final_grades_by_group.setdefault(gid, {}).setdefault(sid, []).append({
            "student_id": row.student_id,
            "student_name": row.full_name,
            "value": row.value,
            "subject_title": row.subject_title,
            "subject_code": row.subject_code,
            "group_code": row.group_code,
        })

    return {
        "teacher_id": teacher.id,
        "teacher_full_name": teacher.full_name,
        "groups": groups,
        "subjectsByGroup": [
            {
                "group": next((g for g in groups if g["id"] == gid), {"id": gid}),
                "subjects": subjects_by_group.get(gid, [])
            }
            for gid in group_ids if gid != -1
        ],
        "lessons": [
            {
                "id": l.id,
                "group_id": l.group_id,
                "group_code": l.group.code if l.group else None,
                "subject_id": l.subject_id,
                "subject_title": l.subject.title if l.subject else None,
                "room": l.room.code if l.room else None,
                "starts_at": l.starts_at,
                "ends_at": l.ends_at,
                "lesson_type": l.lesson_type,
                "notes":l.notes,
            } for l in lessons
        ],
        "final_grades": [
            {
                "group_id": gid,
                "group_code": next((g["code"] for g in groups if g["id"] == gid), None),
                "subjects": [
                    {
                        "subject_id": sid,
                        "subject_title": next(
                            (s["title"] for s in subjects_by_group.get(gid, []) if s["id"] == sid),
                            None
                        ),
                        "students": final_grades_by_group[gid][sid],
                    }
                    for sid in final_grades_by_group[gid]
                ],
            }
            for gid in final_grades_by_group
        ],
    }

@router.get("/lessons", response_model=list[LessonOut], dependencies=[Depends(require_permission("schedules:read"))])
def list_lessons(
    db: Session = Depends(get_db),
    group_code: str | None = None,
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    teacher_full_name: str | None = Query(None, description="ФИО преподавателя (подстрочный поиск)"),
    subject_title: str | None = Query(None, description="Название предмета (подстрочный поиск)"),
    room_code: str | None = Query(None, description="Код аудитории"),
    lesson_type: str | None = Query(None, description="лекция/практика/лабораторная и т.п."),
):
    q = (
        select(Lesson)
        .join(Group, Lesson.group_id == Group.id)
        .join(Subject, Lesson.subject_id == Subject.id)
        .outerjoin(Teacher, Lesson.teacher_id == Teacher.id)
        .outerjoin(Room, Lesson.room_id == Room.id)
    )
    if group_code:
        q = q.where(Group.code == group_code)
    if date_from:
        q = q.where(Lesson.starts_at >= date_from)
    if date_to:
        q = q.where(Lesson.starts_at < date_to)
    if teacher_full_name:
        q = q.where(Teacher.full_name.ilike(f"%{teacher_full_name}%"))
    if subject_title:
        q = q.where(Subject.title.ilike(f"%{subject_title}%"))
    if room_code:
        q = q.where(Room.code == room_code)
    if lesson_type:
        q = q.where(Lesson.lesson_type == lesson_type)

    rows = db.scalars(q).all()

    return [
        LessonOut(
            id=l.id,
            group=l.group.code if l.group else None,
            subject=l.subject.title if l.subject else None,
            teacher=l.teacher.full_name if l.teacher else None,
            room=l.room.code if l.room else None,
            starts_at=l.starts_at,
            ends_at=l.ends_at,
            lesson_type=l.lesson_type,
            notes=l.notes,
            lesson_number=l.lesson_number,
        )
        for l in rows
    ]

@router.get("/lookup/groups")
def lookup_groups(db: Session = Depends(get_db), q: str | None = Query(None)):
    stmt = select(Group)
    if q:
        stmt = stmt.where(or_(Group.code.ilike(f"%{q}%"), Group.title.ilike(f"%{q}%")))
    rows = db.scalars(stmt).all()
    return [{"id": g.id, "code": g.code, "title": g.title} for g in rows]

@router.get("/lookup/teachers")
def lookup_teachers(db: Session = Depends(get_db), q: str | None = Query(None), subdivision_id: int | None = Query(None)):
    stmt = select(Teacher)
    if q:
        stmt = stmt.where(or_(Teacher.full_name.ilike(f"%{q}%"), Teacher.email.ilike(f"%{q}%")))
    if subdivision_id:
        stmt = stmt.where(Teacher.subdivision_id == subdivision_id)
    rows = db.scalars(stmt).all()
    return [
        {"id": t.id, "full_name": t.full_name, "email": t.email, "phone": t.phone, "subject": t.subject,
         "subdivision_id": t.subdivision_id}
        for t in rows
    ]

@router.get(
    "/lessons/{lesson_id}/students",
    dependencies=[Depends(require_permission("schedules:read"))],
)
def get_students_for_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    if not (
        is_admin(me, db)
        or user_has_role(db, me.id, "director")
        or user_has_role(db, me.id, "teacher")
    ):
        raise HTTPException(status_code=403, detail="Not allowed")

    students = (
        db.query(StudentModel)
        .join(User, User.id == StudentModel.user_id)
        .filter(StudentModel.group_id == lesson.group_id)
        .all()
    )

    result = []
    for s in students:
        grades = (
            db.query(Grade)
            .filter(Grade.student_id == s.id, Grade.lesson_id == lesson.id)
            .all()
        )

        final_grade = db.scalar(
            select(Grade.value)
            .where(
                Grade.student_id == s.id,
                Grade.subject_id == lesson.subject_id,
                Grade.grade_type.in_(["итог", "final", "exam", "зачет"]),
            )
            .limit(1)
        )

        result.append(
            {
                "id": s.user.id,
                "full_name": s.user.full_name,
                "email": s.user.email,
                "phone": s.user.phone,
                "record_book": s.record_book,
                "course": s.course,
                "insert_year": s.insert_year,
                "student_id": s.id,
                "final_grade": final_grade,
                "grades": [
                    {
                        "id": g.id,
                        "subject_id": g.subject_id,
                        "teacher_id": g.teacher_id,
                        "lesson_id": g.lesson_id,
                        "grade_type": g.grade_type,
                        "value": g.value,
                        "graded_at": g.graded_at,
                        "comment": g.comment,
                    }
                    for g in grades
                ],
            }
        )

    return {
        "lesson_id": lesson.id,
        "group_id": lesson.group_id,
        "group_code": lesson.group.code if lesson.group else None,
        "subject_id": lesson.subject_id,
        "subject_title": lesson.subject.title if lesson.subject else None,
        "students": result,
    }


@router.get("/lookup/rooms")
def lookup_rooms(db: Session = Depends(get_db), q: str | None = Query(None)):
    stmt = select(Room)
    if q:
        stmt = stmt.where(or_(Room.code.ilike(f"%{q}%"), Room.title.ilike(f"%{q}%")))
    rows = db.scalars(stmt).all()
    return [{"id": r.id, "code": r.code, "title": r.title, "capacity": r.capacity} for r in rows]

@router.get("/lookup/subjects")
def lookup_subjects(db: Session = Depends(get_db), q: str | None = Query(None)):
    stmt = select(Subject)
    if q:
        stmt = stmt.where(or_(Subject.title.ilike(f"%{q}%"), Subject.code.ilike(f"%{q}%")))
    rows = db.scalars(stmt).all()
    return [{"id": s.id, "title": s.title, "code": s.code} for s in rows]

@router.get("/groups/{group_identifier}")
def get_group(group_identifier: str, db: Session = Depends(get_db)):
    group = None
    if group_identifier.isdigit():
        group = db.get(Group, int(group_identifier))
    if not group:
        group = db.scalar(select(Group).where(Group.code == group_identifier))
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    students = (
        db.query(StudentModel)
        .join(User, User.id == StudentModel.user_id)
        .filter(StudentModel.group_id == group.id)
        .all()
    )

    return {
        "id": group.id,
        "code": group.code,
        "title": group.title,
        "students": [
            {
                "id": s.user.id,
                "full_name": s.user.full_name,
                "email": s.user.email,
                "phone": s.user.phone,
                "record_book": s.record_book,
                "course": s.course,
                "insert_year": s.insert_year,
                "student_id": s.id,
            }
            for s in students
        ],
    }
