from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

import logging
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    Profile, StudyTask, StudyPlan, StudySession, Subject, Exam,
    WellbeingCheckIn, ClassOccurrence, TimetableRule, ClassTopic
)
from app.schemas.schemas import (
    StudyTaskCreate, StudyTaskUpdate, StudyTaskResponse, TaskFeedbackRequest,
    StudyPlanGenerateRequest, StudySessionLog,
    StudyWorkloadRecommendation, StudyTaskRescheduleRequest,
    SubjectDetailResponse, TopicStatusUpdateRequest, ClassTopicResponse,
    ReplanNeedMoreTimeRequest, ReplanNeedMoreTimeResponse,
    PlannerFeasibilityCheckRequest, PlannerFeasibilityCheckResponse,
    ExamSyncStatusResponse
)
from app.agent.llm_provider import get_llm_provider
from app.services.attendance_service import AttendanceService

logger = logging.getLogger("app.planner")

router = APIRouter(prefix="/planner", tags=["Study Planner"])

# Canonical MBBS Curriculum Year Mapping for Subject Categorization
MBBS_CURRICULUM_YEAR_MAP = {
    1: ["anatomy", "anat", "physiology", "phys", "biochemistry", "biochem"],
    2: ["pathology", "path", "pharmacology", "pharm", "microbiology", "micro"],
    3: ["community medicine", "psm", "spm", "forensic medicine", "fmt", "toxicology", "ophthalmology", "ophth", "eye", "ent", "otorhinolaryngology"],
    4: ["general medicine", "internal medicine", "general surgery", "surgery", "obstetrics", "gynaecology", "obgyn", "obs", "paediatrics", "pediatrics", "orthopaedics", "orthopedics", "dermatology", "psychiatry", "radiology", "anaesthesia"]
}

# Canonical MBBS Cognitive Depth / Volume Heuristics
SUBJECT_DEPTH_MAP = {
    # High volume / structural depth
    "anatomy": 1.35, "anat": 1.35,
    "general surgery": 1.35, "surgery": 1.35,
    "general medicine": 1.35, "internal medicine": 1.35, "medicine": 1.35,
    # High conceptual / clinical complexity
    "pathology": 1.20, "path": 1.20,
    "pharmacology": 1.20, "pharm": 1.20,
    "physiology": 1.15, "phys": 1.15,
    "pediatrics": 1.15, "paediatrics": 1.15,
    "obstetrics": 1.15, "gynaecology": 1.15, "obgyn": 1.15,
    # Moderate depth
    "biochemistry": 1.0, "biochem": 1.0,
    "microbiology": 1.0, "micro": 1.0,
    "ophthalmology": 1.0, "ophth": 1.0, "eye": 1.0,
    "ent": 1.0, "otorhinolaryngology": 1.0,
    # Moderate / public health
    "community medicine": 0.90, "psm": 0.90, "spm": 0.90,
    "forensic medicine": 0.90, "fmt": 0.90, "toxicology": 0.90,
}


def get_subject_depth(name: str, code: str = "") -> float:
    n = (name or "").lower().strip()
    c = (code or "").lower().strip()
    for k, v in SUBJECT_DEPTH_MAP.items():
        if k in n or (c and k in c):
            return v
    return 1.0


def normalize_topic_title(raw_title: str, subject_name: str = "") -> str:
    t = (raw_title or "").strip()
    s = (subject_name or "").strip()
    if s and t.lower().startswith(s.lower() + " — "):
        t = t[len(s) + 3:].strip()
    elif s and t.lower().startswith(s.lower() + " - "):
        t = t[len(s) + 3:].strip()
    elif " — " in t:
        parts = t.split(" — ", 1)
        t = parts[1].strip()
    elif " - " in t:
        parts = t.split(" - ", 1)
        t = parts[1].strip()
    return t.strip()


def parse_academic_year_num(year_str: Optional[str]) -> int:
    if not year_str:
        return 1
    s = year_str.lower()
    if "4" in s or "final" in s or "part 2" in s or "fourth" in s:
        return 4
    if "3" in s or "third" in s or "part 1" in s:
        return 3
    if "2" in s or "second" in s or "2nd" in s:
        return 2
    if "1" in s or "first" in s or "1st" in s:
        return 1
    return 1


def is_current_semester_subject(
    subject: Subject,
    year_of_study: Optional[str],
    active_subject_ids: set
) -> bool:
    """
    Determines if a subject belongs to the student's active / current semester.
    Primary sources:
    1. Timetable rules / class occurrences / upcoming exams / active attendance.
    2. Explicit matching subject.academic_year.
    3. Canonical MBBS curriculum mapping based on profile year_of_study.
    """
    # 1. Linked through active timetable rules, class occurrences, exams, or attendance
    if subject.id in active_subject_ids:
        return True

    # 2. Linked through explicit subject academic_year
    if subject.academic_year and year_of_study:
        s_yr = subject.academic_year.lower().strip()
        p_yr = year_of_study.lower().strip()
        if s_yr == p_yr or s_yr in p_yr or p_yr in s_yr:
            return True
        if parse_academic_year_num(subject.academic_year) != parse_academic_year_num(year_of_study):
            return False

    # 3. Canonical curriculum matching based on student's current year / semester
    student_yr = parse_academic_year_num(year_of_study)
    curr_kw = MBBS_CURRICULUM_YEAR_MAP.get(student_yr, MBBS_CURRICULUM_YEAR_MAP[1])
    s_name = (subject.name or "").lower()
    s_code = (subject.code or "").lower()

    if any(kw in s_name or kw in s_code for kw in curr_kw):
        return True

    # If it matches a DIFFERENT year's canonical keywords, it's not current
    for yr, kws in MBBS_CURRICULUM_YEAR_MAP.items():
        if yr != student_yr:
            if any(kw in s_name or kw in s_code for kw in kws):
                return False

    return False


