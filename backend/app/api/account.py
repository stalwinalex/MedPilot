from datetime import date
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user, verify_password
from app.models.models import (
    Profile, Subject, TimetableRule, ClassOccurrence, ClassTopic,
    Attendance, Exam, StudyPlan, StudyTask, StudySession,
    Habit, HabitLog, RoutineSetting, Notification,
    GeneratedResource, SharedResource, PYQAnalysis,
    Friend, FriendRequest, WellbeingCheckIn
)
from app.schemas.schemas import (
    ResetAllDataRequest, DeleteAccountRequest, AccountActionResponse
)
from app.api.auth import DEFAULT_MBBS_SUBJECTS, DEFAULT_HABITS

router = APIRouter(prefix="/account", tags=["Account & Data Management"])


@router.post("/reset-timetable", response_model=AccountActionResponse)
async def reset_timetable_only(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Reset Timetable Only:
    - Deletes all timetable recurring rules for current_user
    - Deletes upcoming (date >= today) or unconfirmed/pending class occurrences
    - Preserves past marked attendance occurrences (detaching rule_id)
    - Preserves subjects, exams, study planner, and account credentials
    """
    rules_stmt = select(TimetableRule).filter(TimetableRule.user_id == current_user.id)
    rules = (await db.execute(rules_stmt)).scalars().all()
    deleted_rules_count = len(rules)
    for r in rules:
        await db.delete(r)

    occs_stmt = (
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.attendance))
        .filter(ClassOccurrence.user_id == current_user.id)
    )
    occurrences = (await db.execute(occs_stmt)).scalars().all()

    today = date.today()
    deleted_occs_count = 0
    preserved_occs_count = 0

    for occ in occurrences:
        att = occ.attendance
        is_pending_or_future = (
            occ.date >= today
            or occ.status == "scheduled"
            or not att
            or att.status == "not_marked"
        )
        if is_pending_or_future:
            await db.delete(occ)
            deleted_occs_count += 1
        else:
            occ.rule_id = None
            preserved_occs_count += 1

    await db.commit()

    return AccountActionResponse(
        success=True,
        message="Timetable entries and pending scheduled classes reset successfully.",
        details={
            "deleted_rules": deleted_rules_count,
            "deleted_occurrences": deleted_occs_count,
            "preserved_past_attendance": preserved_occs_count
        }
    )


@router.post("/reset-semester", response_model=AccountActionResponse)
async def reset_current_semester(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Reset Current Semester:
    - Clears current semester timetable rules
    - Clears unarchived class occurrences, attendance records, and class topics
    - Clears semester study tasks and study plans
    - Clears upcoming and current semester exams
    - Preserves historical archived semesters (is_archived == True)
    - Preserves account credentials and enrolled subjects
    """
    rules_stmt = select(TimetableRule).filter(TimetableRule.user_id == current_user.id)
    rules = (await db.execute(rules_stmt)).scalars().all()
    for r in rules:
        await db.delete(r)

    occs_stmt = select(ClassOccurrence).filter(
        ClassOccurrence.user_id == current_user.id,
        ClassOccurrence.is_archived == False
    )
    occs = (await db.execute(occs_stmt)).scalars().all()
    deleted_occs_count = len(occs)
    for occ in occs:
        await db.delete(occ)

    att_stmt = select(Attendance).filter(
        Attendance.user_id == current_user.id,
        Attendance.is_archived == False
    )
    atts = (await db.execute(att_stmt)).scalars().all()
    for a in atts:
        await db.delete(a)

    tasks_stmt = select(StudyTask).filter(StudyTask.user_id == current_user.id)
    tasks = (await db.execute(tasks_stmt)).scalars().all()
    for t in tasks:
        await db.delete(t)

    plans_stmt = select(StudyPlan).filter(StudyPlan.user_id == current_user.id)
    plans = (await db.execute(plans_stmt)).scalars().all()
    for p in plans:
        await db.delete(p)

    exams_stmt = select(Exam).filter(Exam.user_id == current_user.id)
    exams = (await db.execute(exams_stmt)).scalars().all()
    for e in exams:
        await db.delete(e)

    await db.commit()

    return AccountActionResponse(
        success=True,
        message="Current semester timetable, attendance, topics, study tasks, and exams cleared successfully.",
        details={
            "deleted_occurrences": deleted_occs_count,
            "deleted_tasks": len(tasks),
            "deleted_exams": len(exams)
        }
    )


@router.post("/reset-all", response_model=AccountActionResponse)
async def reset_all_medpilot_data(
    req: ResetAllDataRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Reset All MedPilot Data:
    - Keeps account login credentials (email, hashed password, name, college)
    - Completely wipes the user's academic workspace:
      timetable, occurrences, attendance, class topics, tasks, plans, sessions,
      exams, wellbeing history, habit logs, habits, routine settings, notifications,
      generated resources, flashcards, PYQ analyses, friend data, subjects.
    - Re-seeds default MBBS subjects & starter routine habits for a clean onboarding state.
    """
    if req.confirm_text.strip().upper() != "RESET":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation text must match 'RESET' exactly."
        )

    uid = current_user.id

    rules = (await db.execute(select(TimetableRule).filter(TimetableRule.user_id == uid))).scalars().all()
    for r in rules:
        await db.delete(r)

    occs = (await db.execute(select(ClassOccurrence).filter(ClassOccurrence.user_id == uid))).scalars().all()
    for o in occs:
        await db.delete(o)

    atts = (await db.execute(select(Attendance).filter(Attendance.user_id == uid))).scalars().all()
    for a in atts:
        await db.delete(a)

    tasks = (await db.execute(select(StudyTask).filter(StudyTask.user_id == uid))).scalars().all()
    for t in tasks:
        await db.delete(t)

    plans = (await db.execute(select(StudyPlan).filter(StudyPlan.user_id == uid))).scalars().all()
    for p in plans:
        await db.delete(p)

    sessions = (await db.execute(select(StudySession).filter(StudySession.user_id == uid))).scalars().all()
    for s in sessions:
        await db.delete(s)

    exams = (await db.execute(select(Exam).filter(Exam.user_id == uid))).scalars().all()
    for e in exams:
        await db.delete(e)

    wb = (await db.execute(select(WellbeingCheckIn).filter(WellbeingCheckIn.user_id == uid))).scalars().all()
    for w in wb:
        await db.delete(w)

    h_logs = (await db.execute(select(HabitLog).filter(HabitLog.user_id == uid))).scalars().all()
    for hl in h_logs:
        await db.delete(hl)

    habits = (await db.execute(select(Habit).filter(Habit.user_id == uid))).scalars().all()
    for h in habits:
        await db.delete(h)

    r_setting = (await db.execute(select(RoutineSetting).filter(RoutineSetting.user_id == uid))).scalars().first()
    if r_setting:
        await db.delete(r_setting)

    notifs = (await db.execute(select(Notification).filter(Notification.user_id == uid))).scalars().all()
    for n in notifs:
        await db.delete(n)

    resources = (await db.execute(select(GeneratedResource).filter(GeneratedResource.user_id == uid))).scalars().all()
    for res in resources:
        await db.delete(res)

    pyqs = (await db.execute(select(PYQAnalysis).filter(PYQAnalysis.user_id == uid))).scalars().all()
    for pyq in pyqs:
        await db.delete(pyq)

    friends = (await db.execute(select(Friend).filter((Friend.user_id == uid) | (Friend.friend_user_id == uid)))).scalars().all()
    for f in friends:
        await db.delete(f)

    f_reqs = (await db.execute(select(FriendRequest).filter((FriendRequest.sender_id == uid) | (FriendRequest.receiver_id == uid)))).scalars().all()
    for fr in f_reqs:
        await db.delete(fr)

    subjs = (await db.execute(select(Subject).filter(Subject.user_id == uid))).scalars().all()
    for sub in subjs:
        await db.delete(sub)

    await db.flush()

    for s in DEFAULT_MBBS_SUBJECTS:
        new_sub = Subject(
            user_id=current_user.id,
            name=s["name"],
            code=s["code"],
            color=s["color"],
            target_attendance=75.0,
            faculty="",
            academic_year=current_user.year_of_study or "MBBS 1st Year"
        )
        db.add(new_sub)

    for h in DEFAULT_HABITS:
        new_h = Habit(
            user_id=current_user.id,
            name=h["name"],
            category=h["category"],
            target_frequency="daily",
            selected_days="0,1,2,3,4,5,6",
            reminder_time="08:00" if h["category"] == "sleep" else "14:00",
            is_active=True
        )
        db.add(new_h)

    db.add(RoutineSetting(
        user_id=current_user.id,
        reminders_enabled=True,
        morning_time="08:00",
        afternoon_time="14:00",
        evening_time="20:00"
    ))

    await db.commit()

    return AccountActionResponse(
        success=True,
        message="All MedPilot academic data reset to clean onboarding state."
    )


@router.post("/delete", response_model=AccountActionResponse)
async def delete_account(
    req: DeleteAccountRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Permanent Account Deletion:
    - Strictly checks that confirm_text is 'DELETE'
    - Verifies account password if set
    - Permanently deletes Profile and all associated data via cascading delete
    - User is signed out after deletion
    """
    if req.confirm_text.strip().upper() != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation text must match 'DELETE' exactly."
        )

    if current_user.hashed_password:
        if not req.password or not verify_password(req.password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect account password. Deletion cancelled."
            )

    uid = current_user.id

    shared = (await db.execute(select(SharedResource).filter((SharedResource.sender_id == uid) | (SharedResource.receiver_id == uid)))).scalars().all()
    for s in shared:
        await db.delete(s)

    f_reqs = (await db.execute(select(FriendRequest).filter((FriendRequest.sender_id == uid) | (FriendRequest.receiver_id == uid)))).scalars().all()
    for fr in f_reqs:
        await db.delete(fr)

    friends = (await db.execute(select(Friend).filter((Friend.user_id == uid) | (Friend.friend_user_id == uid)))).scalars().all()
    for f in friends:
        await db.delete(f)

    await db.delete(current_user)
    await db.commit()

    return AccountActionResponse(
        success=True,
        message="Account and all associated records permanently deleted."
    )
