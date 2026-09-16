from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Profile, Attendance, ClassOccurrence, Subject, ClassTopic
from app.schemas.schemas import (
    AttendanceMarkRequest, OverallAttendanceSummary, AttendanceResponse,
    ClassOccurrenceResponse, ManualAttendanceCreate, AttendanceCheckInRequest,
    AttendanceResetRequest, SemesterArchiveRequest, AttendanceHistoryUpdateRequest
)
from app.services.attendance_service import AttendanceService

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.get("/summary", response_model=OverallAttendanceSummary)
async def get_attendance_summary(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    summary = await AttendanceService.get_overall_attendance_summary(db, current_user.id)
    return summary


@router.get("/today", response_model=List[ClassOccurrenceResponse])
async def get_today_classes(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns today's classes with attendance statuses for one-click marking.
    """
    classes = await AttendanceService.get_today_classes(db, current_user.id)
    return classes


@router.get("/classes")
async def get_attendance_classes(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all ended classes from the timetable ready for attendance marking,
    plus classes scheduled for later today.
    """
    return await AttendanceService.get_attendance_classes(db, current_user.id)


@router.get("/history", response_model=List[ClassOccurrenceResponse])
async def get_attendance_history(
    subject_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    archive_status: Optional[str] = Query("all"),
    archive_label: Optional[str] = Query(None),
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns historical classes with attendance details, filterable by date, subject, and archive status.
    """
    return await AttendanceService.get_attendance_history(
        db, current_user.id,
        subject_id=subject_id,
        start_date=start_date,
        end_date=end_date,
        archive_status=archive_status,
        archive_label=archive_label
    )


@router.get("/pending-checkins", response_model=List[ClassOccurrenceResponse])
async def get_pending_checkins(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns past/ended classes that are unconfirmed and awaiting attendance check-in.
    """
    await AttendanceService.sync_timetable_occurrences(db, current_user.id)
    today = date.today()
    now_time = datetime.now().time()
    stmt = (
        select(ClassOccurrence)
        .options(
            selectinload(ClassOccurrence.attendance),
            selectinload(ClassOccurrence.topics),
            selectinload(ClassOccurrence.subject)
        )
        .filter(
            ClassOccurrence.user_id == current_user.id,
            ClassOccurrence.status != "cancelled",
            ClassOccurrence.date <= today
        )
        .order_by(ClassOccurrence.date.desc(), ClassOccurrence.start_time.desc())
    )
    occurrences = (await db.execute(stmt)).scalars().all()

    pending = []
    for occ in occurrences:
        # Exclude archived occurrences or archived attendance
        if getattr(occ, "is_archived", False) or (occ.attendance and getattr(occ.attendance, "is_archived", False)):
            continue
        if occ.status == "cancelled" or (occ.attendance and occ.attendance.status == "cancelled"):
            continue
        # Time gate: do not mark pending if class has not ended yet today!
        if occ.date == today and occ.end_time > now_time:
            continue
        if not occ.attendance or occ.attendance.status == "not_marked":
            pending.append(occ)

    return pending


@router.post("/mark", response_model=AttendanceResponse)
async def mark_attendance(
    req: AttendanceMarkRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    valid_statuses = ["present", "absent", "cancelled", "not_marked"]
    if req.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid attendance status '{req.status}'. Must be one of: {valid_statuses}"
        )

    # Verify occurrence belongs to user
    occ_stmt = select(ClassOccurrence).filter(
        ClassOccurrence.id == req.occurrence_id,
        ClassOccurrence.user_id == current_user.id
    )
    occ = (await db.execute(occ_stmt)).scalars().first()
    if not occ:
        raise HTTPException(status_code=404, detail="Class occurrence not found")

    # Reversible cancellation:
    # If marking as cancelled, set occurrence status to cancelled
    # If restoring to present/absent/not_marked, restore occurrence status
    if req.status == "cancelled":
        occ.status = "cancelled"
    elif occ.status == "cancelled":
        occ.status = "completed" if req.status in ["present", "absent"] else "scheduled"

    # Find or create attendance record (ensures zero duplicate records)
    att_stmt = select(Attendance).filter(
        Attendance.occurrence_id == req.occurrence_id,
        Attendance.user_id == current_user.id
    )
    att = (await db.execute(att_stmt)).scalars().first()

    now = datetime.utcnow()
    if not att:
        att = Attendance(
            user_id=current_user.id,
            occurrence_id=req.occurrence_id,
            status=req.status,
            marked_at=now if req.status in ["present", "absent", "cancelled"] else None,
            notes=req.notes or ""
        )
        db.add(att)
    else:
        att.status = req.status
        att.marked_at = now if req.status in ["present", "absent", "cancelled"] else None
        if req.notes is not None:
            att.notes = req.notes

    await db.commit()
    await db.refresh(att)
    return att


@router.post("/check-in", response_model=ClassOccurrenceResponse)
async def check_in_class(
    req: AttendanceCheckInRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Atomic check-in for a completed class: marks attendance (present/absent/cancelled)
    and attaches topics covered and notes in a single request.
    """
    valid_statuses = ["present", "absent", "cancelled", "not_marked"]
    if req.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid attendance status '{req.status}'. Must be one of: {valid_statuses}"
        )

    occ_stmt = (
        select(ClassOccurrence)
        .options(
            selectinload(ClassOccurrence.attendance),
            selectinload(ClassOccurrence.topics),
            selectinload(ClassOccurrence.subject)
        )
        .filter(ClassOccurrence.id == req.occurrence_id, ClassOccurrence.user_id == current_user.id)
    )
    occ = (await db.execute(occ_stmt)).scalars().first()
    if not occ:
        raise HTTPException(status_code=404, detail="Class occurrence not found")

    # Update occurrence status
    if req.status == "cancelled":
        occ.status = "cancelled"
    elif req.status in ["present", "absent"]:
        occ.status = "completed"
    else:
        occ.status = "scheduled"

    # Update or create Attendance
    now = datetime.utcnow()
    att_stmt = select(Attendance).filter(
        Attendance.occurrence_id == req.occurrence_id,
        Attendance.user_id == current_user.id
    )
    att = (await db.execute(att_stmt)).scalars().first()
    if not att:
        att = Attendance(
            user_id=current_user.id,
            occurrence_id=req.occurrence_id,
            status=req.status,
            marked_at=now if req.status in ["present", "absent", "cancelled"] else None,
            notes=req.notes or ""
        )
        db.add(att)
    else:
        att.status = req.status
        att.marked_at = now if req.status in ["present", "absent", "cancelled"] else None
        if req.notes is not None:
            att.notes = req.notes

    # Add ClassTopic(s) if provided
    if req.topic_title and req.topic_title.strip():
        raw_title = req.topic_title.strip()
        delimiter = "\n" if "\n" in raw_title else ("," if "," in raw_title else None)
        parts = [p.strip() for p in raw_title.split(delimiter) if p.strip()] if delimiter else [raw_title]
        existing_topics = [t.title.lower() for t in (occ.topics or [])]
        if occ.topics is None:
            occ.topics = []
        for part in parts:
            if part.lower() not in existing_topics:
                topic = ClassTopic(
                    occurrence_id=occ.id,
                    title=part,
                    description=req.notes or "",
                    order_index=len(occ.topics)
                )
                db.add(topic)
                occ.topics.append(topic)
                existing_topics.append(part.lower())

    await db.commit()

    refreshed_stmt = (
        select(ClassOccurrence)
        .options(
            selectinload(ClassOccurrence.attendance),
            selectinload(ClassOccurrence.topics),
            selectinload(ClassOccurrence.subject)
        )
        .filter(ClassOccurrence.id == req.occurrence_id)
    )
    return (await db.execute(refreshed_stmt)).scalars().first()



@router.post("/manual", response_model=ClassOccurrenceResponse)
async def create_manual_attendance(
    req: ManualAttendanceCreate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually add an unscheduled class and immediately record its attendance.
    """
    # Verify subject exists and belongs to user
    s_stmt = select(Subject).filter(Subject.id == req.subject_id, Subject.user_id == current_user.id)
    subj = (await db.execute(s_stmt)).scalars().first()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")

    occ_status = "cancelled" if req.status == "cancelled" else "completed"

    # Create occurrence
    occ = ClassOccurrence(
        user_id=current_user.id,
        rule_id=None,
        subject_id=req.subject_id,
        date=req.date,
        start_time=req.start_time,
        end_time=req.end_time,
        faculty=req.faculty or "",
        room=req.room or "",
        status=occ_status,
        is_extra_class=True,
        notes=req.notes or ""
    )
    db.add(occ)
    await db.flush()

    # Create attendance record
    att = Attendance(
        user_id=current_user.id,
        occurrence_id=occ.id,
        status=req.status,
        marked_at=datetime.utcnow(),
        notes=req.notes or ""
    )
    db.add(att)
    await db.commit()

    # Return refreshed occurrence with loaded relations
    refreshed_stmt = (
        select(ClassOccurrence)
        .options(
            selectinload(ClassOccurrence.subject),
            selectinload(ClassOccurrence.topics),
            selectinload(ClassOccurrence.attendance)
        )
        .filter(ClassOccurrence.id == occ.id)
    )
    return (await db.execute(refreshed_stmt)).scalars().first()


@router.post("/reset")
async def reset_attendance(
    req: AttendanceResetRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Resets attendance data for a single subject or all subjects.
    Requires explicit confirmation "RESET" to prevent accidental data loss.
    """
    if req.confirmation.strip().upper() != "RESET":
        raise HTTPException(
            status_code=400,
            detail="Confirmation text must be 'RESET' to prevent accidental data reset."
        )

    result = await AttendanceService.reset_attendance(
        db, current_user.id, subject_id=req.subject_id, remove_topics=req.remove_topics
    )
    return result


@router.post("/new-semester")
async def start_new_semester(
    req: SemesterArchiveRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Archives current attendance and past class occurrences under the given label,
    beginning fresh attendance counts for the new semester.
    """
    if not req.semester_label or not req.semester_label.strip():
        raise HTTPException(
            status_code=400,
            detail="Semester label cannot be empty."
        )

    result = await AttendanceService.archive_semester(
        db, current_user.id, semester_label=req.semester_label
    )
    return result


@router.put("/history/{occurrence_id}", response_model=ClassOccurrenceResponse)
async def update_attendance_history_record(
    occurrence_id: str,
    req: AttendanceHistoryUpdateRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates an attendance history record: status (present, absent, cancelled, not_marked),
    topic covered title, and notes.
    """
    valid_statuses = ["present", "absent", "cancelled", "not_marked"]
    if req.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{req.status}'. Must be one of: {valid_statuses}"
        )

    occ_stmt = select(ClassOccurrence).options(
        selectinload(ClassOccurrence.attendance),
        selectinload(ClassOccurrence.topics),
        selectinload(ClassOccurrence.subject)
    ).filter(
        ClassOccurrence.id == occurrence_id,
        ClassOccurrence.user_id == current_user.id
    )
    occ = (await db.execute(occ_stmt)).scalars().first()
    if not occ:
        raise HTTPException(status_code=404, detail="Class occurrence not found")

    if req.status == "cancelled":
        occ.status = "cancelled"
    elif req.status in ["present", "absent"]:
        occ.status = "completed"
    else:
        occ.status = "scheduled"

    now = datetime.utcnow()
    att_stmt = select(Attendance).filter(
        Attendance.occurrence_id == occurrence_id,
        Attendance.user_id == current_user.id
    )
    att = (await db.execute(att_stmt)).scalars().first()
    if not att:
        att = Attendance(
            user_id=current_user.id,
            occurrence_id=occurrence_id,
            status=req.status,
            marked_at=now if req.status in ["present", "absent", "cancelled"] else None,
            notes=req.notes or ""
        )
        db.add(att)
    else:
        att.status = req.status
        att.marked_at = now if req.status in ["present", "absent", "cancelled"] else None
        if req.notes is not None:
            att.notes = req.notes

    # Update or add topic if provided
    if req.topic_title is not None:
        clean_title = req.topic_title.strip()
        if clean_title:
            if occ.topics and len(occ.topics) > 0:
                occ.topics[0].title = clean_title
                if req.notes is not None:
                    occ.topics[0].description = req.notes
            else:
                new_topic = ClassTopic(
                    occurrence_id=occ.id,
                    title=clean_title,
                    description=req.notes or "",
                    order_index=0
                )
                db.add(new_topic)
                if occ.topics is None:
                    occ.topics = []
                occ.topics.append(new_topic)

    await db.commit()

    refreshed_stmt = select(ClassOccurrence).options(
        selectinload(ClassOccurrence.attendance),
        selectinload(ClassOccurrence.topics),
        selectinload(ClassOccurrence.subject)
    ).filter(ClassOccurrence.id == occurrence_id)
    return (await db.execute(refreshed_stmt)).scalars().first()