@router.get("/subjects")
async def get_planner_subjects(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns subjects categorized for the Study Planner:
    - current_semester_subjects: subjects linked through timetable, exams, active attendance,
      or belonging to the student's active academic year.
    - other_subjects: subjects from other years or unlinked seeded subjects.
    """
    stmt = select(Subject).filter(Subject.user_id == current_user.id).order_by(Subject.name.asc())
    subjects = (await db.execute(stmt)).scalars().all()

    # Find active subject IDs from timetable rules, occurrences, exams
    tt_rules = (await db.execute(select(TimetableRule.subject_id).filter(TimetableRule.user_id == current_user.id))).scalars().all()
    occs = (await db.execute(select(ClassOccurrence.subject_id).filter(ClassOccurrence.user_id == current_user.id))).scalars().all()
    exams = (await db.execute(select(Exam.subject_id).filter(Exam.user_id == current_user.id))).scalars().all()

    active_ids = set([sid for sid in (tt_rules + occs + exams) if sid])

    target_pct = current_user.target_attendance_percentage or 75.0
    enriched: List[SubjectDetailResponse] = []
    for s in subjects:
        summary = await AttendanceService.get_subject_attendance_summary(
            db, current_user.id, s, s.target_attendance or target_pct
        )
        if summary.classes_conducted > 0:
            active_ids.add(s.id)

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

    current_sem = []
    other = []
    for d, s in zip(enriched, subjects):
        if is_current_semester_subject(s, current_user.year_of_study, active_ids):
            current_sem.append(d)
        else:
            other.append(d)

    if not current_sem and enriched:
        current_sem = enriched
        other = []

    return {
        "year_of_study": current_user.year_of_study,
        "current_semester_subjects": current_sem,
        "other_subjects": other,
        "all_subjects": enriched
    }


@router.get("/tasks", response_model=List[StudyTaskResponse])
async def get_tasks(
    scheduled_date: Optional[date] = Query(None),
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(StudyTask)
        .options(selectinload(StudyTask.subject), selectinload(StudyTask.exam))
        .filter(StudyTask.user_id == current_user.id)
    )
    if scheduled_date:
        stmt = stmt.filter(StudyTask.scheduled_date == scheduled_date)
    stmt = stmt.order_by(StudyTask.is_completed.asc(), StudyTask.scheduled_date.asc(), StudyTask.order_index.asc())
    
    tasks = (await db.execute(stmt)).scalars().all()
    return tasks


async def get_user_daily_budget(user_id: str, db: AsyncSession, plan_id: Optional[str] = None, default_budget: int = 120) -> int:
    """
    Returns the user's hard daily study budget constraint in minutes.
    Prioritizes the active or task-linked StudyPlan constraint (daily_study_budget_minutes),
    falling back to profile target or 120 min default.
    """
    if plan_id:
        p = (await db.execute(select(StudyPlan).filter(StudyPlan.id == plan_id))).scalars().first()
        if p and p.daily_study_budget_minutes and p.daily_study_budget_minutes > 0:
            return p.daily_study_budget_minutes
    active_plan = (await db.execute(
        select(StudyPlan).filter(StudyPlan.user_id == user_id, StudyPlan.status == "active")
    )).scalars().first()
    if active_plan and active_plan.daily_study_budget_minutes and active_plan.daily_study_budget_minutes > 0:
        return active_plan.daily_study_budget_minutes
    prof = (await db.execute(select(Profile).filter(Profile.id == user_id))).scalars().first()
    if prof and prof.daily_study_target_minutes and prof.daily_study_target_minutes > 0:
        return prof.daily_study_target_minutes
    return default_budget


@router.post("/tasks", response_model=StudyTaskResponse)
async def create_task(
    data: StudyTaskCreate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Enforce hard daily study budget constraint
    if data.scheduled_date and not data.confirm_budget_override:
        if data.plan_id:
            budget = await get_user_daily_budget(current_user.id, db, plan_id=data.plan_id)
        else:
            budget = current_user.daily_study_target_minutes if (current_user.daily_study_target_minutes and current_user.daily_study_target_minutes > 0) else 180
        existing_stmt = select(StudyTask).filter(
            StudyTask.user_id == current_user.id,
            StudyTask.scheduled_date == data.scheduled_date,
            StudyTask.is_completed == False
        )
        existing_tasks = (await db.execute(existing_stmt)).scalars().all()
        cur_mins = sum(t.estimated_minutes or 30 for t in existing_tasks)
        new_mins = data.estimated_minutes or 45
        if cur_mins + new_mins > budget:
            limit_str = f"{budget // 60}h {budget % 60}m" if budget % 60 else f"{budget // 60}-hour"
            raise HTTPException(
                status_code=400,
                detail=f"Daily study budget exceeded: adding this {new_mins}m task brings {data.scheduled_date.strftime('%A, %b %d')} to {cur_mins + new_mins}m, exceeding your {limit_str} daily limit. Please reschedule or confirm override."
            )

    task = StudyTask(
        user_id=current_user.id,
        subject_id=data.subject_id,
        exam_id=data.exam_id,
        plan_id=data.plan_id,
        title=data.title,
        topic_name=data.topic_name or normalize_topic_title(data.title),
        description=data.description or "",
        reason=data.reason or "",
        priority=data.priority or "medium",
        estimated_minutes=data.estimated_minutes or 45,
        actual_minutes=data.actual_minutes,
        feedback=data.feedback.lower().strip() if data.feedback else None,
        planning_score=data.planning_score,
        missed_class_date=data.missed_class_date,
        scheduled_date=data.scheduled_date,
        scheduled_time=data.scheduled_time
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    refreshed_stmt = (
        select(StudyTask)
        .options(selectinload(StudyTask.subject), selectinload(StudyTask.exam))
        .filter(StudyTask.id == task.id)
    )
    return (await db.execute(refreshed_stmt)).scalars().first()


@router.get("/tasks/{task_id}", response_model=StudyTaskResponse)
async def get_task_by_id(
    task_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(StudyTask)
        .options(selectinload(StudyTask.subject), selectinload(StudyTask.exam))
        .filter(StudyTask.id == task_id, StudyTask.user_id == current_user.id)
    )
    task = (await db.execute(stmt)).scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/tasks/{task_id}", response_model=StudyTaskResponse)
async def update_task(
    task_id: str,
    data: StudyTaskUpdate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(StudyTask).filter(StudyTask.id == task_id, StudyTask.user_id == current_user.id)
    task = (await db.execute(stmt)).scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    target_date = data.scheduled_date or task.scheduled_date
    target_mins = data.estimated_minutes if data.estimated_minutes is not None else (task.estimated_minutes or 30)
    is_rescheduling_or_duration_change = (
        (data.scheduled_date is not None and data.scheduled_date != task.scheduled_date) or
        (data.estimated_minutes is not None and data.estimated_minutes != task.estimated_minutes)
    )
    if is_rescheduling_or_duration_change and not (data.is_completed or task.is_completed) and not data.confirm_budget_override:
        if task.plan_id:
            budget = await get_user_daily_budget(current_user.id, db, plan_id=task.plan_id)
        else:
            budget = current_user.daily_study_target_minutes if (current_user.daily_study_target_minutes and current_user.daily_study_target_minutes > 0) else 180
        other_tasks_stmt = select(StudyTask).filter(
            StudyTask.user_id == current_user.id,
            StudyTask.scheduled_date == target_date,
            StudyTask.is_completed == False,
            StudyTask.id != task.id
        )
        other_tasks = (await db.execute(other_tasks_stmt)).scalars().all()
        cur_mins = sum(t.estimated_minutes or 30 for t in other_tasks)
        if cur_mins + target_mins > budget:
            limit_str = f"{budget // 60}h {budget % 60}m" if budget % 60 else f"{budget // 60}-hour"
            raise HTTPException(
                status_code=400,
                detail=f"Daily study budget exceeded: updating this task brings {target_date.strftime('%A, %b %d')} to {cur_mins + target_mins}m, exceeding your {limit_str} daily limit. Please reschedule or confirm override."
            )

    if data.subject_id is not None:
        task.subject_id = data.subject_id
    if data.title is not None:
        task.title = data.title
        task.topic_name = normalize_topic_title(data.title)
    if data.description is not None:
        task.description = data.description
    if data.priority is not None:
        task.priority = data.priority
    if data.estimated_minutes is not None:
        task.estimated_minutes = data.estimated_minutes
    if data.actual_minutes is not None:
        task.actual_minutes = data.actual_minutes
    if data.feedback is not None:
        task.feedback = data.feedback.lower().strip() if data.feedback else None
    if data.reason is not None:
        task.reason = data.reason
    if data.planning_score is not None:
        task.planning_score = data.planning_score
    if data.missed_class_date is not None:
        task.missed_class_date = data.missed_class_date
    if data.scheduled_date is not None:
        task.scheduled_date = data.scheduled_date
    if data.scheduled_time is not None:
        task.scheduled_time = data.scheduled_time
    if data.is_completed is not None:
        task.is_completed = data.is_completed
        task.completed_at = datetime.utcnow() if data.is_completed else None

    await db.commit()

    refreshed_stmt = (
        select(StudyTask)
        .options(selectinload(StudyTask.subject), selectinload(StudyTask.exam))
        .filter(StudyTask.id == task.id)
    )
    return (await db.execute(refreshed_stmt)).scalars().first()


@router.post("/tasks/{task_id}/feedback", response_model=StudyTaskResponse)
async def submit_task_feedback(
    task_id: str,
    data: TaskFeedbackRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(StudyTask).filter(StudyTask.id == task_id, StudyTask.user_id == current_user.id)
    task = (await db.execute(stmt)).scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if data.feedback:
        task.feedback = data.feedback.lower().strip()
    if data.actual_minutes is not None:
        task.actual_minutes = data.actual_minutes
    elif not task.actual_minutes:
        task.actual_minutes = task.estimated_minutes or 30

    task.is_completed = True
    if not task.completed_at:
        task.completed_at = datetime.utcnow()

    # Automatically record StudySession for audit and study history
    session_stmt = select(StudySession).filter(StudySession.task_id == task.id, StudySession.user_id == current_user.id)
    existing_session = (await db.execute(session_stmt)).scalars().first()
    if not existing_session:
        actual_dur = task.actual_minutes or 30
        session = StudySession(
            user_id=current_user.id,
            subject_id=task.subject_id,
            task_id=task.id,
            duration_minutes=actual_dur,
            mode="focus",
            notes=f"Completed study task: {task.title}" + (f" (Feedback: {task.feedback})" if task.feedback else ""),
            started_at=task.completed_at - timedelta(minutes=actual_dur),
            completed_at=task.completed_at
        )
        db.add(session)

    await db.commit()

    refreshed_stmt = (
        select(StudyTask)
        .options(selectinload(StudyTask.subject), selectinload(StudyTask.exam))
        .filter(StudyTask.id == task.id)
    )
    return (await db.execute(refreshed_stmt)).scalars().first()


@router.post("/tasks/{task_id}/replan-need-more-time", response_model=ReplanNeedMoreTimeResponse)
async def replan_need_more_time(
    task_id: str,
    req: ReplanNeedMoreTimeRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Intelligently replans schedule after a student selects 'Need more time'.
    Strictly enforces configured daily study time as a hard limit unless explicitly approved.
    Implements multi-step rebalancing:
      1. Move lower-priority tasks to later days with capacity
      2. Shorten lower-priority revision tasks (keeping min duration >= 20m)
      3. Split follow-up across days
      4. Schedule on later day with capacity
      5. Move optional revision tasks later
    Protects exams within 3 days, high-priority topics, and missed classes.
    """
    stmt = (
        select(StudyTask)
        .options(selectinload(StudyTask.subject), selectinload(StudyTask.exam), selectinload(StudyTask.plan))
        .filter(StudyTask.id == task_id, StudyTask.user_id == current_user.id)
    )
    task = (await db.execute(stmt)).scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # If actual minutes or feedback provided, update original task
    if req.actual_minutes is not None:
        task.actual_minutes = req.actual_minutes
    elif not task.actual_minutes:
        task.actual_minutes = task.estimated_minutes or 30

    task.feedback = "need_more_time"
    task.is_completed = True
    if not task.completed_at:
        task.completed_at = datetime.utcnow()

    # Record StudySession for audit
    session_stmt = select(StudySession).filter(StudySession.task_id == task.id, StudySession.user_id == current_user.id)
    existing_session = (await db.execute(session_stmt)).scalars().first()
    if not existing_session:
        actual_dur = task.actual_minutes or 30
        session = StudySession(
            user_id=current_user.id,
            subject_id=task.subject_id,
            task_id=task.id,
            duration_minutes=actual_dur,
            mode="focus",
            notes=f"Completed study task: {task.title} (Feedback: need_more_time)",
            started_at=task.completed_at - timedelta(minutes=actual_dur),
            completed_at=task.completed_at
        )
        db.add(session)

    # Strategy: handle_later -> Just save feedback, do not create any task
    if req.strategy == "handle_later":
        await db.commit()
        return ReplanNeedMoreTimeResponse(
            success=True,
            status="handle_later",
            message="Feedback saved for future planning.",
            explanation="Saved 'Need more time' feedback. No additional tasks were created.",
            daily_limit_minutes=current_user.daily_study_target_minutes or 120
        )

    # Extra minutes needed
    extra_mins = req.extra_minutes if (req.extra_minutes and req.extra_minutes > 0) else (task.estimated_minutes or 30)

    # Hard Daily Study Limit: prioritize task's plan or active plan
    daily_limit = await get_user_daily_budget(current_user.id, db, plan_id=task.plan_id)
    limit_str = f"{daily_limit // 60}h {daily_limit % 60}m" if daily_limit % 60 else f"{daily_limit // 60}-hour"

    today_d = date.today()
    tomorrow_d = today_d + timedelta(days=1)

    # Determine plan horizon
    active_plan = task.plan
    if not active_plan and task.plan_id:
        active_plan = (await db.execute(select(StudyPlan).filter(StudyPlan.id == task.plan_id))).scalars().first()
    if not active_plan:
        active_plan = (await db.execute(
            select(StudyPlan).filter(StudyPlan.user_id == current_user.id, StudyPlan.status == "active")
        )).scalars().first()

    if active_plan and active_plan.end_date and active_plan.end_date >= tomorrow_d:
        plan_num_days = (active_plan.end_date - tomorrow_d).days + 1
        days = [tomorrow_d + timedelta(days=i) for i in range(max(plan_num_days, 7))]
        plan_days = [tomorrow_d + timedelta(days=i) for i in range(plan_num_days)]
    else:
        days = [tomorrow_d + timedelta(days=i) for i in range(7)]
        plan_days = days

    # Fetch active uncompleted tasks in upcoming days
    upcoming_stmt = (
        select(StudyTask)
        .options(selectinload(StudyTask.subject), selectinload(StudyTask.exam))
        .filter(
            StudyTask.user_id == current_user.id,
            StudyTask.scheduled_date >= tomorrow_d,
            StudyTask.scheduled_date <= days[-1],
            StudyTask.is_completed == False,
            StudyTask.id != task.id
        )
        .order_by(StudyTask.scheduled_date.asc(), StudyTask.order_index.asc())
    )
    upcoming_tasks = (await db.execute(upcoming_stmt)).scalars().all()

    tasks_by_date = {d: [] for d in days}
    for ut in upcoming_tasks:
        if ut.scheduled_date in tasks_by_date:
            tasks_by_date[ut.scheduled_date].append(ut)

    daily_minutes = {d: sum(ut.estimated_minutes or 30 for ut in tasks_by_date[d]) for d in days}

    def is_protected(t: StudyTask, on_date: date) -> bool:
        if t.priority == "high":
            return True
        if t.planning_score and t.planning_score >= 75.0:
            return True
        if t.exam and t.exam.exam_date:
            days_to_exam = (t.exam.exam_date - on_date).days
            if 0 <= days_to_exam <= 3:
                return True
        if t.missed_class_date:
            return True
        reason_lower = (t.reason or "").lower()
        if "missed" in reason_lower or "catch-up" in reason_lower or "catch up" in reason_lower:
            return True
        return False

    # User explicitly authorized exceeding daily limit for Day 2 only
    if req.increase_daily_limit or req.strategy == "increase_study_time":
        target_d = req.target_date or tomorrow_d
        followup_task = StudyTask(
            user_id=current_user.id,
            plan_id=task.plan_id,
            subject_id=task.subject_id,
            exam_id=task.exam_id,
            title=f"{task.title} (Follow-up)",
            description=task.description or "",
            reason="Follow-up revision: student approved extra study time (Need more time)",
            topic_name=task.topic_name,
            priority="high",
            estimated_minutes=extra_mins,
            scheduled_date=target_d,
            is_completed=False
        )
        db.add(followup_task)
        await db.commit()
        await db.refresh(followup_task)
        new_tot = daily_minutes.get(target_d, 0) + extra_mins
        return ReplanNeedMoreTimeResponse(
            success=True,
            status="scheduled_with_increase",
            explanation=f"Added {extra_mins} minutes for {task.title} on {target_d.strftime('%A')}. Daily study extended to {new_tot // 60}h {new_tot % 60}m per your approval.",
            scheduled_date=target_d,
            task_id=followup_task.id,
            daily_limit_minutes=daily_limit
        )

    # Strategy: spread_later (Spread beyond current plan)
    if req.strategy == "spread_later":
        spread_dest = (plan_days[-1] + timedelta(days=1)) if plan_days else (days[-1] + timedelta(days=1))
        cand_d = spread_dest
        while daily_minutes.get(cand_d, 0) + extra_mins > daily_limit:
            cand_d = cand_d + timedelta(days=1)
        if active_plan and cand_d > active_plan.end_date:
            active_plan.end_date = cand_d
        followup_task = StudyTask(
            user_id=current_user.id,
            plan_id=task.plan_id,
            subject_id=task.subject_id,
            exam_id=task.exam_id,
            title=f"{task.title} (Follow-up)",
            description=task.description or "",
            reason="Follow-up revision: spread beyond current plan within daily limit",
            topic_name=task.topic_name,
            priority="high",
            estimated_minutes=extra_mins,
            scheduled_date=cand_d,
            is_completed=False
        )
        db.add(followup_task)
        await db.commit()
        await db.refresh(followup_task)
        return ReplanNeedMoreTimeResponse(
            success=True,
            status="spread_later",
            explanation=f"Scheduled {extra_mins} min {task.title} follow-up on {cand_d.strftime('%a, %b %d')} beyond current plan within your {limit_str} daily limit.",
            scheduled_date=cand_d,
            task_id=followup_task.id,
            daily_limit_minutes=daily_limit
        )

    # Strategy: move_lower_priority with specific move_task_id
    if req.strategy == "move_lower_priority" and req.move_task_id:
        target_mt = next((t for t in tasks_by_date[tomorrow_d] if t.id == req.move_task_id), None)
        if target_mt:
            dest_day = next((d for d in days[1:] if daily_minutes[d] + (target_mt.estimated_minutes or 30) <= daily_limit), None)
            if not dest_day:
                dest_day = (plan_days[-1] + timedelta(days=1)) if plan_days else (days[-1] + timedelta(days=1))
                if active_plan and dest_day > active_plan.end_date:
                    active_plan.end_date = dest_day
            target_mt.scheduled_date = dest_day
            followup_task = StudyTask(
                user_id=current_user.id,
                plan_id=task.plan_id,
                subject_id=task.subject_id,
                exam_id=task.exam_id,
                title=f"{task.title} (Follow-up)",
                description=task.description or "",
                reason="Follow-up revision: student chose to postpone lower-priority task",
                topic_name=task.topic_name,
                priority="high",
                estimated_minutes=extra_mins,
                scheduled_date=tomorrow_d,
                is_completed=False
            )
            db.add(followup_task)
            await db.commit()
            await db.refresh(followup_task)
            return ReplanNeedMoreTimeResponse(
                success=True,
                status="rebalanced",
                explanation=f"Added {extra_mins} min {task.title} follow-up to tomorrow. Moved {target_mt.title} to {dest_day.strftime('%A')} so tomorrow stays within your {limit_str} limit.",
                scheduled_date=tomorrow_d,
                task_id=followup_task.id,
                daily_limit_minutes=daily_limit
            )

    # Strategy: rebalance_tomorrow explicitly chosen
    if req.strategy == "rebalance_tomorrow" and len(tasks_by_date[tomorrow_d]) > 0:
        movable_cands = [t for t in tasks_by_date[tomorrow_d] if not is_protected(t, tomorrow_d)]
        target_move = movable_cands[0] if movable_cands else tasks_by_date[tomorrow_d][-1]
        dest_day = (plan_days[-1] + timedelta(days=1)) if plan_days else (tomorrow_d + timedelta(days=7))
        target_move.scheduled_date = dest_day
        if active_plan and dest_day > active_plan.end_date:
            active_plan.end_date = dest_day
        followup_task = StudyTask(
            user_id=current_user.id,
            plan_id=task.plan_id,
            subject_id=task.subject_id,
            exam_id=task.exam_id,
            title=f"{task.title} (Follow-up)",
            description=task.description or "",
            reason="Follow-up revision: student requested rebalancing",
            topic_name=task.topic_name,
            priority="high",
            estimated_minutes=extra_mins,
            scheduled_date=tomorrow_d,
            is_completed=False
        )
        db.add(followup_task)
        await db.commit()
        await db.refresh(followup_task)
        return ReplanNeedMoreTimeResponse(
            success=True,
            status="rebalanced",
            explanation=f"Rebalanced tomorrow: moved {target_move.title} to {dest_day.strftime('%a, %b %d')} and added {extra_mins} min for {task.title}.",
            scheduled_date=tomorrow_d,
            task_id=followup_task.id,
            daily_limit_minutes=daily_limit
        )

    # -------------------------------------------------------------
    # AUTOMATIC REBALANCING (STRATEGY == "auto")
    # -------------------------------------------------------------
    # Case 0: Tomorrow has room within the daily limit
    if daily_minutes[tomorrow_d] + extra_mins <= daily_limit:
        followup_task = StudyTask(
            user_id=current_user.id,
            plan_id=task.plan_id,
            subject_id=task.subject_id,
            exam_id=task.exam_id,
            title=f"{task.title} (Follow-up)",
            description=task.description or "",
            reason="Follow-up revision: student needed more time",
            topic_name=task.topic_name,
            priority="high",
            estimated_minutes=extra_mins,
            scheduled_date=tomorrow_d,
            is_completed=False
        )
        db.add(followup_task)
        await db.commit()
        await db.refresh(followup_task)
        rem = daily_limit - (daily_minutes[tomorrow_d] + extra_mins)
        return ReplanNeedMoreTimeResponse(
            success=True,
            status="scheduled",
            explanation=f"Added {extra_mins} minutes for {task.title} on tomorrow. Tomorrow remains within your {limit_str} limit ({rem}m remaining).",
            scheduled_date=tomorrow_d,
            task_id=followup_task.id,
            daily_limit_minutes=daily_limit
        )

    # Case 1 to 5: Tomorrow is full -> Try intelligent multi-step rebalancing
    movable_tasks = [
        t for t in tasks_by_date[tomorrow_d]
        if not is_protected(t, tomorrow_d)
    ]
    # Rank low-priority first, then largest duration
    movable_tasks.sort(key=lambda t: (0 if t.priority == "low" else 1, -(t.estimated_minutes or 30)))

    # Step 1: Move lower-priority tasks (single task move)
    moved_item = None
    for mt in movable_tasks:
        dur = mt.estimated_minutes or 30
        if (daily_minutes[tomorrow_d] - dur + extra_mins) <= daily_limit:
            dest_day = next((d for d in days[1:] if daily_minutes[d] + dur <= daily_limit), None)
            if dest_day:
                mt.scheduled_date = dest_day
                daily_minutes[tomorrow_d] -= dur
                daily_minutes[dest_day] += dur
                moved_item = {
                    "id": mt.id,
                    "title": mt.title,
                    "old_date": tomorrow_d.isoformat(),
                    "new_date": dest_day.isoformat(),
                    "day_name": dest_day.strftime("%A")
                }
                break

    if moved_item:
        followup_task = StudyTask(
            user_id=current_user.id,
            plan_id=task.plan_id,
            subject_id=task.subject_id,
            exam_id=task.exam_id,
            title=f"{task.title} (Follow-up)",
            description=task.description or "",
            reason="Follow-up revision: student needed more time (rebalanced schedule)",
            topic_name=task.topic_name,
            priority="high",
            estimated_minutes=extra_mins,
            scheduled_date=tomorrow_d,
            is_completed=False
        )
        db.add(followup_task)
        # Pre-validation verify
        assert daily_minutes[tomorrow_d] + extra_mins <= daily_limit
        await db.commit()
        await db.refresh(followup_task)
        explanation = f"Added {extra_mins} minutes for {task.title}. Moved {moved_item['title']} to {moved_item['day_name']} so tomorrow remains within your {limit_str} limit."
        return ReplanNeedMoreTimeResponse(
            success=True,
            status="rebalanced",
            explanation=explanation,
            scheduled_date=tomorrow_d,
            task_id=followup_task.id,
            moved_task=moved_item,
            daily_limit_minutes=daily_limit
        )

    # Step 1b: Moving 2 movable tasks to make room
    if len(movable_tasks) >= 2:
        for i in range(len(movable_tasks)):
            for j in range(i + 1, len(movable_tasks)):
                mt1, mt2 = movable_tasks[i], movable_tasks[j]
                dur1 = mt1.estimated_minutes or 30
                dur2 = mt2.estimated_minutes or 30
                if daily_minutes[tomorrow_d] - (dur1 + dur2) + extra_mins <= daily_limit:
                    dest1 = next((d for d in days[1:] if daily_minutes[d] + dur1 <= daily_limit), None)
                    if dest1:
                        daily_minutes[dest1] += dur1
                        dest2 = next((d for d in days[1:] if daily_minutes[d] + dur2 <= daily_limit), None)
                        daily_minutes[dest1] -= dur1
                        if dest2:
                            mt1.scheduled_date = dest1
                            mt2.scheduled_date = dest2
                            daily_minutes[tomorrow_d] -= (dur1 + dur2)
                            daily_minutes[dest1] += dur1
                            daily_minutes[dest2] += dur2
                            followup_task = StudyTask(
                                user_id=current_user.id,
                                plan_id=task.plan_id,
                                subject_id=task.subject_id,
                                exam_id=task.exam_id,
                                title=f"{task.title} (Follow-up)",
                                description=task.description or "",
                                reason="Follow-up revision: student needed more time (rebalanced schedule)",
                                topic_name=task.topic_name,
                                priority="high",
                                estimated_minutes=extra_mins,
                                scheduled_date=tomorrow_d,
                                is_completed=False
                            )
                            db.add(followup_task)
                            assert daily_minutes[tomorrow_d] + extra_mins <= daily_limit
                            assert daily_minutes[dest1] <= daily_limit
                            assert daily_minutes[dest2] <= daily_limit
                            await db.commit()
                            await db.refresh(followup_task)
                            return ReplanNeedMoreTimeResponse(
                                success=True,
                                status="rebalanced",
                                explanation=f"Added {extra_mins} min {task.title} follow-up to tomorrow. Moved {mt1.title} and {mt2.title} so tomorrow stays within your {limit_str} limit.",
                                scheduled_date=tomorrow_d,
                                task_id=followup_task.id,
                                daily_limit_minutes=daily_limit
                            )

    # Step 2: Shorten lower-priority revision task (keeping duration >= 20m)
    needed_reduction = extra_mins - max(0, daily_limit - daily_minutes[tomorrow_d])
    for mt in movable_tasks:
        dur = mt.estimated_minutes or 30
        if dur - 20 >= needed_reduction and needed_reduction > 0:
            old_dur = dur
            new_dur = dur - needed_reduction
            mt.estimated_minutes = new_dur
            daily_minutes[tomorrow_d] -= needed_reduction
            followup_task = StudyTask(
                user_id=current_user.id,
                plan_id=task.plan_id,
                subject_id=task.subject_id,
                exam_id=task.exam_id,
                title=f"{task.title} (Follow-up)",
                description=task.description or "",
                reason="Follow-up revision: shortened lower-priority study to fit daily limit",
                topic_name=task.topic_name,
                priority="high",
                estimated_minutes=extra_mins,
                scheduled_date=tomorrow_d,
                is_completed=False
            )
            db.add(followup_task)
            assert daily_minutes[tomorrow_d] + extra_mins <= daily_limit
            await db.commit()
            await db.refresh(followup_task)
            explanation = f"Added {extra_mins} min {task.title} follow-up to tomorrow. Shortened {mt.title} from {old_dur}m to {new_dur}m so tomorrow stays within your {limit_str} limit."
            return ReplanNeedMoreTimeResponse(
                success=True,
                status="rebalanced",
                explanation=explanation,
                scheduled_date=tomorrow_d,
                task_id=followup_task.id,
                daily_limit_minutes=daily_limit
            )

    # Step 3: Split the follow-up across days
    avail_tom = max(0, daily_limit - daily_minutes[tomorrow_d])
    if avail_tom >= 20 and (extra_mins - avail_tom) >= 15:
        p1 = avail_tom
        p2 = extra_mins - p1
        dest_d = next((d for d in days[1:] if daily_minutes[d] + p2 <= daily_limit), None)
        if dest_d:
            t1 = StudyTask(
                user_id=current_user.id,
                plan_id=task.plan_id,
                subject_id=task.subject_id,
                exam_id=task.exam_id,
                title=f"{task.title} (Part 1 - Follow-up)",
                description=task.description or "",
                reason="Follow-up revision part 1: split across days to respect daily limit",
                topic_name=task.topic_name,
                priority="high",
                estimated_minutes=p1,
                scheduled_date=tomorrow_d,
                is_completed=False
            )
            t2 = StudyTask(
                user_id=current_user.id,
                plan_id=task.plan_id,
                subject_id=task.subject_id,
                exam_id=task.exam_id,
                title=f"{task.title} (Part 2 - Follow-up)",
                description=task.description or "",
                reason="Follow-up revision part 2: split across days to respect daily limit",
                topic_name=task.topic_name,
                priority="high",
                estimated_minutes=p2,
                scheduled_date=dest_d,
                is_completed=False
            )
            db.add(t1)
            db.add(t2)
            assert daily_minutes[tomorrow_d] + p1 <= daily_limit
            assert daily_minutes[dest_d] + p2 <= daily_limit
            await db.commit()
            await db.refresh(t1)
            return ReplanNeedMoreTimeResponse(
                success=True,
                status="rebalanced",
                explanation=f"Split {extra_mins} min follow-up across days: {p1} min on tomorrow and {p2} min on {dest_d.strftime('%A')} to stay within your {limit_str} limit.",
                scheduled_date=tomorrow_d,
                task_id=t1.id,
                daily_limit_minutes=daily_limit
            )

    # Step 4: Move the follow-up to a later day with space
    next_free_day = next((d for d in days[1:] if daily_minutes[d] + extra_mins <= daily_limit), None)
    if next_free_day:
        followup_task = StudyTask(
            user_id=current_user.id,
            plan_id=task.plan_id,
            subject_id=task.subject_id,
            exam_id=task.exam_id,
            title=f"{task.title} (Follow-up)",
            description=task.description or "",
            reason="Follow-up revision: scheduled on next available day within daily limit",
            topic_name=task.topic_name,
            priority="high",
            estimated_minutes=extra_mins,
            scheduled_date=next_free_day,
            is_completed=False
        )
        db.add(followup_task)
        assert daily_minutes[next_free_day] + extra_mins <= daily_limit
        await db.commit()
        await db.refresh(followup_task)
        explanation = f"Tomorrow is already full ({daily_minutes[tomorrow_d]} min). Scheduled {extra_mins} minutes for {task.title} on {next_free_day.strftime('%A')} within your {limit_str} limit."
        return ReplanNeedMoreTimeResponse(
            success=True,
            status="scheduled_later",
            explanation=explanation,
            scheduled_date=next_free_day,
            task_id=followup_task.id,
            daily_limit_minutes=daily_limit
        )

    # Step 5: Move optional revision tasks later to open space
    for candidate_d in days:
        for t in list(tasks_by_date[candidate_d]):
            if (t.priority == "low" or "revision" in (t.title + (t.reason or "")).lower()) and not is_protected(t, candidate_d):
                t_dur = t.estimated_minutes or 30
                end_dest = (plan_days[-1] + timedelta(days=1)) if plan_days else (days[-1] + timedelta(days=1))
                t.scheduled_date = end_dest
                daily_minutes[candidate_d] -= t_dur
                if active_plan and end_dest > active_plan.end_date:
                    active_plan.end_date = end_dest
                if daily_minutes[tomorrow_d] + extra_mins <= daily_limit:
                    followup_task = StudyTask(
                        user_id=current_user.id,
                        plan_id=task.plan_id,
                        subject_id=task.subject_id,
                        exam_id=task.exam_id,
                        title=f"{task.title} (Follow-up)",
                        description=task.description or "",
                        reason="Follow-up revision: moved optional revision to open capacity",
                        topic_name=task.topic_name,
                        priority="high",
                        estimated_minutes=extra_mins,
                        scheduled_date=tomorrow_d,
                        is_completed=False
                    )
                    db.add(followup_task)
                    assert daily_minutes[tomorrow_d] + extra_mins <= daily_limit
                    await db.commit()
                    await db.refresh(followup_task)
                    return ReplanNeedMoreTimeResponse(
                        success=True,
                        status="rebalanced",
                        explanation=f"Added {extra_mins} min {task.title} follow-up to tomorrow. Moved optional revision {t.title} later so tomorrow stays within your {limit_str} limit.",
                        scheduled_date=tomorrow_d,
                        task_id=followup_task.id,
                        daily_limit_minutes=daily_limit
                    )

    # When NO space exists across any upcoming day within the limit:
    # DO NOT silently overload any day. Prompt student interactively!
    tomorrow_tasks_data = [
        {
            "id": t.id,
            "title": t.title,
            "priority": t.priority,
            "estimated_minutes": t.estimated_minutes or 30,
            "subject_name": t.subject.name if t.subject else "Subject"
        }
        for t in tasks_by_date[tomorrow_d]
        if not is_protected(t, tomorrow_d)
    ]
    options = [
        {
            "id": "spread_later",
            "label": "Spread beyond current plan",
            "description": "Add study days after the current plan end date"
        },
        {
            "id": "move_lower_priority",
            "label": "Move a lower-priority task",
            "description": "Pick a non-urgent task to postpone to next week"
        },
        {
            "id": "increase_study_time",
            "label": "Increase daily time for one day",
            "description": f"Authorize exceeding the {limit_str} limit for tomorrow only"
        },
        {
            "id": "handle_later",
            "label": "I'll handle it later",
            "description": "Save 'Need more time' feedback without adding extra tasks"
        }
    ]
    return ReplanNeedMoreTimeResponse(
        success=False,
        requires_user_action=True,
        status="no_space",
        message=f"Your remaining study days are already full within your {limit_str} daily limit.",
        daily_limit_minutes=daily_limit,
        options=options,
        tomorrow_tasks=tomorrow_tasks_data
    )


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(StudyTask).filter(StudyTask.id == task_id, StudyTask.user_id == current_user.id)
    task = (await db.execute(stmt)).scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await db.delete(task)
    await db.commit()
    return {"message": "Task deleted successfully"}


@router.get("/missed-topics")
async def get_missed_topics(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns missed class occurrences with recorded topics and their current study/later/skip status.
    """
    stmt = (
        select(ClassOccurrence)
        .options(
            selectinload(ClassOccurrence.topics),
            selectinload(ClassOccurrence.attendance),
            selectinload(ClassOccurrence.subject)
        )
        .filter(ClassOccurrence.user_id == current_user.id)
        .order_by(ClassOccurrence.date.desc())
    )
    occurrences = (await db.execute(stmt)).scalars().all()

    # Pre-cache user subjects to ensure subject names are always resolved
    subj_stmt = select(Subject).filter(Subject.user_id == current_user.id)
    user_subjects = {s.id: s for s in (await db.execute(subj_stmt)).scalars().all()}

    missed_list = []
    for occ in occurrences:
        if occ.status == "cancelled":
            continue
        att = occ.attendance
        if att and att.status == "absent" and occ.topics:
            subj = occ.subject or user_subjects.get(occ.subject_id)
            subj_name = subj.name if subj else "Subject"
            subj_color = (subj.color or "#72C9BE") if subj else "#72C9BE"
            missed_list.append({
                "occurrence_id": occ.id,
                "date": occ.date.isoformat(),
                "class_date": occ.date.isoformat(),
                "class_date_str": occ.date.strftime("%d %b").lstrip("0"),
                "subject_id": occ.subject_id,
                "subject_name": subj_name,
                "subject_color": subj_color,
                "subject": {
                    "id": occ.subject_id,
                    "name": subj_name,
                    "color": subj_color
                },
                "topics": [
                    {
                        "id": top.id,
                        "title": top.title,
                        "name": top.title,
                        "description": top.description or "",
                        "order_index": top.order_index,
                        "study_status": getattr(top, "study_status", "study") or "study",
                        "snooze_until": top.snooze_until.isoformat() if getattr(top, "snooze_until", None) else None,
                        "skip_reason": getattr(top, "skip_reason", None)
                    }
                    for top in occ.topics
                ]
            })

    return missed_list


@router.put("/topics/{topic_id}/status", response_model=ClassTopicResponse)
async def update_planner_topic_status(
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
async def restore_planner_topic(
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


@router.post("/feasibility-check", response_model=PlannerFeasibilityCheckResponse)
async def check_plan_feasibility(
    req: PlannerFeasibilityCheckRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Estimates whether the student's available study time is realistically sufficient
    before creating a plan, comparing available minutes against candidate topics,
    difficulty, exam importance, and urgency.
    """
    plan_days = req.plan_days if (req.plan_days and req.plan_days > 0) else 7
    hours = req.study_hours or 0
    mins = req.study_minutes or 0
    daily_minutes = (hours * 60) + mins
    if daily_minutes <= 0:
        daily_minutes = current_user.daily_study_target_minutes or 120
    total_available_minutes = plan_days * daily_minutes

    subjs_stmt = select(Subject).filter(Subject.user_id == current_user.id)
    user_subjects = (await db.execute(subjs_stmt)).scalars().all()
    subj_map = {s.id: s for s in user_subjects}

    mode = (req.subject_mode or "all").lower()
    if mode == "choose" and req.subject_ids:
        target_subjs = [s for s in user_subjects if s.id in set(req.subject_ids)]
    else:
        tt_rules_preview = (await db.execute(select(TimetableRule.subject_id).filter(TimetableRule.user_id == current_user.id))).scalars().all()
        exams_preview = (await db.execute(select(Exam.subject_id).filter(Exam.user_id == current_user.id))).scalars().all()
        recent_occs = (await db.execute(select(ClassOccurrence.subject_id).filter(ClassOccurrence.user_id == current_user.id, ClassOccurrence.date >= (date.today() - timedelta(days=14))))).scalars().all()
        active_preview_ids = set([sid for sid in (tt_rules_preview + exams_preview + recent_occs) if sid])
        target_subjs = [s for s in user_subjects if is_current_semester_subject(s, current_user.year_of_study, active_preview_ids)]
        if not target_subjs:
            target_subjs = user_subjects

    target_subj_ids = {s.id for s in target_subjs}
    today = date.today()
    cand_count = 0
    estimated_needed_minutes = 0

    exam_stmt = select(Exam).filter(Exam.user_id == current_user.id, Exam.exam_date >= today)
    exams = (await db.execute(exam_stmt)).scalars().all()
    for e in exams:
        if e.subject_id in target_subj_ids:
            tops = e.important_topics if isinstance(e.important_topics, list) else []
            if tops:
                for t in tops:
                    cand_count += 1
                    depth = get_subject_depth(subj_map.get(e.subject_id).name if subj_map.get(e.subject_id) else "")
                    estimated_needed_minutes += int(round(35 * depth))
            else:
                cand_count += 1
                estimated_needed_minutes += 40

    occ_stmt = select(ClassOccurrence).options(
        selectinload(ClassOccurrence.topics),
        selectinload(ClassOccurrence.attendance)
    ).filter(ClassOccurrence.user_id == current_user.id)
    occs = (await db.execute(occ_stmt)).scalars().all()
    for occ in occs:
        if occ.status != "cancelled" and occ.attendance and occ.attendance.status == "absent" and occ.subject_id in target_subj_ids:
            for top in (occ.topics or []):
                if getattr(top, "study_status", "study") != "skip":
                    cand_count += 1
                    estimated_needed_minutes += 35

    if cand_count < len(target_subjs):
        missing = len(target_subjs) - cand_count
        cand_count += missing
        estimated_needed_minutes += missing * 30

    if cand_count == 0:
        cand_count = max(1, len(target_subjs))
        estimated_needed_minutes = cand_count * 30

    avail_hours = round(total_available_minutes / 60.0, 1)
    needed_hours = round(estimated_needed_minutes / 60.0, 1)

    # Insufficient if available time is < 70% of estimated needed time and there are multiple topics
    is_insufficient = (total_available_minutes < estimated_needed_minutes * 0.70) and (cand_count >= 2) and (total_available_minutes > 0)

    avail_hr_str = f"{int(avail_hours)} hours" if avail_hours.is_integer() else f"{avail_hours} hours"
    if total_available_minutes < 60:
        avail_hr_str = f"{total_available_minutes} minutes"
    needed_hr_str = f"{int(needed_hours)} hours" if needed_hours.is_integer() else f"{needed_hours} hours"

    message = (
        f"Your available study time may not be enough to cover everything properly.\n\n"
        f"You have {avail_hr_str} available for {cand_count} topics.\n"
        f"MedPilot estimates about {needed_hr_str} for thorough coverage."
    ) if is_insufficient else None

    return PlannerFeasibilityCheckResponse(
        is_insufficient=is_insufficient,
        total_available_minutes=total_available_minutes,
        available_hours=avail_hours,
        candidate_topic_count=cand_count,
        estimated_needed_minutes=estimated_needed_minutes,
        estimated_needed_hours=needed_hours,
        message=message,
        warning=message,
        options=[
            "Add More Study Time",
            "Add More Days",
            "Prioritize Important Topics",
            "Create Quick Review Plan"
        ] if is_insufficient else []
    )


@router.get("/exam-sync-status", response_model=ExamSyncStatusResponse)
async def get_exam_sync_status(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Detects if any exams changed (added/removed topics, changed date, weightage, syllabus)
    since the active study plan was created.
    """
    plan_stmt = select(StudyPlan).filter(StudyPlan.user_id == current_user.id, StudyPlan.status == "active").order_by(StudyPlan.created_at.desc())
    active_plan = (await db.execute(plan_stmt)).scalars().first()
    if not active_plan:
        return ExamSyncStatusResponse(exam_sync_needed=False)

    today = date.today()
    tasks_stmt = select(StudyTask).filter(
        StudyTask.user_id == current_user.id,
        StudyTask.plan_id == active_plan.id,
        StudyTask.scheduled_date >= today,
        StudyTask.is_completed == False
    )
    unfinished_tasks = (await db.execute(tasks_stmt)).scalars().all()
    if not unfinished_tasks:
        return ExamSyncStatusResponse(exam_sync_needed=False)

    exams_stmt = select(Exam).options(selectinload(Exam.subject)).filter(
        Exam.user_id == current_user.id,
        Exam.exam_date >= today
    )
    exams = (await db.execute(exams_stmt)).scalars().all()

    changed_exams = []
    for e in exams:
        is_changed = False
        if getattr(e, "updated_at", None) and active_plan.created_at and e.updated_at > active_plan.created_at:
            is_changed = True
        else:
            e_tasks = [t for t in unfinished_tasks if t.exam_id == e.id]
            if not e_tasks and (e.important_topics or e.syllabus_portion):
                is_changed = True
            elif e_tasks:
                e_topics = set(str(t).lower().strip() for t in (e.important_topics or []))
                t_topics = set(t.topic_name.lower().strip() for t in e_tasks if t.topic_name)
                if e_topics and not e_topics.issubset(t_topics):
                    is_changed = True

        if is_changed:
            changed_exams.append({
                "id": e.id,
                "name": e.name,
                "subject_name": e.subject.name if e.subject else "",
                "exam_date": e.exam_date.isoformat(),
                "syllabus_portion": e.syllabus_portion,
                "topics": e.important_topics
            })

    exam_sync_needed = len(changed_exams) > 0
    msg = "Your exam details changed. Update your remaining study plan?" if exam_sync_needed else None

    return ExamSyncStatusResponse(
        exam_sync_needed=exam_sync_needed,
        message=msg,
        changed_exams=changed_exams,
        unfinished_task_count=len(unfinished_tasks)
    )


@router.post("/sync-exams")
async def sync_plan_with_exams(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Re-plans only unfinished/future tasks (scheduled_date >= date.today() and is_completed == False),
    updating them to align with updated exam details without altering completed tasks or history.
    """
    plan_stmt = select(StudyPlan).filter(StudyPlan.user_id == current_user.id, StudyPlan.status == "active").order_by(StudyPlan.created_at.desc())
    active_plan = (await db.execute(plan_stmt)).scalars().first()
    today = date.today()

    end_date = active_plan.end_date if active_plan and active_plan.end_date >= today else (today + timedelta(days=6))
    remaining_days = max(1, (end_date - today).days + 1)
    daily_budget = active_plan.daily_study_budget_minutes if active_plan else 120

    gen_req = StudyPlanGenerateRequest(
        start_date=today,
        end_date=end_date,
        plan_days=remaining_days,
        study_hours=daily_budget // 60,
        study_minutes=daily_budget % 60,
        subject_mode="all",
        planning_style="priority_aware"
    )
    return await generate_ai_study_plan(gen_req, current_user, db)


@router.post("/generate")
async def generate_ai_study_plan(
    req: StudyPlanGenerateRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Intelligent MBBS Study Planner Engine:
    Gathers available real curriculum data:
    1. Topics recorded from completed/attended classes
    2. Missed/absent class topics (high-priority catch up)
    3. Upcoming exams & their recorded topics / dates
    4. Existing unfinished study tasks
    5. Subject attendance risk (subjects below or near target attendance)
    6. Today's timetable / remaining classes
    7. Daily wellbeing check-in (adjusts block sizing & intensity)
    8. User's available study time / daily study hours & days

    Structured Scheduling:
    - plan_days (default 7, or calculated until next exam)
    - study_hours & study_minutes per day
    - subject_mode: 'all', 'choose', or 'auto' (Let MedPilot Decide)
    - planning_style: 'balanced' (fair subject coverage) vs 'priority_aware' (weighted to exams/catch-up)
    - until_next_exam: auto-aligns plan duration to the next exam
    - quick_review_mode: fast 15-minute high-yield review sprints

    Groundedness Guarantee:
    - Never fabricates subjects, exams, or topics.
    - If no inputs exist, returns:
      "I need something to plan. Add an exam, topic, or study task first."
    - Formats clean titles: "{Subject} — {Topic}"
    - Annotates descriptions with reasons: "Reason: missed class topic", "Reason: exam in 3 days", etc.
    - Deduplicates and reuses uncompleted tasks so re-running is idempotent.
    """
    start_d = req.start_date or date.today()

    # 1. Fetch user subjects
    subjs_stmt = select(Subject).filter(Subject.user_id == current_user.id)
    user_subjects = (await db.execute(subjs_stmt)).scalars().all()
    subj_map = {s.id: s for s in user_subjects}

    # 2. Fetch attendance summary to identify subjects at attendance risk
    at_risk_subject_ids = set()
    try:
        att_summary = await AttendanceService.get_overall_attendance_summary(db, current_user.id)
        for s_summ in att_summary.subjects_summary:
            if s_summ.is_below_target or (s_summ.classes_needed_for_target and s_summ.classes_needed_for_target > 0):
                at_risk_subject_ids.add(s_summ.subject_id)
            elif s_summ.classes_conducted > 0 and s_summ.percentage is not None:
                target = 75.0
                subj_obj = subj_map.get(s_summ.subject_id)
                if subj_obj and subj_obj.target_attendance:
                    target = subj_obj.target_attendance
                elif current_user.target_attendance_percentage:
                    target = current_user.target_attendance_percentage
                if s_summ.percentage < target:
                    at_risk_subject_ids.add(s_summ.subject_id)
    except Exception:
        pass

    # 3. Determine Plan Duration (Number of Study Days)
    plan_days = req.plan_days if (req.plan_days and req.plan_days > 0) else 7
    if req.until_next_exam:
        next_exam_stmt = (
            select(Exam)
            .filter(Exam.user_id == current_user.id, Exam.exam_date >= start_d)
            .order_by(Exam.exam_date.asc())
        )
        next_exam = (await db.execute(next_exam_stmt)).scalars().first()
        if next_exam:
            diff_days = (next_exam.exam_date - start_d).days
            plan_days = max(1, min(30, diff_days if diff_days > 0 else 1))

    end_d = req.end_date or (start_d + timedelta(days=plan_days - 1))

    # 4. Calculate Daily Study Time & Total Available Time
    if req.study_hours is not None or req.study_minutes is not None:
        hours = req.study_hours or 0
        mins = req.study_minutes or 0
        daily_study_minutes = (hours * 60) + mins
    elif req.daily_study_hours and req.daily_study_hours > 0:
        daily_study_minutes = int(round(req.daily_study_hours * 60))
    elif getattr(current_user, 'daily_study_target_minutes', None) and current_user.daily_study_target_minutes > 0:
        daily_study_minutes = current_user.daily_study_target_minutes
    elif getattr(current_user, 'daily_study_hours', None) and current_user.daily_study_hours > 0:
        daily_study_minutes = int(round(current_user.daily_study_hours * 60))
    else:
        daily_study_minutes = 120

    daily_study_minutes = max(15, daily_study_minutes)
    total_available_minutes = plan_days * daily_study_minutes

    # 5. Determine Target Subjects based on subject_mode
    subject_mode = (req.subject_mode or "all").lower()
    if subject_mode == "choose" and req.subject_ids:
        chosen_set = set(req.subject_ids)
        target_subjects = [s for s in user_subjects if s.id in chosen_set]
        if not target_subjects and user_subjects:
            target_subjects = user_subjects
    elif subject_mode == "auto":
        auto_subj_ids = set()
        exams_preview = (await db.execute(select(Exam.subject_id).filter(Exam.user_id == current_user.id, Exam.exam_date >= start_d))).scalars().all()
        auto_subj_ids.update([sid for sid in exams_preview if sid])
        recent_occs = (await db.execute(select(ClassOccurrence.subject_id).filter(ClassOccurrence.user_id == current_user.id, ClassOccurrence.date >= (start_d - timedelta(days=14))))).scalars().all()
        auto_subj_ids.update([sid for sid in recent_occs if sid])
        auto_subj_ids.update(at_risk_subject_ids)

        tt_rules_preview = (await db.execute(select(TimetableRule.subject_id).filter(TimetableRule.user_id == current_user.id))).scalars().all()
        active_preview_ids = set([sid for sid in (tt_rules_preview + exams_preview + recent_occs) if sid])
        active_preview_ids.update(at_risk_subject_ids)

        current_sem_subjects = [
            s for s in user_subjects
            if is_current_semester_subject(s, current_user.year_of_study, active_preview_ids)
        ]
        base_pool = current_sem_subjects if current_sem_subjects else user_subjects

        if auto_subj_ids:
            target_subjects = [s for s in base_pool if s.id in auto_subj_ids]
            if not target_subjects:
                target_subjects = base_pool
        else:
            target_subjects = base_pool
    else:
        # 'all': default to student's active current semester subjects
        tt_rules_preview = (await db.execute(select(TimetableRule.subject_id).filter(TimetableRule.user_id == current_user.id))).scalars().all()
        exams_preview = (await db.execute(select(Exam.subject_id).filter(Exam.user_id == current_user.id, Exam.exam_date >= start_d))).scalars().all()
        recent_occs = (await db.execute(select(ClassOccurrence.subject_id).filter(ClassOccurrence.user_id == current_user.id, ClassOccurrence.date >= (start_d - timedelta(days=14))))).scalars().all()
        active_preview_ids = set([sid for sid in (tt_rules_preview + exams_preview + recent_occs) if sid])
        active_preview_ids.update(at_risk_subject_ids)

        current_sem_subjects = [
            s for s in user_subjects
            if is_current_semester_subject(s, current_user.year_of_study, active_preview_ids)
        ]
        target_subjects = current_sem_subjects if current_sem_subjects else user_subjects

    target_subject_ids = {s.id for s in target_subjects}

    # 6. Fetch Student Wellbeing Check-in
    wb_stmt = select(WellbeingCheckIn).filter(
        WellbeingCheckIn.user_id == current_user.id,
        WellbeingCheckIn.date == start_d
    )
    wb = (await db.execute(wb_stmt)).scalars().first()
    mood = wb.mood if (wb and wb.status == "answered") else None

    # Adapt task block sizing & daily capacity
    if req.quick_review_mode:
        task_minutes = 15
        max_daily_tasks = max(1, daily_study_minutes // 15)
    elif mood == "tired":
        task_minutes = 20
        max_daily_tasks = 3
    elif mood == "stressful":
        task_minutes = 20
        max_daily_tasks = 2
    elif mood == "okay":
        task_minutes = 25
        max_daily_tasks = 3
    elif mood == "good":
        task_minutes = 35
        max_daily_tasks = 4
    elif mood == "great":
        task_minutes = 40
        max_daily_tasks = 5
    else:
        task_minutes = 30
        max_daily_tasks = 4

    effective_daily_minutes = daily_study_minutes
    if mood in ["tired", "stressful"] and not req.quick_review_mode:
        effective_daily_minutes = min(daily_study_minutes, 90)
    effective_daily_minutes = max(effective_daily_minutes, task_minutes)

    # 7. Fetch Historical Completed Tasks for Feedback Loop & Learning
    history_stmt = (
        select(StudyTask)
        .filter(StudyTask.user_id == current_user.id, StudyTask.is_completed == True)
        .order_by(StudyTask.completed_at.desc())
    )
    historical_completed = (await db.execute(history_stmt)).scalars().all()

    # Build topic history map (accumulated feedback and actual vs est overrun)
    topic_history = {}
    subject_history = {}

    for ht in historical_completed:
        candidates_to_key = []
        if ht.topic_name:
            candidates_to_key.append(normalize_topic_title(ht.topic_name).lower().strip())
        if ht.title:
            candidates_to_key.append(normalize_topic_title(ht.title).lower().strip())
            candidates_to_key.append(ht.title.lower().strip())
        for norm_t in candidates_to_key:
            if not norm_t:
                continue
            if norm_t not in topic_history:
                topic_history[norm_t] = {
                    "sessions_count": 0,
                    "hard_count": 0,
                    "need_more_time_count": 0,
                    "easy_count": 0,
                    "okay_count": 0,
                    "total_actual": 0,
                    "total_estimated": 0,
                    "latest_feedback": ht.feedback,
                    "feedback": ht.feedback,
                    "actual_minutes": ht.actual_minutes,
                    "estimated_minutes": ht.estimated_minutes,
                }
            th = topic_history[norm_t]
            th["sessions_count"] += 1
            fb = (ht.feedback or "").lower()
            if fb == "hard":
                th["hard_count"] += 1
            elif fb == "need_more_time":
                th["need_more_time_count"] += 1
            elif fb == "easy":
                th["easy_count"] += 1
            elif fb == "okay":
                th["okay_count"] += 1
            if ht.actual_minutes and ht.actual_minutes > 0:
                th["total_actual"] += ht.actual_minutes
            if ht.estimated_minutes and ht.estimated_minutes > 0:
                th["total_estimated"] += ht.estimated_minutes

        if ht.subject_id:
            if ht.subject_id not in subject_history:
                subject_history[ht.subject_id] = {"hard_count": 0, "easy_count": 0, "total": 0, "overrun_sum": 0.0}
            sh = subject_history[ht.subject_id]
            sh["total"] += 1
            if ht.feedback in ["hard", "need_more_time"]:
                sh["hard_count"] += 1
            elif ht.feedback == "easy":
                sh["easy_count"] += 1
            if ht.actual_minutes and ht.estimated_minutes and ht.estimated_minutes > 0:
                sh["overrun_sum"] += (ht.actual_minutes / ht.estimated_minutes)

    # 8. Gather Candidate Study Items
    candidates = []

    # A. Upcoming Exams
    # Load Class Occurrences first to enable cross-referencing missed classes with exams
    occ_stmt = (
        select(ClassOccurrence)
        .options(
            selectinload(ClassOccurrence.topics),
            selectinload(ClassOccurrence.attendance),
            selectinload(ClassOccurrence.subject)
        )
        .filter(ClassOccurrence.user_id == current_user.id)
        .order_by(ClassOccurrence.date.desc())
    )
    occurrences = (await db.execute(occ_stmt)).scalars().all()

    # Map of (subject_id, normalized_topic) -> (occurrence_date, formatted_date_str)
    missed_topic_map = {}
    for occ in occurrences:
        if occ.status != "cancelled" and occ.attendance and occ.attendance.status == "absent":
            occ_date_str = occ.date.strftime("%d %b").lstrip("0")
            for top in (occ.topics or []):
                if top.title:
                    norm = normalize_topic_title(top.title, occ.subject.name if occ.subject else "").lower().strip()
                    if (occ.subject_id, norm) not in missed_topic_map:
                        missed_topic_map[(occ.subject_id, norm)] = (occ.date, occ_date_str)

    # A. Upcoming Exams candidates with combined evidence weighting
    exam_stmt = (
        select(Exam)
        .options(selectinload(Exam.subject))
        .filter(Exam.user_id == current_user.id)
        .order_by(Exam.exam_date.asc())
    )
    exams = (await db.execute(exam_stmt)).scalars().all()
    upcoming_exams = [e for e in exams if e.exam_date >= (start_d - timedelta(days=1))]
    if not upcoming_exams and exams:
        upcoming_exams = [e for e in exams if e.exam_date >= (start_d - timedelta(days=30))]

    for exam in upcoming_exams:
        if target_subject_ids and exam.subject_id not in target_subject_ids:
            continue
        days_until = (exam.exam_date - start_d).days
        subj_name = exam.subject.name if exam.subject else "Exam"

        # 1. Base urgency from exam proximity
        if days_until <= 0:
            urgency_score = 10.0
            urgency_text = "Exam today"
        elif days_until == 1:
            urgency_score = 9.5
            urgency_text = "Exam tomorrow"
        elif days_until <= 3:
            urgency_score = 8.5
            urgency_text = f"Exam in {days_until} days"
        elif days_until <= 7:
            urgency_score = 6.5
            urgency_text = f"Exam in {days_until} days"
        elif days_until <= 14:
            urgency_score = 4.5
            urgency_text = f"Exam in {days_until} days"
        else:
            urgency_score = 3.0
            urgency_text = f"Exam in {days_until} days"

        # 2. Importance from exam type, target score, or weightage
        exam_importance_bonus = 0.0
        if getattr(exam, 'exam_type', None) in ("University Prof Exam", "University Prof", "Prof Exam"):
            exam_importance_bonus += 1.5
        elif getattr(exam, 'exam_type', None) in ("Internal Assessment", "Pre-Prof"):
            exam_importance_bonus += 0.5

        if getattr(exam, 'target_score', None) and exam.target_score >= 80:
            exam_importance_bonus += 1.0

        if getattr(exam, 'weightage_percentage', None) and exam.weightage_percentage:
            exam_importance_bonus += min(2.5, exam.weightage_percentage / 20.0)

        portion_str = (exam.syllabus_portion or "").strip()
        topics = exam.important_topics if isinstance(exam.important_topics, list) else []
        if topics:
            for top in topics:
                t_str = str(top).strip()
                if t_str:
                    raw_title = t_str if t_str.lower().startswith(subj_name.lower()) else f"{subj_name} — {t_str}"
                    norm_top = normalize_topic_title(raw_title, subj_name).lower()
                    
                    # Topic importance: designated in exam
                    topic_bonus = 2.0
                    reason_parts = [urgency_text]
                    if portion_str:
                        reason_parts.append(f"Unit: {portion_str}")
                    reason_parts.append("High-priority topic")

                    # Connection to missed class if student was absent for this topic
                    missed_info = missed_topic_map.get((exam.subject_id, norm_top))
                    missed_class_d = None
                    if missed_info:
                        missed_class_d, missed_date_str = missed_info
                        topic_bonus += 3.0
                        reason_parts.append(f"Missed class ({missed_date_str})")

                    base_score = urgency_score + exam_importance_bonus + topic_bonus
                    priority = "high" if base_score >= 10.0 else ("medium" if base_score >= 6.0 else "low")
                    reason = " • ".join(reason_parts)
                    desc = f"Reason: {reason.lower()}"

                    candidates.append({
                        "title": raw_title,
                        "topic_name": norm_top,
                        "description": desc,
                        "reason": reason,
                        "subject_id": exam.subject_id,
                        "exam_id": exam.id,
                        "priority": priority,
                        "base_score": base_score,
                        "category": "exam_topic",
                        "days_until_exam": days_until,
                        "missed_class_date": missed_class_d,
                        "syllabus_portion": portion_str or None
                    })
        else:
            exam_title = exam.name.strip()
            raw_title = exam_title if exam_title.lower().startswith(subj_name.lower()) else f"{subj_name} — {exam_title}"
            norm_top = normalize_topic_title(raw_title, subj_name).lower()
            base_score = urgency_score + exam_importance_bonus
            priority = "high" if base_score >= 10.0 else ("medium" if base_score >= 6.0 else "low")
            reason_parts = [urgency_text]
            if portion_str:
                reason_parts.append(f"Unit: {portion_str}")
            reason_parts.append("Exam prep")
            reason = " • ".join(reason_parts)
            desc = f"Reason: {reason.lower()}"
            candidates.append({
                "title": raw_title,
                "topic_name": norm_top,
                "description": desc,
                "reason": reason,
                "subject_id": exam.subject_id,
                "exam_id": exam.id,
                "priority": priority,
                "base_score": base_score,
                "category": "exam",
                "days_until_exam": days_until,
                "syllabus_portion": portion_str or None
            })

    # B. Class Occurrences (Missed classes & recent topics)
    for occ in occurrences:
        if occ.status == "cancelled":
            continue
        if target_subject_ids and occ.subject_id not in target_subject_ids:
            continue
        att = occ.attendance
        is_absent = (att and att.status == "absent")
        subj_name = occ.subject.name if occ.subject else "Class"
        days_ago = (start_d - occ.date).days

        if is_absent:
            score = 11.0
            priority = "high"
            occ_date_str = occ.date.strftime("%d %b").lstrip("0")

            # Check if there is an upcoming exam for this subject
            exam_for_subj = next((e for e in upcoming_exams if e.subject_id == occ.subject_id), None)
            days_until_subj_exam = (exam_for_subj.exam_date - start_d).days if exam_for_subj else None

            if occ.topics:
                for top in occ.topics:
                    # Check topic study_status and snooze_until
                    status = getattr(top, "study_status", "study") or "study"
                    snooze_until = getattr(top, "snooze_until", None)
                    if status == "skip":
                        continue
                    if status == "later" and snooze_until and snooze_until > start_d:
                        continue

                    if top.title and top.title.strip():
                        t_clean = top.title.strip()
                        raw_title = t_clean if t_clean.lower().startswith(subj_name.lower()) else f"{subj_name} — {t_clean}"
                        norm_top = normalize_topic_title(raw_title, subj_name).lower()

                        # Compact reason with class date, topic name, and exam urgency
                        reason_parts = [f"Missed class • {occ_date_str}", f"Topic: {t_clean}"]
                        if days_until_subj_exam is not None and days_until_subj_exam >= 0:
                            if days_until_subj_exam == 0:
                                reason_parts.append("Exam today")
                            elif days_until_subj_exam == 1:
                                reason_parts.append("Exam tomorrow")
                            else:
                                reason_parts.append(f"Exam in {days_until_subj_exam} days")
                        reason = " • ".join(reason_parts)
                        desc = f"Reason: missed class topic • {occ_date_str}"

                        candidates.append({
                            "title": raw_title,
                            "topic_name": norm_top,
                            "description": desc,
                            "reason": reason,
                            "subject_id": occ.subject_id,
                            "exam_id": exam_for_subj.id if exam_for_subj else None,
                            "priority": priority,
                            "base_score": score,
                            "category": "missed_class",
                            "missed_class_date": occ.date,
                            "occurrence_id": occ.id,
                            "topic_id": top.id
                        })
            else:
                raw_title = f"{subj_name} — Missed Class Catch-up"
                reason = f"Missed class • {occ_date_str} • catch-up"
                desc = f"Reason: missed class topic • {occ_date_str}"
                candidates.append({
                    "title": raw_title,
                    "topic_name": "missed class catch-up",
                    "description": desc,
                    "reason": reason,
                    "subject_id": occ.subject_id,
                    "exam_id": exam_for_subj.id if exam_for_subj else None,
                    "priority": priority,
                    "base_score": score,
                    "category": "missed_class",
                    "missed_class_date": occ.date,
                    "occurrence_id": occ.id,
                    "topic_id": None
                })
        elif occ.topics:
            if days_ago == 0:
                score = 8.0
                desc = "Reason: topic from today's class"
                reason = "Taught today • consolidation"
            elif days_ago <= 7:
                score = 6.5
                desc = "Reason: recent class topic"
                reason = "Recent class • reinforcement"
            else:
                score = 3.5
                desc = "Reason: past class topic revision"
                reason = "Past topic revision"

            priority = "high" if score >= 8 else ("medium" if score >= 5 else "low")

            for top in occ.topics:
                # Check topic study_status and snooze_until
                status = getattr(top, "study_status", "study") or "study"
                snooze_until = getattr(top, "snooze_until", None)
                if status == "skip":
                    continue
                if status == "later" and snooze_until and snooze_until > start_d:
                    continue

                if top.title and top.title.strip():
                    t_clean = top.title.strip()
                    raw_title = t_clean if t_clean.lower().startswith(subj_name.lower()) else f"{subj_name} — {t_clean}"
                    norm_top = normalize_topic_title(raw_title, subj_name).lower()
                    candidates.append({
                        "title": raw_title,
                        "topic_name": norm_top,
                        "description": desc,
                        "reason": reason,
                        "subject_id": occ.subject_id,
                        "exam_id": None,
                        "priority": priority,
                        "base_score": score,
                        "category": "class_topic",
                        "days_ago": days_ago,
                        "occurrence_id": occ.id,
                        "topic_id": top.id
                    })

    # C. Manually added unfinished study tasks
    task_stmt = (
        select(StudyTask)
        .options(selectinload(StudyTask.subject))
        .filter(
            StudyTask.user_id == current_user.id,
            StudyTask.is_completed == False
        )
    )
    manual_tasks = (await db.execute(task_stmt)).scalars().all()
    for mt in manual_tasks:
        if target_subject_ids and mt.subject_id not in target_subject_ids:
            continue
        p = (mt.priority or "medium").lower()
        if p == "high":
            score = 8.0
            reason = mt.reason or "High priority task"
        elif p == "medium":
            score = 5.0
            reason = mt.reason or "Unfinished study task"
        else:
            score = 2.5
            reason = mt.reason or "Optional revision task"

        desc = mt.description or reason
        subj_name = mt.subject.name if mt.subject else ""
        raw_title = mt.title.strip()
        if subj_name and not (raw_title.lower().startswith(subj_name.lower() + " — ") or raw_title.lower().startswith(subj_name.lower() + " - ")):
            raw_title = f"{subj_name} — {raw_title}"

        norm_top = (mt.topic_name or normalize_topic_title(raw_title, subj_name)).lower()
        candidates.append({
            "title": raw_title,
            "topic_name": norm_top,
            "description": desc,
            "reason": reason,
            "subject_id": mt.subject_id,
            "exam_id": mt.exam_id,
            "priority": p,
            "base_score": score,
            "category": "manual_task",
            "existing_task_id": mt.id
        })

    # 9. Empty State Check
    if not candidates:
        return {
            "plan_id": None,
            "title": "",
            "total_tasks_created": 0,
            "message": "I need something to plan. Add an exam, topic, or study task first.",
            "tasks": []
        }

    # 10. Deduplicate Candidates by (subject_id, normalized_title)
    unique_candidates = []
    seen_keys = set()
    for c in candidates:
        key = (c["subject_id"], c["topic_name"])
        if key not in seen_keys:
            seen_keys.add(key)
            unique_candidates.append(c)

    # 11. Enrich Candidates with Feedback Multipliers, Cognitive Depth & Build Topic Weights (W_topic)
    for c in unique_candidates:
        subj = subj_map.get(c["subject_id"])
        subj_name = subj.name if subj else ""
        depth = get_subject_depth(subj_name, subj.code if subj else "")
        c["subject_depth"] = depth

        base_s = c["base_score"]
        reason_parts = [c["reason"]] if c.get("reason") else []

        # Attendance risk bonus
        if c["subject_id"] in at_risk_subject_ids:
            base_s += 2.0
            reason_parts.append("attendance at risk")

        # Feedback loop lookup (accumulated topic & subject history)
        feedback_mult = 1.0
        hist = topic_history.get(c["topic_name"]) or topic_history.get(normalize_topic_title(c["title"]).lower().strip())
        if hist:
            hard_c = hist.get("hard_count", 0)
            nmt_c = hist.get("need_more_time_count", 0)
            easy_c = hist.get("easy_count", 0)
            latest_fb = (hist.get("latest_feedback") or hist.get("feedback") or "").lower()

            if hard_c > 0 or nmt_c > 0 or latest_fb in ["hard", "need_more_time"]:
                boost = 1.50 if (latest_fb == "need_more_time" or nmt_c > 0) else 1.45
                feedback_mult *= boost
                if nmt_c > 0 or latest_fb == "need_more_time":
                    reason_parts.append("Needed more time previously")
                else:
                    reason_parts.append("Previously marked Hard")
            elif easy_c > 0 or latest_fb == "easy":
                feedback_mult *= 0.65
                reason_parts.append("Previously mastered • quick review")
            elif latest_fb == "okay":
                feedback_mult *= 1.0
                reason_parts.append("Previously rated Okay")

            # Check completion overrun (accumulated actual > estimated)
            tot_act = hist.get("total_actual", 0) or hist.get("actual_minutes", 0)
            tot_est = hist.get("total_estimated", 0) or hist.get("estimated_minutes", 0)
            if tot_act and tot_est and tot_est > 0 and tot_act > tot_est:
                overrun = min(1.4, tot_act / tot_est)
                feedback_mult *= overrun
                reason_parts.append("Extended study needed")

        # Subject-level calibration from accumulated history
        # (e.g. If Anatomy tasks repeatedly take longer than planned and are marked Hard, future Anatomy tasks increase appropriately)
        subj_hist = subject_history.get(c["subject_id"])
        if subj_hist and subj_hist.get("total", 0) > 0:
            sh_tot = subj_hist["total"]
            sh_hard = subj_hist.get("hard_count", 0)
            sh_easy = subj_hist.get("easy_count", 0)
            sh_overrun = (subj_hist.get("overrun_sum", 0.0) / sh_tot) if sh_tot > 0 else 1.0

            if (sh_hard / sh_tot >= 0.4) or (sh_overrun > 1.15):
                subj_factor = 1.0 + min(0.35, 0.20 * (sh_hard / sh_tot) + 0.15 * max(0.0, sh_overrun - 1.0))
                feedback_mult *= subj_factor
                sname = subj_map.get(c["subject_id"]).name if subj_map.get(c["subject_id"]) else "Subject"
                calib_label = f"{sname} repeatedly takes longer"
                if calib_label not in reason_parts:
                    reason_parts.append(calib_label)
            elif (sh_easy / sh_tot >= 0.7) and (sh_overrun < 0.95):
                feedback_mult *= 0.85

        calc_w = round(base_s * feedback_mult * depth, 2)
        c["calculated_weight"] = calc_w

        # Combined evidence priority calibration
        if calc_w >= 10.0:
            c["priority"] = "high"
        elif calc_w >= 6.0:
            c["priority"] = "medium"
        else:
            c["priority"] = "low"

        c["reason"] = " • ".join(reason_parts) if reason_parts else "Curriculum study"

        if req.quick_review_mode:
            if "quick review sprint" not in c["description"].lower():
                c["description"] = f"{c['description']} • quick review sprint"
            if "quick review sprint" not in c["reason"].lower():
                c["reason"] = f"{c['reason']} • quick review sprint"

    # In Balanced Mode with Explicitly Chosen Subjects: Ensure each chosen subject has at least 1 candidate
    planning_style = (req.planning_style or "priority_aware").lower()
    if subject_mode == "choose" and planning_style == "balanced" and target_subjects:
        existing_cand_subjs = {c["subject_id"] for c in unique_candidates}
        for s in target_subjects:
            if s.id not in existing_cand_subjs:
                depth = get_subject_depth(s.name, s.code)
                unique_candidates.append({
                    "title": f"{s.name} — Subject Review",
                    "topic_name": "subject review",
                    "description": "Reason: balanced curriculum revision",
                    "reason": "Balanced curriculum revision",
                    "subject_id": s.id,
                    "exam_id": None,
                    "priority": "medium",
                    "base_score": 5.0,
                    "subject_depth": depth,
                    "calculated_weight": round(5.0 * depth, 2),
                    "category": "subject_revision"
                })

    # Group enriched candidates by subject_id
    cands_by_subject: Dict[str, List[dict]] = {}
    for c in unique_candidates:
        sid = c["subject_id"]
        if sid not in cands_by_subject:
            cands_by_subject[sid] = []
        cands_by_subject[sid].append(c)

    # Sort topics within each subject descending by calculated_weight
    for sid in cands_by_subject:
        cands_by_subject[sid].sort(key=lambda x: x["calculated_weight"], reverse=True)

    # 12. Candidate Selection Across Subjects (Balanced vs Priority-Aware)
    # Determine daily slot count (how many tasks scheduled per day)
    if req.quick_review_mode:
        daily_capacity = max(1, min(max_daily_tasks, effective_daily_minutes // 15))
    elif mood in ["tired", "stressful"]:
        daily_capacity = max(1, min(max_daily_tasks, effective_daily_minutes // 20))
    elif mood == "great":
        daily_capacity = max(1, min(max_daily_tasks, effective_daily_minutes // 40))
    else:
        daily_capacity = max(1, min(max_daily_tasks, effective_daily_minutes // 30))

    total_slots = plan_days * daily_capacity

    if planning_style == "balanced":
        # Fair Distribution: round-robin across selected subjects
        by_subject: Dict[str, List[dict]] = {s.id: [] for s in target_subjects if s.id in cands_by_subject}
        for sid in by_subject:
            by_subject[sid] = list(cands_by_subject[sid])

        subj_list = [sid for sid in by_subject.keys() if len(by_subject[sid]) > 0]
        subj_list.sort(key=lambda sid: by_subject[sid][0]["calculated_weight"] if by_subject[sid] else 0, reverse=True)

        selected_candidates = []
        subject_ptrs = {sid: 0 for sid in subj_list}
        added = True
        while len(selected_candidates) < total_slots and added:
            added = False
            for sid in subj_list:
                if len(selected_candidates) >= total_slots:
                    break
                ptr = subject_ptrs[sid]
                if ptr < len(by_subject[sid]):
                    selected_candidates.append(by_subject[sid][ptr])
                    subject_ptrs[sid] += 1
                    added = True
    else:
        # Priority-Aware Distribution:
        # Guarantee 1 item from each selected subject if slots permit, then fill remaining by highest calculated_weight
        unique_candidates.sort(key=lambda c: c["calculated_weight"], reverse=True)
        selected_candidates = []
        for sid in target_subject_ids:
            top_for_subj = next((c for c in unique_candidates if c["subject_id"] == sid and c not in selected_candidates), None)
            if top_for_subj:
                selected_candidates.append(top_for_subj)
                if len(selected_candidates) >= total_slots:
                    break

        for c in unique_candidates:
            if len(selected_candidates) >= total_slots:
                break
            if c not in selected_candidates:
                selected_candidates.append(c)

        selected_candidates.sort(key=lambda c: c["calculated_weight"], reverse=True)

    if not selected_candidates:
        selected_candidates = unique_candidates[:total_slots]

    # 13. Mood-based Single Task Block Limits
    # 13. Mood-based Single Task Block Limits
    if req.quick_review_mode:
        min_block = 15
        max_block = 15
    elif mood in ["tired", "stressful"]:
        min_block = 15
        max_block = 20
    elif mood == "great":
        min_block = 25
        max_block = 60
    else:
        min_block = 20
        max_block = 45

    # 14. Distribute Candidates Across Days & Allocate Weighted Minutes Per Day
    # Partition selected candidates across days
    tasks_per_day = [[] for _ in range(plan_days)]
    for idx, cand in enumerate(selected_candidates):
        day_idx = idx % plan_days
        tasks_per_day[day_idx].append(cand)

    scheduled_tasks_data = []
    for day_offset in range(plan_days):
        day_cands = tasks_per_day[day_offset]
        if not day_cands:
            continue

        task_date = start_d + timedelta(days=day_offset)
        day_budget = effective_daily_minutes

        if req.quick_review_mode:
            # Fixed 15m sprints
            for c in day_cands:
                score = c.get("calculated_weight", 5.0)
                logger.info(f"[PLANNER WEIGHT] Quick sprint for '{c['title']}': score={score}, alloc=15m")
                scheduled_tasks_data.append({
                    "item": c,
                    "date": task_date,
                    "order_index": len(scheduled_tasks_data),
                    "estimated_minutes": 15,
                    "planning_score": score,
                    "missed_class_date": c.get("missed_class_date"),
                    "reason": c["reason"],
                    "description": c["description"],
                    "topic_name": c["topic_name"]
                })
        else:
            # Two-Stage Weighting:
            # Stage 1: How much TOTAL time should each subject receive?
            # Stage 2: How should that subject's time be divided between its topics?
            day_subjs = list(dict.fromkeys(c["subject_id"] for c in day_cands))
            num_subjs = len(day_subjs)

            # Stage 1: Subject weights
            subj_weights = {}
            for sid in day_subjs:
                cands_for_s = [c for c in day_cands if c["subject_id"] == sid]
                max_w = max(c["calculated_weight"] for c in cands_for_s)
                avg_w = sum(c["calculated_weight"] for c in cands_for_s) / len(cands_for_s)
                subj_weights[sid] = round(0.6 * max_w + 0.4 * avg_w, 2)

            total_sw = sum(subj_weights.values()) or 1.0

            subj_time_alloc: Dict[str, float] = {}
            if planning_style == "balanced":
                # Balanced: every selected subject receives guaranteed reasonable coverage (40% baseline + 60% proportional)
                for sid in day_subjs:
                    base_share = 0.40 / num_subjs
                    prop_share = 0.60 * (subj_weights[sid] / total_sw)
                    subj_time_alloc[sid] = (base_share + prop_share) * day_budget
            else:
                # Priority-aware: stronger weighting toward urgent / high-value subjects
                exp_weights = {sid: (subj_weights[sid] ** 1.25) for sid in day_subjs}
                total_exp = sum(exp_weights.values()) or 1.0
                for sid in day_subjs:
                    subj_time_alloc[sid] = (exp_weights[sid] / total_exp) * day_budget

            # Stage 2: Topic allocation within each subject
            cur_max = 60 if (len(day_cands) <= 2 and day_budget >= 80 and mood not in ["tired", "stressful"]) else max_block
            rounded_allocations = []
            ordered_day_cands = []

            for sid in day_subjs:
                s_budget = subj_time_alloc[sid]
                cands_for_s = [c for c in day_cands if c["subject_id"] == sid]
                s_top_weights = sum(c["calculated_weight"] for c in cands_for_s) or 1.0

                for c in cands_for_s:
                    ordered_day_cands.append(c)
                    raw_mins = (c["calculated_weight"] / s_top_weights) * s_budget
                    rounded_alloc = max(min_block, min(cur_max, int(round(raw_mins / 5.0) * 5)))
                    rounded_allocations.append(rounded_alloc)

            # Adjust residual difference so daily sum equals day_budget <= daily_study_minutes
            res_diff = day_budget - sum(rounded_allocations)
            if res_diff != 0 and len(rounded_allocations) > 0:
                step = 5 if res_diff > 0 else -5
                c_idx = 0
                while res_diff != 0 and c_idx < len(rounded_allocations) * 8:
                    pos = c_idx % len(rounded_allocations)
                    trial = rounded_allocations[pos] + step
                    if min_block <= trial <= cur_max:
                        rounded_allocations[pos] = trial
                        res_diff -= step
                    c_idx += 1

            # 2-Subject Weighting Rule:
            # If 2 subjects have different weights, their allocated time must differ logically.
            if len(ordered_day_cands) == 2 and not req.quick_review_mode:
                w0 = ordered_day_cands[0]["calculated_weight"]
                w1 = ordered_day_cands[1]["calculated_weight"]
                if w0 != w1 and rounded_allocations[0] == rounded_allocations[1]:
                    diff_step = 5
                    if w0 > w1:
                        if rounded_allocations[1] - diff_step >= min_block and rounded_allocations[0] + diff_step <= cur_max:
                            rounded_allocations[0] += diff_step
                            rounded_allocations[1] -= diff_step
                    elif w1 > w0:
                        if rounded_allocations[0] - diff_step >= min_block and rounded_allocations[1] + diff_step <= cur_max:
                            rounded_allocations[1] += diff_step
                            rounded_allocations[0] -= diff_step

            for c, mins in zip(ordered_day_cands, rounded_allocations):
                score = c.get("calculated_weight", 5.0)
                sname = subj_map.get(c["subject_id"]).name if subj_map.get(c["subject_id"]) else c["subject_id"]
                logger.info(
                    f"[PLANNER WEIGHT] Subject '{sname}' Topic '{c['title']}': "
                    f"score={score}, duration={mins}m, reason={c['reason']}"
                )
                scheduled_tasks_data.append({
                    "item": c,
                    "date": task_date,
                    "order_index": len(scheduled_tasks_data),
                    "estimated_minutes": mins,
                    "planning_score": score,
                    "missed_class_date": c.get("missed_class_date"),
                    "reason": c["reason"],
                    "description": c["description"],
                    "topic_name": c["topic_name"]
                })

    # HARD DAILY BUDGET ENFORCEMENT & VERIFICATION
    # Ensure sum(task durations for any day) <= daily_study_minutes
    dates_in_plan = set(e["date"] for e in scheduled_tasks_data)
    for d in dates_in_plan:
        day_entries = [e for e in scheduled_tasks_data if e["date"] == d]
        day_sum = sum(e["estimated_minutes"] for e in day_entries)
        if day_sum > daily_study_minutes:
            excess = day_sum - daily_study_minutes
            for e in sorted(day_entries, key=lambda x: x["item"].get("calculated_weight", 5.0)):
                if excess <= 0:
                    break
                can_trim = max(0, e["estimated_minutes"] - 15)
                trim_amt = min(excess, can_trim)
                if trim_amt > 0:
                    e["estimated_minutes"] -= trim_amt
                    excess -= trim_amt
        # Final safety guarantee
        final_day_sum = sum(e["estimated_minutes"] for e in day_entries)
        if final_day_sum > daily_study_minutes:
            for e in reversed(day_entries):
                if final_day_sum <= daily_study_minutes:
                    break
                over = final_day_sum - daily_study_minutes
                trim_amt = min(over, e["estimated_minutes"] - 15)
                if trim_amt > 0:
                    e["estimated_minutes"] -= trim_amt
                    final_day_sum -= trim_amt

    # Archive previous active plans
    prev_plans = (await db.execute(
        select(StudyPlan).filter(StudyPlan.user_id == current_user.id, StudyPlan.status == "active")
    )).scalars().all()
    for p in prev_plans:
        p.status = "archived"

    # Create new StudyPlan
    plan = StudyPlan(
        user_id=current_user.id,
        title=f"{plan_days}-Day AI Study Plan ({start_d.strftime('%b %d')} – {end_d.strftime('%b %d')})",
        start_date=start_d,
        end_date=end_d,
        daily_study_budget_minutes=daily_study_minutes,
        status="active"
    )
    db.add(plan)
    await db.flush()

    # 15. Reuse / Update Existing Uncompleted Tasks (Idempotence)
    existing_uncompleted_stmt = select(StudyTask).filter(
        StudyTask.user_id == current_user.id,
        StudyTask.is_completed == False
    )
    existing_uncompleted = (await db.execute(existing_uncompleted_stmt)).scalars().all()
    existing_by_id = {t.id: t for t in existing_uncompleted}
    existing_by_subj_title = {(t.subject_id, t.title.lower().strip()): t for t in existing_uncompleted}
    existing_by_title = {t.title.lower().strip(): t for t in existing_uncompleted}

    used_task_ids = set()
    created_tasks = []
    total_planned_minutes = 0

    for entry in scheduled_tasks_data:
        item = entry["item"]
        task_date = entry["date"]
        task_mins = entry["estimated_minutes"]
        order_idx = entry["order_index"]
        reason_desc = entry.get("reason") or item.get("reason") or ""
        norm_top = entry.get("topic_name") or item.get("topic_name") or normalize_topic_title(item["title"])
        pl_score = entry.get("planning_score") or item.get("calculated_weight")
        mc_date = entry.get("missed_class_date") or item.get("missed_class_date")

        target_task = None
        if item.get("existing_task_id") and item["existing_task_id"] in existing_by_id and item["existing_task_id"] not in used_task_ids:
            target_task = existing_by_id[item["existing_task_id"]]
        else:
            key = (item["subject_id"], item["title"].lower().strip())
            if key in existing_by_subj_title and existing_by_subj_title[key].id not in used_task_ids:
                target_task = existing_by_subj_title[key]
            elif item["title"].lower().strip() in existing_by_title and existing_by_title[item["title"].lower().strip()].id not in used_task_ids:
                target_task = existing_by_title[item["title"].lower().strip()]

        if target_task:
            target_task.plan_id = plan.id
            target_task.subject_id = item["subject_id"]
            target_task.exam_id = item.get("exam_id")
            target_task.title = item["title"]
            target_task.description = item.get("description") or target_task.description or ""
            target_task.reason = reason_desc
            target_task.topic_name = norm_top
            target_task.priority = item["priority"]
            target_task.estimated_minutes = task_mins
            target_task.planning_score = pl_score
            target_task.missed_class_date = mc_date
            target_task.syllabus_portion = item.get("syllabus_portion")
            target_task.scheduled_date = task_date
            target_task.order_index = order_idx
            used_task_ids.add(target_task.id)
            created_tasks.append(target_task)
        else:
            new_task = StudyTask(
                user_id=current_user.id,
                plan_id=plan.id,
                subject_id=item["subject_id"],
                exam_id=item.get("exam_id"),
                title=item["title"],
                description=item.get("description") or "",
                reason=reason_desc,
                topic_name=norm_top,
                priority=item["priority"],
                estimated_minutes=task_mins,
                planning_score=pl_score,
                missed_class_date=mc_date,
                syllabus_portion=item.get("syllabus_portion"),
                scheduled_date=task_date,
                order_index=order_idx
            )
            db.add(new_task)
            created_tasks.append(new_task)

        total_planned_minutes += task_mins

    plan.total_planned_minutes = total_planned_minutes
    await db.commit()

    return {
        "plan_id": plan.id,
        "title": plan.title,
        "total_tasks_created": len(created_tasks),
        "message": f"Successfully scheduled {len(created_tasks)} study tasks over the next {plan_days} day{'s' if plan_days != 1 else ''} based on your {planning_style} curriculum plan!",
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "reason": t.reason or "",
                "subject_id": t.subject_id,
                "priority": t.priority,
                "estimated_minutes": t.estimated_minutes,
                "actual_minutes": t.actual_minutes,
                "planning_score": t.planning_score,
                "missed_class_date": t.missed_class_date.isoformat() if t.missed_class_date else None,
                "syllabus_portion": t.syllabus_portion,
                "feedback": t.feedback,
                "scheduled_date": str(t.scheduled_date)
            }
            for t in created_tasks
        ]
    }


@router.post("/session")
async def log_study_session(
    data: StudySessionLog,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = StudySession(
        user_id=current_user.id,
        subject_id=data.subject_id,
        task_id=data.task_id,
        duration_minutes=data.duration_minutes,
        mode=data.mode,
        session_breakdown=data.session_breakdown or {},
        notes=data.notes or "",
        started_at=data.started_at,
        completed_at=data.completed_at
    )
    db.add(session)

    # If linked to a task, mark task completed
    if data.task_id:
        task_stmt = select(StudyTask).filter(StudyTask.id == data.task_id, StudyTask.user_id == current_user.id)
        task = (await db.execute(task_stmt)).scalars().first()
        if task:
            task.is_completed = True
            task.completed_at = datetime.utcnow()

    await db.commit()
    return {"message": "Study session logged successfully", "session_id": session.id}


@router.get("/recommendation/today", response_model=StudyWorkloadRecommendation)
async def get_today_workload_recommendation(
    target_date: Optional[date] = None,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Evaluates:
    - User's self-reported daily wellbeing check-in (mood: great, good, okay, tired, stressful)
    - Upcoming exams (within 7 days)
    - Today's unfinished study tasks & priority
    - Today's timetable occurrences and topics
    - Planned study targets
    Provides non-destructive, stress-reducing workload pacing.
    """
    d = target_date or date.today()

    # 1. Fetch today's wellbeing check-in
    wb_stmt = select(WellbeingCheckIn).filter(
        WellbeingCheckIn.user_id == current_user.id,
        WellbeingCheckIn.date == d
    )
    wb_record = (await db.execute(wb_stmt)).scalars().first()
    mood = wb_record.mood if wb_record and wb_record.status == "answered" else None
    checkin_status = wb_record.status if wb_record else "pending"

    # 2. Fetch today's tasks
    tasks_stmt = (
        select(StudyTask)
        .options(selectinload(StudyTask.subject), selectinload(StudyTask.exam))
        .filter(StudyTask.user_id == current_user.id, StudyTask.scheduled_date == d)
        .order_by(StudyTask.is_completed.asc(), StudyTask.order_index.asc())
    )
    tasks = (await db.execute(tasks_stmt)).scalars().all()
    today_task_count = len(tasks)
    unfinished_tasks = [t for t in tasks if not t.is_completed]
    unfinished_task_count = len(unfinished_tasks)
    today_estimated_minutes = sum(t.estimated_minutes or 45 for t in unfinished_tasks)
    reschedule_candidates = [
        t for t in unfinished_tasks
        if (t.priority or "medium").lower() in ["medium", "low"]
    ]
    reschedule_candidates_count = len(reschedule_candidates)

    # 3. Fetch upcoming exams (within next 7 days)
    max_exam_date = d + timedelta(days=7)
    exam_stmt = (
        select(Exam)
        .options(selectinload(Exam.subject))
        .filter(Exam.user_id == current_user.id, Exam.exam_date >= d, Exam.exam_date <= max_exam_date)
        .order_by(Exam.exam_date.asc())
    )
    exams = (await db.execute(exam_stmt)).scalars().all()
    nearest_exam = exams[0] if exams else None
    urgent_exam_alert = None
    days_to_exam = None
    if nearest_exam:
        days_to_exam = (nearest_exam.exam_date - d).days
        subj_name = nearest_exam.subject.name if nearest_exam.subject else "Upcoming Subject"
        if days_to_exam <= 5:
            urgent_exam_alert = f"Upcoming Exam: {nearest_exam.name} ({subj_name}) is in {days_to_exam} day{'s' if days_to_exam != 1 else ''}."

    # 4. Fetch today's timetable classes/topics
    occ_stmt = (
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.topics), selectinload(ClassOccurrence.subject))
        .filter(ClassOccurrence.user_id == current_user.id, ClassOccurrence.date == d)
    )
    occurrences = (await db.execute(occ_stmt)).scalars().all()
    today_topics = []
    for occ in occurrences:
        if occ.status != "cancelled":
            for t in occ.topics:
                today_topics.append(t.title)

    # 5. Formulate mood-based workload recommendation
    guidance = []

    if mood == "great":
        workload_mode = "high-focus"
        suggested_block_minutes = 50
        headline = "Peak Energy: Great time for challenging concepts or ahead-of-schedule prep"
        guidance.append("Prioritize challenging or newly introduced medical concepts while your focus is high.")
        guidance.append("Use 45-50 minute deep focus blocks paired with 10-minute active recall breaks.")
        if unfinished_task_count > 0:
            guidance.append(f"You have {unfinished_task_count} unfinished task(s) today (~{today_estimated_minutes} mins). Tackle the most demanding one first.")
        else:
            guidance.append("All scheduled tasks are clear! Consider exploring high-yield question banks or previewing tomorrow's lectures.")

    elif mood == "good":
        workload_mode = "normal"
        suggested_block_minutes = 45
        headline = "Steady Momentum: Proceed with your normal planned workload"
        guidance.append("Follow your planned study schedule with steady, consistent focus.")
        guidance.append("Standard 40-45 minute study blocks with 5-minute recovery intervals.")
        if unfinished_task_count > 0:
            guidance.append(f"{unfinished_task_count} pending task(s) today (~{today_estimated_minutes} mins). Complete them in order of planned priority.")
        else:
            guidance.append("Great job staying on track with your study plan today.")

    elif mood == "okay":
        workload_mode = "paced"
        suggested_block_minutes = 30
        headline = "Balanced Pacing: Slightly shorter study blocks to protect stamina"
        guidance.append("Keep your regular academic priorities, but break study time into manageable 25-30 minute Pomodoro intervals.")
        guidance.append("Take regular 5-minute hydration or stretching breaks between focus blocks.")
        if unfinished_task_count > 0:
            guidance.append(f"Pace yourself across {unfinished_task_count} remaining task(s). Finish one block before starting the next.")

    elif mood == "tired":
        workload_mode = "light-revision"
        suggested_block_minutes = 25
        headline = "Low Energy Pacing: Prioritize light revision, flashcards & essential tasks"
        guidance.append("Prioritize light revision, notes, flashcards, or catch-up topics.")
        guidance.append("Avoid starting heavy unfamiliar topics or committing to marathon late-night sessions.")
        guidance.append("Keep sessions brief (15-20 minutes). Prioritize restorative sleep to recover for tomorrow's classes.")
        if reschedule_candidates_count > 0:
            guidance.append(f"You have {reschedule_candidates_count} non-essential task(s) that can be rescheduled to tomorrow if needed.")

    elif mood == "stressful":
        workload_mode = "essential-only"
        suggested_block_minutes = 25
        headline = "Stress-Relief Pacing: Show essential tasks first, optional workload reduced"
        guidance.append("Focus solely on your most essential study tasks. Optional items can wait.")
        guidance.append("Use short 15-20 minute low-friction focus sprints with mindful breathing pauses.")
        if reschedule_candidates_count > 0:
            guidance.append(f"{reschedule_candidates_count} optional task(s) can safely be rescheduled for tomorrow with one tap below.")
        guidance.append("Remember: consistent small efforts beat stressful cramming. Be kind to yourself.")

    else:
        # Default / pending / skipped
        workload_mode = "normal"
        suggested_block_minutes = 45
        headline = "Daily Study Plan: Balanced revision tailored to your schedule"
        guidance.append("Follow your scheduled tasks in order of academic priority.")
        guidance.append("Aim for 40-45 minute focus sessions with brief intervals.")
        if checkin_status == "pending":
            guidance.append("Optional: Complete your daily wellbeing check-in in Routine & Wellbeing after 4:00 PM to adapt this pace.")

    # 6. Incorporate Exam Alert if approaching
    if nearest_exam and days_to_exam is not None and days_to_exam <= 5:
        if mood in ["tired", "stressful"]:
            guidance.append(
                f"Exam approaching ({nearest_exam.name} in {days_to_exam}d): Focus strictly on high-yield exam topics without overload."
            )
        else:
            guidance.append(
                f"Exam approaching ({nearest_exam.name} in {days_to_exam}d): Dedicate a primary study block to this subject's high-yield topics."
            )

    # 7. Incorporate Today's Timetable Topics if relevant
    if today_topics:
        distinct_topics = list(dict.fromkeys(today_topics))
        guidance.append(
            f"Topics taught in today's classes: {', '.join(distinct_topics[:2])}. A quick 15m review will reinforce memory."
        )

    return StudyWorkloadRecommendation(
        mood=mood,
        checkin_status=checkin_status,
        workload_mode=workload_mode,
        headline=headline,
        guidance=guidance,
        suggested_block_minutes=suggested_block_minutes,
        urgent_exam_alert=urgent_exam_alert,
        today_task_count=today_task_count,
        unfinished_task_count=unfinished_task_count,
        today_estimated_minutes=today_estimated_minutes,
        reschedule_candidates_count=reschedule_candidates_count,
        disclaimer="Academic workload pacing only. MedPilot does not provide medical or mental-health advice."
    )


@router.post("/tasks/reschedule-optional")
async def reschedule_optional_tasks(
    req: StudyTaskRescheduleRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    User-initiated rescheduling of non-essential study tasks from today to tomorrow
    (or target_date). Never deletes tasks.
    """
    today_d = date.today()
    new_date = req.target_date or (today_d + timedelta(days=1))

    if req.task_ids:
        stmt = select(StudyTask).filter(
            StudyTask.id.in_(req.task_ids),
            StudyTask.user_id == current_user.id
        )
    else:
        # Default to unfinished low and medium priority tasks scheduled for today
        stmt = select(StudyTask).filter(
            StudyTask.user_id == current_user.id,
            StudyTask.scheduled_date == today_d,
            StudyTask.is_completed == False,
            StudyTask.priority.in_(["medium", "low"])
        )

    tasks_to_move = (await db.execute(stmt)).scalars().all()
    count = len(tasks_to_move)

    daily_limit = current_user.daily_study_target_minutes if (getattr(current_user, 'daily_study_target_minutes', None) and current_user.daily_study_target_minutes > 0) else 120
    
    # Query existing active tasks on target date
    dest_tasks_stmt = select(StudyTask).filter(
        StudyTask.user_id == current_user.id,
        StudyTask.scheduled_date == new_date,
        StudyTask.is_completed == False
    )
    dest_existing = (await db.execute(dest_tasks_stmt)).scalars().all()
    curr_dest_min = sum(t.estimated_minutes or 30 for t in dest_existing)

    cur_date = new_date
    cur_alloc = curr_dest_min
    overflow_days = set()

    for t in tasks_to_move:
        dur = t.estimated_minutes or 30
        if cur_alloc + dur <= daily_limit:
            t.scheduled_date = cur_date
            cur_alloc += dur
        else:
            cur_date = cur_date + timedelta(days=1)
            t.scheduled_date = cur_date
            cur_alloc = dur
            overflow_days.add(cur_date)

    await db.commit()

    overflow_msg = f" (rebalanced across {len(overflow_days) + 1} days to stay within your {daily_limit // 60}h daily limit)" if overflow_days else ""
    return {
        "message": f"Rescheduled {count} task(s) to {new_date.strftime('%a, %b %d')}{overflow_msg}.",
        "rescheduled_count": count,
        "new_date": new_date
    }

