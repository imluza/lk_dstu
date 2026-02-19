from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException
from app.models.schedule import Lesson, LessonTime, Group, Subject, Teacher, Room
from app.schemas.schedule import LessonCreate

def get_or_create(db, model, where: dict, defaults: dict = {}):
    inst = db.scalar(select(model).filter_by(**where))
    if inst:
        return inst
    inst = model(**where, **defaults)
    db.add(inst)
    db.flush()
    return inst

def create_lesson(db: Session, payload: LessonCreate):
    group = db.scalar(select(Group).where(Group.code == payload.group_code))
    if not group:
        raise HTTPException(status_code=404, detail=f"Группа {payload.group_code} не найдена")

    room = db.scalar(select(Room).where(Room.code == payload.room_code))
    if not room:
        raise HTTPException(status_code=404, detail=f"Аудитория {payload.room_code} не найдена")

    if payload.subject_id:
        subject_id = payload.subject_id
    else:
        subject = get_or_create(db, Subject, {"title": payload.subject_title})
        subject_id = subject.id

    if payload.teacher_id:
        teacher_id = payload.teacher_id
    elif payload.teacher_full_name:
        teacher = get_or_create(
            db,
            Teacher,
            {"full_name": payload.teacher_full_name},
            {
                "email": payload.teacher_email,
                "phone": payload.teacher_phone,
                "subject": payload.teacher_subject,
            },
        )
        teacher_id = teacher.id
    else:
        teacher_id = None

    if payload.lesson_number is not None:
        lt = db.scalar(select(LessonTime).where(LessonTime.lesson_number == payload.lesson_number))
        if not lt:
            raise HTTPException(status_code=400, detail=f"LessonTime {payload.lesson_number} не найден")
        starts_at = payload.starts_at.replace(hour=lt.start_time.hour, minute=lt.start_time.minute)
        ends_at = payload.ends_at.replace(hour=lt.end_time.hour, minute=lt.end_time.minute)
        lesson_number = payload.lesson_number
    else:
        lt = db.scalar(select(LessonTime).where(LessonTime.start_time == payload.starts_at.time()))
        if not lt:
            raise HTTPException(status_code=400, detail=f"Не найден номер пары для {payload.starts_at.time()}")
        lesson_number = lt.lesson_number
        starts_at = payload.starts_at
        ends_at = payload.ends_at

    lesson = Lesson(
        group_id=group.id,
        subject_id=subject_id,
        teacher_id=teacher_id,
        room_id=room.id,
        lesson_number=lesson_number,
        starts_at=starts_at,
        ends_at=ends_at,
        lesson_type=payload.lesson_type,
        notes=payload.notes,
        created_by=None,
    )

    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson
