from typing import List, Optional
from datetime import date, timedelta, time, datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Profile, TimetableRule, ClassOccurrence, ClassTopic, Attendance, Subject
from app.schemas.schemas import (
    TimetableRuleCreate, TimetableRuleUpdate, TimetableRuleResponse,
    ClassOccurrenceCreate, ClassOccurrenceUpdate, ClassOccurrenceResponse,
    ClassSwapRequest, ClassRescheduleRequest,
    ClassTopicCreate, ClassTopicUpdate, ClassTopicBatchCreate, ClassTopicResponse,
    TopicStatusUpdateRequest,
    TimetableImportItem, TimetableImportPreview, TimetableImportConfirmRequest,
    DayScheduleBatchRequest, ClassSlotInput,
    TimetableSettingsResponse, TimetableSettingsUpdate
)
from app.services.timetable_service import TimetableService
from app.services.timetable_parser_service import TimetableParserService

router = APIRouter(prefix="/timetable", tags=["Timetable"])


# -------------------------------------------------------------
# Level A: Recurring Timetable Rules
# -------------------------------------------------------------
@router.get("/rules", response_model=List[TimetableRuleResponse])
async def get_rules(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(TimetableRule)
        .options(selectinload(TimetableRule.subject))
        .filter(TimetableRule.user_id == current_user.id)
        .order_by(TimetableRule.day_of_week.asc(), TimetableRule.start_time.asc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/rules", response_model=TimetableRuleResponse)
async def create_rule(
    data: TimetableRuleCreate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    eff_from = data.effective_from or current_user.timetable_start_date or date.today()
    rule = TimetableRule(
        user_id=current_user.id,
        subject_id=data.subject_id,
        day_of_week=data.day_of_week,
        start_time=data.start_time,
        end_time=data.end_time,
        faculty=data.faculty or "",
        room=data.room or "",
        is_active=data.is_active if data.is_active is not None else True,
        effective_from=eff_from
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    # Immediately generate occurrences starting from effective_from
    today = date.today()
    start_week = today - timedelta(days=today.weekday())
    gen_start = eff_from
    end_week = max(start_week + timedelta(days=6), eff_from)
    await TimetableService.ensure_occurrences_generated(db, current_user.id, gen_start, end_week)

    # Re-fetch with subject loaded
    stmt = select(TimetableRule).options(selectinload(TimetableRule.subject)).filter(TimetableRule.id == rule.id)
    return (await db.execute(stmt)).scalars().first()


@router.post("/rules/batch", response_model=List[TimetableRuleResponse])
async def create_rules_batch(
    data: DayScheduleBatchRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not data.slots:
        raise HTTPException(status_code=400, detail="Please provide at least one class slot.")

    target_days = list(set([data.day_of_week] + (data.apply_to_days or [])))
    created_rule_ids = []
    eff_from = data.effective_from or current_user.timetable_start_date or date.today()

    for day in target_days:
        if data.replace_existing:
            # Delete existing rules for this day
            stmt = select(TimetableRule).filter(
                TimetableRule.user_id == current_user.id,
                TimetableRule.day_of_week == day
            )
            existing_rules = (await db.execute(stmt)).scalars().all()
            for r in existing_rules:
                await db.delete(r)

        for slot in data.slots:
            new_rule = TimetableRule(
                user_id=current_user.id,
                subject_id=slot.subject_id,
                day_of_week=day,
                start_time=slot.start_time,
                end_time=slot.end_time,
                faculty=slot.faculty or "",
                room=slot.room or "",
                is_active=True,
                effective_from=eff_from
            )
            db.add(new_rule)
            await db.flush()
            created_rule_ids.append(new_rule.id)

    await db.commit()

    # Immediately generate occurrences starting from effective_from
    today = date.today()
    start_week = today - timedelta(days=today.weekday())
    gen_start = eff_from
    end_window = max(start_week + timedelta(days=13), eff_from)
    await TimetableService.ensure_occurrences_generated(db, current_user.id, gen_start, end_window)

    # Return created rules with subject loaded
    stmt = (
        select(TimetableRule)
        .options(selectinload(TimetableRule.subject))
        .filter(TimetableRule.id.in_(created_rule_ids))
        .order_by(TimetableRule.day_of_week.asc(), TimetableRule.start_time.asc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.put("/rules/{rule_id}", response_model=TimetableRuleResponse)
async def update_rule(
    rule_id: str,
    data: TimetableRuleUpdate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        rule = await TimetableService.update_rule_and_future_occurrences(
            db, current_user.id, rule_id, data
        )
        stmt = select(TimetableRule).options(selectinload(TimetableRule.subject)).filter(TimetableRule.id == rule.id)
        return (await db.execute(stmt)).scalars().first()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TimetableRule).filter(TimetableRule.id == rule_id, TimetableRule.user_id == current_user.id)
    rule = (await db.execute(stmt)).scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    from sqlalchemy import delete
    # Completely delete all occurrences generated from this rule along with attendance
    del_occs_stmt = select(ClassOccurrence).filter(
        ClassOccurrence.rule_id == rule_id,
        ClassOccurrence.user_id == current_user.id
    )
    occs = (await db.execute(del_occs_stmt)).scalars().all()
    for o in occs:
        await db.execute(delete(Attendance).filter(Attendance.occurrence_id == o.id))
        await db.execute(delete(ClassTopic).filter(ClassTopic.occurrence_id == o.id))
        await db.delete(o)

    await db.delete(rule)
    await db.commit()
    return {"message": "Recurring timetable rule and its classes completely deleted"}


@router.delete("/occurrences/{occurrence_id}")
async def delete_occurrence(
    occurrence_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ClassOccurrence).filter(
        ClassOccurrence.id == occurrence_id,
        ClassOccurrence.user_id == current_user.id
    )
    occ = (await db.execute(stmt)).scalars().first()
    if not occ:
        raise HTTPException(status_code=404, detail="Class occurrence not found")

    from sqlalchemy import delete
    await db.execute(delete(Attendance).filter(Attendance.occurrence_id == occurrence_id))
    await db.execute(delete(ClassTopic).filter(ClassTopic.occurrence_id == occurrence_id))
    await db.delete(occ)
    await db.commit()
    return {"message": "Class occurrence completely deleted"}


# -------------------------------------------------------------
# Level B: Individual Class Occurrences
# -------------------------------------------------------------
@router.get("/occurrences", response_model=List[ClassOccurrenceResponse])
async def get_occurrences(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    today = date.today()
    s_date = start_date or (today - timedelta(days=today.weekday()))
    e_date = end_date or (s_date + timedelta(days=6))

    occurrences = await TimetableService.get_occurrences_for_range(db, current_user.id, s_date, e_date)
    return occurrences


@router.get("/occurrences/{occurrence_id}", response_model=ClassOccurrenceResponse)
async def get_occurrence_by_id(
    occurrence_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ClassOccurrence)
        .options(
            selectinload(ClassOccurrence.subject),
            selectinload(ClassOccurrence.topics),
            selectinload(ClassOccurrence.attendance)
        )
        .filter(ClassOccurrence.id == occurrence_id, ClassOccurrence.user_id == current_user.id)
    )
    occ = (await db.execute(stmt)).scalars().first()
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence not found")
    return occ


@router.post("/occurrences", response_model=ClassOccurrenceResponse)
async def add_extra_class(
    data: ClassOccurrenceCreate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    occ = await TimetableService.add_extra_class(db, current_user.id, data)
    stmt = (
        select(ClassOccurrence)
        .options(
            selectinload(ClassOccurrence.subject),
            selectinload(ClassOccurrence.topics),
            selectinload(ClassOccurrence.attendance)
        )
        .filter(ClassOccurrence.id == occ.id)
    )
    return (await db.execute(stmt)).scalars().first()


@router.put("/occurrences/{occurrence_id}", response_model=ClassOccurrenceResponse)
async def update_occurrence(
    occurrence_id: str,
    data: ClassOccurrenceUpdate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ClassOccurrence).filter(ClassOccurrence.id == occurrence_id, ClassOccurrence.user_id == current_user.id)
    occ = (await db.execute(stmt)).scalars().first()
    if not occ:
        raise HTTPException(status_code=404, detail="Class occurrence not found")

    if data.subject_id is not None:
        occ.subject_id = data.subject_id
    if data.date is not None:
        if occ.date != data.date and not occ.original_date:
            occ.original_date = occ.date
        occ.date = data.date
    if data.start_time is not None:
        if occ.start_time != data.start_time and not occ.original_start_time:
            occ.original_start_time = occ.start_time
        occ.start_time = data.start_time
    if data.end_time is not None:
        occ.end_time = data.end_time
    if data.faculty is not None:
        occ.faculty = data.faculty
    if data.room is not None:
        occ.room = data.room
    if data.notes is not None:
        occ.notes = data.notes

    if data.status is not None:
        occ.status = data.status
        # Synchronize attendance record
        att_stmt = select(Attendance).filter(Attendance.occurrence_id == occ.id, Attendance.user_id == current_user.id)
        att = (await db.execute(att_stmt)).scalars().first()
        if data.status == "cancelled":
            if att:
                att.status = "cancelled"
            else:
                att = Attendance(user_id=current_user.id, occurrence_id=occ.id, status="cancelled", marked_at=datetime.utcnow(), notes="")
                db.add(att)
        elif data.status == "scheduled":
            if att and att.status == "cancelled":
                att.status = "not_marked"

    await db.commit()

    refreshed_stmt = (
        select(ClassOccurrence)
        .options(
            selectinload(ClassOccurrence.subject),
            selectinload(ClassOccurrence.topics),
            selectinload(ClassOccurrence.attendance)
        )
        .filter(ClassOccurrence.id == occurrence_id)
    )
    return (await db.execute(refreshed_stmt)).scalars().first()


@router.post("/occurrences/{occurrence_id}/toggle-cancel", response_model=ClassOccurrenceResponse)
async def toggle_occurrence_cancel(
    occurrence_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.attendance))
        .filter(ClassOccurrence.id == occurrence_id, ClassOccurrence.user_id == current_user.id)
    )
    occ = (await db.execute(stmt)).scalars().first()
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence not found")

    att_stmt = select(Attendance).filter(Attendance.occurrence_id == occ.id, Attendance.user_id == current_user.id)
    att = (await db.execute(att_stmt)).scalars().first()

    if occ.status == "cancelled":
        occ.status = "scheduled"
        if att and att.status == "cancelled":
            att.status = "not_marked"
    else:
        occ.status = "cancelled"
        if att:
            att.status = "cancelled"
        else:
            att = Attendance(user_id=current_user.id, occurrence_id=occ.id, status="cancelled", marked_at=datetime.utcnow(), notes="")
            db.add(att)

    await db.commit()
    refreshed = (
        select(ClassOccurrence)
        .options(
            selectinload(ClassOccurrence.subject),
            selectinload(ClassOccurrence.topics),
            selectinload(ClassOccurrence.attendance)
        )
        .filter(ClassOccurrence.id == occurrence_id)
    )
    return (await db.execute(refreshed)).scalars().first()



@router.post("/occurrences/{occurrence_id}/topics", response_model=ClassTopicResponse)
async def add_topic_to_occurrence(
    occurrence_id: str,
    data: ClassTopicCreate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.topics))
        .filter(ClassOccurrence.id == occurrence_id, ClassOccurrence.user_id == current_user.id)
    )
    occ = (await db.execute(stmt)).scalars().first()
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence not found")

    raw_title = data.title.strip()
    if not raw_title:
        raise HTTPException(status_code=400, detail="Topic title cannot be empty")

    # Support multiple topics separated by newline or comma
    delimiter = "\n" if "\n" in raw_title else ("," if "," in raw_title else None)
    if delimiter:
        parts = [p.strip() for p in raw_title.split(delimiter) if p.strip()]
    else:
        parts = [raw_title]

    existing_count = len(occ.topics or [])
    created_topics = []
    for idx, part in enumerate(parts):
        topic = ClassTopic(
            occurrence_id=occ.id,
            title=part,
            description=data.description or "",
            order_index=(data.order_index or existing_count) + idx
        )
        db.add(topic)
        created_topics.append(topic)

    await db.commit()
    for t in created_topics:
        await db.refresh(t)
    return created_topics[0]


@router.post("/occurrences/{occurrence_id}/topics/batch", response_model=List[ClassTopicResponse])
async def add_topics_batch_to_occurrence(
    occurrence_id: str,
    data: ClassTopicBatchCreate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.topics))
        .filter(ClassOccurrence.id == occurrence_id, ClassOccurrence.user_id == current_user.id)
    )
    occ = (await db.execute(stmt)).scalars().first()
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence not found")

    existing_count = len(occ.topics or [])
    created = []
    for idx, title_text in enumerate(data.topics):
        clean_text = title_text.strip()
        if clean_text:
            topic = ClassTopic(
                occurrence_id=occ.id,
                title=clean_text,
                description=data.description or "",
                order_index=existing_count + idx
            )
            db.add(topic)
            created.append(topic)

    await db.commit()
    for t in created:
        await db.refresh(t)
    return created


@router.put("/topics/{topic_id}", response_model=ClassTopicResponse)
async def update_topic(
    topic_id: str,
    data: ClassTopicUpdate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ClassTopic)
        .join(ClassOccurrence, ClassTopic.occurrence_id == ClassOccurrence.id)
        .filter(ClassTopic.id == topic_id, ClassOccurrence.user_id == current_user.id)
    )
    topic = (await db.execute(stmt)).scalars().first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    if data.title is not None and data.title.strip():
        topic.title = data.title.strip()
    if data.description is not None:
        topic.description = data.description.strip()
    if data.order_index is not None:
        topic.order_index = data.order_index
    if data.study_status is not None:
        topic.study_status = data.study_status.lower().strip()
    if data.snooze_until is not None:
        topic.snooze_until = data.snooze_until
    if data.skip_reason is not None:
        topic.skip_reason = data.skip_reason

    await db.commit()
    await db.refresh(topic)
    return topic


@router.put("/topics/{topic_id}/status", response_model=ClassTopicResponse)
async def update_topic_status(
    topic_id: str,
    data: TopicStatusUpdateRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ClassTopic)
        .join(ClassOccurrence, ClassTopic.occurrence_id == ClassOccurrence.id)
        .filter(ClassTopic.id == topic_id, ClassOccurrence.user_id == current_user.id)
    )
    topic = (await db.execute(stmt)).scalars().first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    status = data.study_status.lower().strip()
    if status not in ["study", "later", "skip"]:
        raise HTTPException(status_code=400, detail="Invalid study_status. Must be 'study', 'later', or 'skip'")

    topic.study_status = status

    if status == "later":
        if data.snooze_until:
            topic.snooze_until = data.snooze_until
        elif data.snooze_days:
            topic.snooze_until = date.today() + timedelta(days=data.snooze_days)
        else:
            topic.snooze_until = date.today() + timedelta(days=1)
        topic.skip_reason = None
    elif status == "skip":
        topic.snooze_until = None
        topic.skip_reason = data.skip_reason or "skip_this_plan"
    else:  # study
        topic.snooze_until = None
        topic.skip_reason = None

    await db.commit()
    await db.refresh(topic)
    return topic


