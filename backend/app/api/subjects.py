from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Profile, Subject, ClassOccurrence, Attendance
from app.schemas.schemas import (
    SubjectCreate, SubjectUpdate, SubjectResponse, SubjectDetailResponse, ClassOccurrenceResponse
)
from app.services.attendance_service import AttendanceService

router = APIRouter(prefix="/subjects", tags=["Subjects"])


@router.get("/", response_model=List[SubjectDetailResponse])
async def get_subjects(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Subject).filter(Subject.user_id == current_user.id).order_by(Subject.name.asc())
    result = await db.execute(stmt)
    subjects = result.scalars().all()

    enriched: List[SubjectDetailResponse] = []
    target_pct = current_user.target_attendance_percentage or 75.0

    for s in subjects:
        summary = await AttendanceService.get_subject_attendance_summary(
            db, current_user.id, s, s.target_attendance or target_pct
        )
        enriched.append(SubjectDetailResponse(
            id=s.id,
            user_id=s.user_id,
            name=s.name,
            code=s.code or "",
            color=s.color or "#0D9488",
            target_attendance=s.target_attendance,
            faculty=s.faculty or "",
            academic_year=s.academic_year or "",
            created_at=s.created_at,
            classes_conducted=summary.classes_conducted,
            classes_attended=summary.classes_attended,
            classes_missed=summary.classes_missed,
            classes_cancelled=summary.classes_cancelled,
            current_percentage=summary.current_percentage,
            is_below_target=summary.is_below_target,
            classes_needed_for_target=summary.classes_needed_for_target,
            bunk_buffer=summary.bunk_buffer
        ))
    return enriched


@router.post("/", response_model=SubjectResponse)
async def create_subject(
    data: SubjectCreate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    subject = Subject(
        user_id=current_user.id,
        name=data.name,
        code=data.code or "",
        color=data.color or "#0D9488",
        target_attendance=data.target_attendance or current_user.target_attendance_percentage,
        faculty=data.faculty or "",
        academic_year=data.academic_year or ""
    )
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    return subject


@router.put("/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: str,
    data: SubjectUpdate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Subject).filter(Subject.id == subject_id, Subject.user_id == current_user.id)
    subject = (await db.execute(stmt)).scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    if data.name is not None:
        subject.name = data.name
    if data.code is not None:
        subject.code = data.code
    if data.color is not None:
        subject.color = data.color
    if data.target_attendance is not None:
        subject.target_attendance = data.target_attendance
    if data.faculty is not None:
        subject.faculty = data.faculty
    if data.academic_year is not None:
        subject.academic_year = data.academic_year

    await db.commit()
    await db.refresh(subject)
    return subject


@router.delete("/{subject_id}")
async def delete_subject(
    subject_id: str,
    force: bool = Query(False, description="Set to true to force delete subject and associated attendance records"),
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Subject).filter(Subject.id == subject_id, Subject.user_id == current_user.id)
    subject = (await db.execute(stmt)).scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Check if this subject has existing attendance records
    att_stmt = (
        select(Attendance)
        .join(ClassOccurrence, Attendance.occurrence_id == ClassOccurrence.id)
        .filter(ClassOccurrence.subject_id == subject_id, ClassOccurrence.user_id == current_user.id)
    )
    records = (await db.execute(att_stmt)).scalars().all()
    marked_records = [r for r in records if r.status in ["present", "absent"]]

    if marked_records and not force:
        raise HTTPException(
            status_code=409,
            detail=f"Subject '{subject.name}' has {len(marked_records)} attendance records. Deleting it will permanently remove these records. Confirm to proceed."
        )

    await db.delete(subject)
    await db.commit()
    return {"message": f"Subject '{subject.name}' deleted successfully", "records_removed": len(records)}


@router.get("/{subject_id}/history", response_model=List[ClassOccurrenceResponse])
async def get_subject_attendance_history(
    subject_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify subject belongs to user
    s_stmt = select(Subject).filter(Subject.id == subject_id, Subject.user_id == current_user.id)
    subject = (await db.execute(s_stmt)).scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    history = await AttendanceService.get_attendance_history(db, current_user.id, subject_id=subject_id)
    return history
