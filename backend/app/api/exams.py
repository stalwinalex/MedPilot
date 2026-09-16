from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Profile, Exam, Subject
from app.schemas.schemas import (
    ExamCreate, ExamUpdate, ExamResponse,
    TopicSuggestionResponse, TopicValidationRequest, TopicValidationResponse
)
from app.services.curriculum_service import (
    get_subject_topic_suggestions, validate_topic_for_subject
)

router = APIRouter(prefix="/exams", tags=["Exams"])


def clean_important_topics(topics: Optional[List[str]]) -> List[str]:
    if not topics:
        return []
    cleaned = []
    seen = set()
    for t in topics:
        if not isinstance(t, str):
            continue
        ts = t.strip()
        if not ts:
            continue
        # Strip literal old placeholder if present
        if "cardiovascular system, heart failure, shock" in ts.lower():
            continue
        if ts.lower() not in seen:
            seen.add(ts.lower())
            cleaned.append(ts)
    return cleaned


@router.get("/topic-suggestions", response_model=TopicSuggestionResponse)
async def get_topic_suggestions_endpoint(
    subject_id: str,
    portion: Optional[str] = None,
    days_remaining: Optional[int] = None,
    target_score: Optional[float] = None,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Subject).filter(Subject.id == subject_id, Subject.user_id == current_user.id)
    subj = (await db.execute(stmt)).scalars().first()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")

    result = await get_subject_topic_suggestions(
        db=db,
        user_id=current_user.id,
        subject_id=subj.id,
        subject_name=subj.name,
        portion=portion,
        year_of_study=current_user.year_of_study,
        days_remaining=days_remaining,
        target_score=target_score
    )
    return TopicSuggestionResponse(
        subject_id=subj.id,
        subject_name=subj.name,
        portion=result.get("portion"),
        matched_portion=result.get("matched_portion"),
        confidence=result.get("confidence"),
        confidence_score=result.get("confidence_score"),
        match_message=result.get("match_message"),
        available_portions=result.get("available_portions", []),
        suggestions=result.get("suggestions", []),
        ai_ranked=result.get("ai_ranked", False),
        ai_provider=result.get("ai_provider")
    )


@router.post("/validate-topic", response_model=TopicValidationResponse)
async def validate_topic_endpoint(
    data: TopicValidationRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Subject).filter(Subject.id == data.subject_id, Subject.user_id == current_user.id)
    subj = (await db.execute(stmt)).scalars().first()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")

    res = validate_topic_for_subject(data.topic, subj.name, subj.code or "")
    return TopicValidationResponse(
        is_valid=res["is_valid"],
        warning=res["warning"],
        suggested_subject=res["suggested_subject"]
    )


@router.get("/", response_model=List[ExamResponse])
async def get_exams(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Exam)
        .options(selectinload(Exam.subject))
        .filter(Exam.user_id == current_user.id)
        .order_by(Exam.exam_date.asc())
    )
    exams = (await db.execute(stmt)).scalars().all()
    today = date.today()

    response_list = []
    for e in exams:
        item = ExamResponse.model_validate(e)
        item.days_remaining = (e.exam_date - today).days

        # Non-destructively inspect saved topics for cross-subject warnings
        warnings = []
        subj_name = e.subject.name if e.subject else ""
        if isinstance(e.important_topics, list) and subj_name:
            for top in e.important_topics:
                top_str = str(top).strip()
                if top_str:
                    val = validate_topic_for_subject(top_str, subj_name, e.subject.code if e.subject else "")
                    if not val["is_valid"] and val["warning"]:
                        warnings.append({
                            "topic": top_str,
                            "warning": val["warning"],
                            "suggested_subject": val["suggested_subject"]
                        })
        item.topic_warnings = warnings if warnings else None
        response_list.append(item)

    return response_list


@router.post("/", response_model=ExamResponse)
async def create_exam(
    data: ExamCreate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    cleaned_topics = clean_important_topics(data.important_topics)
    exam = Exam(
        user_id=current_user.id,
        subject_id=data.subject_id,
        name=data.name,
        exam_date=data.exam_date,
        exam_type=data.exam_type or "Internal Assessment",
        target_score=data.target_score or 75.0,
        important_topics=cleaned_topics,
        syllabus_portion=data.syllabus_portion,
        prep_status=data.prep_status or "not_started"
    )
    db.add(exam)
    await db.commit()
    await db.refresh(exam)

    stmt = select(Exam).options(selectinload(Exam.subject)).filter(Exam.id == exam.id)
    created = (await db.execute(stmt)).scalars().first()
    item = ExamResponse.model_validate(created)
    item.days_remaining = (created.exam_date - date.today()).days

    warnings = []
    subj_name = created.subject.name if created.subject else ""
    if isinstance(created.important_topics, list) and subj_name:
        for top in created.important_topics:
            top_str = str(top).strip()
            if top_str:
                val = validate_topic_for_subject(top_str, subj_name, created.subject.code if created.subject else "")
                if not val["is_valid"] and val["warning"]:
                    warnings.append({
                        "topic": top_str,
                        "warning": val["warning"],
                        "suggested_subject": val["suggested_subject"]
                    })
    item.topic_warnings = warnings if warnings else None
    return item


@router.put("/{exam_id}", response_model=ExamResponse)
async def update_exam(
    exam_id: str,
    data: ExamUpdate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Exam).filter(Exam.id == exam_id, Exam.user_id == current_user.id)
    exam = (await db.execute(stmt)).scalars().first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    if data.name is not None:
        exam.name = data.name
    if data.exam_date is not None:
        exam.exam_date = data.exam_date
    if data.exam_type is not None:
        exam.exam_type = data.exam_type
    if data.target_score is not None:
        exam.target_score = data.target_score
    if data.important_topics is not None:
        exam.important_topics = clean_important_topics(data.important_topics)
    if data.syllabus_portion is not None:
        exam.syllabus_portion = data.syllabus_portion
    if data.prep_status is not None:
        exam.prep_status = data.prep_status

    await db.commit()

    refreshed_stmt = select(Exam).options(selectinload(Exam.subject)).filter(Exam.id == exam.id)
    refreshed = (await db.execute(refreshed_stmt)).scalars().first()
    item = ExamResponse.model_validate(refreshed)
    item.days_remaining = (refreshed.exam_date - date.today()).days

    # Topic warnings for updated exam
    warnings = []
    subj_name = refreshed.subject.name if refreshed.subject else ""
    if isinstance(refreshed.important_topics, list) and subj_name:
        for top in refreshed.important_topics:
            top_str = str(top).strip()
            if top_str:
                val = validate_topic_for_subject(top_str, subj_name, refreshed.subject.code if refreshed.subject else "")
                if not val["is_valid"] and val["warning"]:
                    warnings.append({
                        "topic": top_str,
                        "warning": val["warning"],
                        "suggested_subject": val["suggested_subject"]
                    })
    item.topic_warnings = warnings if warnings else None
    return item


@router.delete("/{exam_id}")
async def delete_exam(
    exam_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Exam).filter(Exam.id == exam_id, Exam.user_id == current_user.id)
    exam = (await db.execute(stmt)).scalars().first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    await db.delete(exam)
    await db.commit()
    return {"message": "Exam deleted successfully"}