@router.post("/topics/{topic_id}/restore", response_model=ClassTopicResponse)
async def restore_topic(
    topic_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ClassTopic)
        .join(ClassOccurrence, ClassTopic.occurrence_id == ClassOccurrence.id)
        .filter(ClassTopic.id == topic_id, ClassOccurrence.user_id == current_user.id)
    )
    topic = (await db.execute(stmt)).scalars().first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    topic.study_status = "study"
    topic.snooze_until = None
    topic.skip_reason = None

    await db.commit()
    await db.refresh(topic)
    return topic


@router.delete("/topics/{topic_id}")
async def delete_topic(
    topic_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ClassTopic)
        .join(ClassOccurrence, ClassTopic.occurrence_id == ClassOccurrence.id)
        .filter(ClassTopic.id == topic_id, ClassOccurrence.user_id == current_user.id)
    )
    topic = (await db.execute(stmt)).scalars().first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    await db.delete(topic)
    await db.commit()
    return {"message": "Topic deleted successfully"}


@router.post("/reschedule", response_model=ClassOccurrenceResponse)
async def reschedule_occurrence(
    req: ClassRescheduleRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        occ = await TimetableService.reschedule_class(db, current_user.id, req)
        stmt = (
            select(ClassOccurrence)
            .options(
                selectinload(ClassOccurrence.subject),
                selectinload(ClassOccurrence.topics),
                selectinload(ClassOccurrence.attendance)
            )
            .filter(ClassOccurrence.id == occ.id)
        )
        return (await db.execute(stmt)).scalars().first()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/swap")
async def swap_occurrences(
    req: ClassSwapRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        occ1, occ2 = await TimetableService.swap_classes(db, current_user.id, req)
        return {"message": "Classes successfully swapped", "swapped": [occ1.id, occ2.id]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------------------------------------------
# Timetable Import & Review
# -------------------------------------------------------------
@router.post("/import/parse", response_model=TimetableImportPreview)
async def parse_timetable_file(
    file: UploadFile = File(...),
    api_key: Optional[str] = Form(None),
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    filename = file.filename or "uploaded_file"
    ext = filename.lower().split('.')[-1]
    if ext not in ["pdf", "jpg", "jpeg", "png", "webp"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '.{ext}'. Please upload a PDF or image (JPG, PNG, WEBP)."
        )

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum allowed size is 10 MB.")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    subj_stmt = select(Subject).filter(Subject.user_id == current_user.id)
    subjects = (await db.execute(subj_stmt)).scalars().all()

    warnings = []
    items = []
    raw_text = ""

    # 1. Try AI Multimodal Vision (Gemini 1.5 Flash)
    gemini_items = await TimetableParserService.parse_with_gemini(
        file_bytes=content,
        filename=filename,
        existing_subjects=subjects,
        api_key=api_key
    )

    if gemini_items:
        items = gemini_items
        raw_text = f"✨ AI Agent successfully parsed '{filename}' with multimodal vision. Extracted {len(items)} classes with high accuracy."
    else:
        # Fallback to local OCR / PDF text extraction + enhanced table parser
        if ext == "pdf":
            raw_text = TimetableParserService.extract_text_from_pdf(content)
            if not raw_text.strip():
                warnings.append("Could not extract selectable text from this PDF. It may be a scanned document or image-only PDF.")
        else:
            raw_text = await TimetableParserService.extract_text_from_image(content, filename)
            if not raw_text.strip():
                warnings.append("OCR could not detect readable text from this image. Please ensure the timetable is clear, well-lit, and in focus.")

        items = TimetableParserService.parse_timetable_text(raw_text, subjects)

        if not items and raw_text.strip():
            warnings.append("Text was detected, but no standard class time patterns were recognized. You can add classes manually.")
        elif not items:
            warnings.append("No class schedule was detected. Try another file or enter classes manually.")

    rule_stmt = select(TimetableRule).filter(TimetableRule.user_id == current_user.id)
    rules = (await db.execute(rule_stmt)).scalars().all()
    conflict_count = TimetableParserService.detect_conflicts(rules, items)

    return TimetableImportPreview(
        extracted_items=items,
        raw_text=raw_text[:2000],
        warnings=warnings,
        duplicate_count=conflict_count
    )


@router.post("/import/confirm")
async def confirm_timetable_import(
    req: TimetableImportConfirmRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not req.items:
        raise HTTPException(status_code=400, detail="No items to import.")

    subj_stmt = select(Subject).filter(Subject.user_id == current_user.id)
    existing_subjects = {s.name.lower(): s for s in (await db.execute(subj_stmt)).scalars().all()}
    subj_by_id = {s.id: s for s in existing_subjects.values()}

    rule_stmt = select(TimetableRule).filter(TimetableRule.user_id == current_user.id)
    existing_rules = (await db.execute(rule_stmt)).scalars().all()

    imported_count = 0
    skipped_count = 0
    new_subjects_created = 0

    starts_from = req.schedule_starts_from or current_user.timetable_start_date or date.today()
    if current_user.timetable_start_date != starts_from:
        current_user.timetable_start_date = starts_from
        db.add(current_user)

    for item in req.items:
        try:
            start_t = time.fromisoformat(item.start_time)
            end_t = time.fromisoformat(item.end_time)
        except Exception:
            skipped_count += 1
            continue

        conflicting_rule = None
        for r in existing_rules:
            if r.day_of_week == item.day_of_week and r.is_active:
                if max(start_t, r.start_time) < min(end_t, r.end_time):
                    conflicting_rule = r
                    break

        if conflicting_rule:
            if req.duplicate_mode == "skip":
                skipped_count += 1
                continue
            elif req.duplicate_mode == "replace":
                await db.delete(conflicting_rule)
                existing_rules.remove(conflicting_rule)

        subject_id = item.matched_subject_id
        if not subject_id or subject_id not in subj_by_id:
            subj_name = (item.subject_name or "General Subject").strip()
            if subj_name.lower() in existing_subjects:
                subject_id = existing_subjects[subj_name.lower()].id
            else:
                new_subj = Subject(
                    user_id=current_user.id,
                    name=subj_name,
                    code=subj_name[:4].upper(),
                    color="#0D9488",
                    target_attendance=current_user.target_attendance_percentage or 75.0,
                    faculty=item.faculty or ""
                )
                db.add(new_subj)
                await db.flush()
                existing_subjects[subj_name.lower()] = new_subj
                subj_by_id[new_subj.id] = new_subj
                subject_id = new_subj.id
                new_subjects_created += 1

        new_rule = TimetableRule(
            user_id=current_user.id,
            subject_id=subject_id,
            day_of_week=item.day_of_week,
            start_time=start_t,
            end_time=end_t,
            faculty=item.faculty or "",
            room=item.room or "",
            is_active=True,
            effective_from=starts_from
        )
        db.add(new_rule)
        imported_count += 1

    await db.commit()

    today = date.today()
    start_week = today - timedelta(days=today.weekday())
    gen_start = starts_from
    end_next_week = max(start_week + timedelta(days=13), starts_from)
    await TimetableService.ensure_occurrences_generated(db, current_user.id, gen_start, end_next_week)

    return {
        "message": f"Successfully imported {imported_count} timetable classes.",
        "imported_count": imported_count,
        "skipped_count": skipped_count,
        "new_subjects_created": new_subjects_created
    }


# -------------------------------------------------------------
# Timetable Settings
# -------------------------------------------------------------
@router.get("/settings", response_model=TimetableSettingsResponse)
async def get_timetable_settings(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return TimetableSettingsResponse(
        timetable_start_date=current_user.timetable_start_date
    )


@router.patch("/settings", response_model=TimetableSettingsResponse)
async def update_timetable_settings(
    data: TimetableSettingsUpdate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if data.timetable_start_date is not None:
        current_user.timetable_start_date = data.timetable_start_date
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)

        # Cleanup invalid past occurrences if start date was set or moved
        await TimetableService.cleanup_invalid_past_occurrences(db, current_user.id)

        # Ensure occurrences are generated from new start date
        today = date.today()
        start_week = today - timedelta(days=today.weekday())
        gen_start = data.timetable_start_date
        end_window = max(start_week + timedelta(days=13), gen_start)
        await TimetableService.ensure_occurrences_generated(db, current_user.id, gen_start, end_window)

    return TimetableSettingsResponse(
        timetable_start_date=current_user.timetable_start_date
    )
