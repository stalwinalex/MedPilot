from typing import List, Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Profile, Habit, HabitLog, RoutineSetting, WellbeingCheckIn
from app.schemas.schemas import (
    HabitCreate,
    HabitUpdate,
    HabitResponse,
    HabitLogCreate,
    HabitLogResponse,
    RoutineSettingUpdate,
    RoutineSettingResponse,
    WeeklySummaryResponse,
    WeeklySummaryDay,
    WellbeingCheckInCreate,
    WellbeingCheckInResponse,
)

router = APIRouter(prefix="/habits", tags=["Routine & Wellbeing"])


@router.get("/")
async def get_habits(
    target_date: Optional[date] = None,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    d = target_date or date.today()
    day_int_str = str(d.weekday())

    # Only active, non-paused routines for today
    stmt = select(Habit).filter(
        Habit.user_id == current_user.id,
        Habit.is_active == True,
        Habit.is_paused == False
    ).order_by(Habit.order_index.asc(), Habit.created_at.asc())
    habits = (await db.execute(stmt)).scalars().all()

    # Filter for day of week
    day_habits = []
    for h in habits:
        days = [x.strip() for x in (h.selected_days or "").split(",") if x.strip()]
        if not days or day_int_str in days:
            day_habits.append(h)

    # Check today's completion
    log_stmt = select(HabitLog).filter(HabitLog.user_id == current_user.id, HabitLog.date == d)
    logs = (await db.execute(log_stmt)).scalars().all()
    log_map = {l.habit_id: l.status for l in logs}
    notes_map = {l.habit_id: (l.notes or "") for l in logs}

    results = []
    for h in day_habits:
        status = log_map.get(h.id, "missed")
        today_notes = notes_map.get(h.id, "")
        results.append({
            "id": h.id,
            "user_id": h.user_id,
            "name": h.name,
            "category": h.category,
            "target_frequency": h.target_frequency,
            "selected_days": h.selected_days or "0,1,2,3,4,5,6",
            "reminder_time": h.reminder_time or "",
            "note": h.note or "",
            "is_paused": h.is_paused,
            "order_index": h.order_index,
            "is_active": h.is_active,
            "created_at": h.created_at,
            "today_completed": (status == "completed"),
            "today_status": status,
            "today_notes": today_notes,
            "date": d
        })
    return results


@router.get("/all")
async def get_all_habits(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Habit).filter(
        Habit.user_id == current_user.id,
        Habit.is_active == True
    ).order_by(Habit.is_paused.asc(), Habit.order_index.asc(), Habit.created_at.asc())
    habits = (await db.execute(stmt)).scalars().all()
    return habits


@router.post("/", response_model=HabitResponse)
async def create_habit(
    data: HabitCreate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    habit = Habit(
        user_id=current_user.id,
        name=data.name.strip(),
        category=data.category or "routine",
        target_frequency=data.target_frequency or "daily",
        selected_days=data.selected_days if data.selected_days is not None else "0,1,2,3,4,5,6",
        reminder_time=data.reminder_time or "",
        note=data.note or "",
        is_paused=bool(data.is_paused),
        order_index=data.order_index or 0,
        is_active=True
    )
    db.add(habit)
    await db.commit()
    await db.refresh(habit)
    return habit


@router.post("/log", response_model=HabitLogResponse)
async def log_habit_status(
    req: HabitLogCreate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    valid_statuses = ["completed", "partial", "skipped", "missed"]
    if req.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Status must be one of: {', '.join(valid_statuses)}"
        )

    h_stmt = select(Habit).filter(Habit.id == req.habit_id, Habit.user_id == current_user.id)
    habit = (await db.execute(h_stmt)).scalars().first()
    if not habit:
        raise HTTPException(status_code=404, detail="Routine not found")

    stmt = select(HabitLog).filter(
        HabitLog.habit_id == req.habit_id,
        HabitLog.user_id == current_user.id,
        HabitLog.date == req.date
    )
    log_entry = (await db.execute(stmt)).scalars().first()

    if not log_entry:
        log_entry = HabitLog(
            user_id=current_user.id,
            habit_id=req.habit_id,
            date=req.date,
            status=req.status,
            notes=req.notes or ""
        )
        db.add(log_entry)
    else:
        log_entry.status = req.status
        if req.notes is not None:
            log_entry.notes = req.notes

    await db.commit()
    await db.refresh(log_entry)
    return log_entry


@router.get("/weekly-summary", response_model=WeeklySummaryResponse)
async def get_weekly_summary(
    target_date: Optional[date] = None,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    end_date = target_date or date.today()
    start_date = end_date - timedelta(days=6)

    # Get all active habits
    stmt = select(Habit).filter(Habit.user_id == current_user.id, Habit.is_active == True)
    habits = (await db.execute(stmt)).scalars().all()

    # Get all logs for the 7-day period
    log_stmt = select(HabitLog).filter(
        HabitLog.user_id == current_user.id,
        HabitLog.date >= start_date,
        HabitLog.date <= end_date
    )
    logs = (await db.execute(log_stmt)).scalars().all()
    status_map = {(l.habit_id, l.date): l.status for l in logs}

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    days_data = []
    total_completed = 0
    total_partial = 0
    total_skipped = 0
    total_missed = 0
    total_routines = 0

    for i in range(7):
        curr_d = start_date + timedelta(days=i)
        w = curr_d.weekday()
        w_str = str(w)

        scheduled_habits = [
            h for h in habits
            if (not h.is_paused or (h.is_paused and (h.id, curr_d) in status_map)) and
               (w_str in [x.strip() for x in (h.selected_days or "").split(",") if x.strip()])
        ]
        total_for_day = len(scheduled_habits)
        completed_for_day = sum(1 for h in scheduled_habits if status_map.get((h.id, curr_d)) == "completed")
        partial_for_day = sum(1 for h in scheduled_habits if status_map.get((h.id, curr_d)) == "partial")
        skipped_for_day = sum(1 for h in scheduled_habits if status_map.get((h.id, curr_d)) == "skipped")
        recorded_count = completed_for_day + partial_for_day + skipped_for_day
        missed_for_day = max(0, total_for_day - recorded_count)

        # Exclude skipped routines from completion calculations:
        active_denom = max(0, total_for_day - skipped_for_day)
        effective_score = completed_for_day + (0.5 * partial_for_day)
        pct = round((effective_score / active_denom * 100), 1) if active_denom > 0 else 0.0

        days_data.append(WeeklySummaryDay(
            date=curr_d,
            day_name=day_names[w],
            completed_count=completed_for_day,
            partial_count=partial_for_day,
            skipped_count=skipped_for_day,
            missed_count=missed_for_day,
            total_count=total_for_day,
            percentage=pct
        ))
        total_completed += completed_for_day
        total_partial += partial_for_day
        total_skipped += skipped_for_day
        total_missed += missed_for_day
        total_routines += total_for_day

    active_total = max(0, total_routines - total_skipped)
    total_effective = total_completed + (0.5 * total_partial)
    overall_pct = round((total_effective / active_total * 100), 1) if active_total > 0 else 0.0

    return WeeklySummaryResponse(
        days=days_data,
        total_completed=total_completed,
        total_partial=total_partial,
        total_skipped=total_skipped,
        total_missed=total_missed,
        total_routines=total_routines,
        overall_percentage=overall_pct
    )


@router.get("/history")
async def get_routine_history(
    days: int = 14,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    h_stmt = select(Habit).filter(Habit.user_id == current_user.id)
    habits = (await db.execute(h_stmt)).scalars().all()
    habit_map = {h.id: h for h in habits}

    stmt = select(HabitLog).filter(
        HabitLog.user_id == current_user.id,
        HabitLog.date >= start_date,
        HabitLog.date <= end_date
    ).order_by(HabitLog.date.desc())
    logs = (await db.execute(stmt)).scalars().all()

    history = []
    for l in logs:
        habit = habit_map.get(l.habit_id)
        if habit:
            history.append({
                "id": l.id,
                "habit_id": l.habit_id,
                "habit_name": habit.name,
                "category": habit.category,
                "date": l.date,
                "status": l.status,
                "notes": l.notes or ""
            })
    return history


@router.get("/settings", response_model=RoutineSettingResponse)
async def get_routine_settings(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(RoutineSetting).filter(RoutineSetting.user_id == current_user.id)
    setting = (await db.execute(stmt)).scalars().first()
    if not setting:
        setting = RoutineSetting(user_id=current_user.id)
        db.add(setting)
        await db.commit()
        await db.refresh(setting)
    return setting


@router.put("/settings", response_model=RoutineSettingResponse)
async def update_routine_settings(
    req: RoutineSettingUpdate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(RoutineSetting).filter(RoutineSetting.user_id == current_user.id)
    setting = (await db.execute(stmt)).scalars().first()
    if not setting:
        setting = RoutineSetting(user_id=current_user.id)
        db.add(setting)

    for field, val in req.model_dump(exclude_unset=True).items():
        setattr(setting, field, val)

    await db.commit()
    await db.refresh(setting)
    return setting


# Parameterized routes placed AFTER fixed path routes
@router.put("/{habit_id}", response_model=HabitResponse)
async def update_habit(
    habit_id: str,
    data: HabitUpdate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Habit).filter(Habit.id == habit_id, Habit.user_id == current_user.id)
    habit = (await db.execute(stmt)).scalars().first()
    if not habit:
        raise HTTPException(status_code=404, detail="Routine not found")

    if data.name is not None:
        habit.name = data.name.strip()
    if data.category is not None:
        habit.category = data.category
    if data.target_frequency is not None:
        habit.target_frequency = data.target_frequency
    if data.selected_days is not None:
        habit.selected_days = data.selected_days
    if data.reminder_time is not None:
        habit.reminder_time = data.reminder_time
    if data.note is not None:
        habit.note = data.note
    if data.is_paused is not None:
        habit.is_paused = data.is_paused
    if data.order_index is not None:
        habit.order_index = data.order_index
    if data.is_active is not None:
        habit.is_active = data.is_active

    await db.commit()
    await db.refresh(habit)
    return habit


@router.post("/{habit_id}/toggle-pause", response_model=HabitResponse)
async def toggle_pause_habit(
    habit_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Habit).filter(Habit.id == habit_id, Habit.user_id == current_user.id)
    habit = (await db.execute(stmt)).scalars().first()
    if not habit:
        raise HTTPException(status_code=404, detail="Routine not found")
    habit.is_paused = not habit.is_paused
    await db.commit()
    await db.refresh(habit)
    return habit


@router.delete("/{habit_id}")
async def delete_habit(
    habit_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Habit).filter(Habit.id == habit_id, Habit.user_id == current_user.id)
    habit = (await db.execute(stmt)).scalars().first()
    if not habit:
        raise HTTPException(status_code=404, detail="Routine not found")
    await db.delete(habit)
    await db.commit()
    return {"message": "Routine deleted successfully"}


@router.get("/wellbeing/today", response_model=WellbeingCheckInResponse)
async def get_today_wellbeing_checkin(
    target_date: Optional[date] = None,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns today's wellbeing check-in. If not yet answered or skipped,
    returns status="pending".
    """
    d = target_date or date.today()
    stmt = select(WellbeingCheckIn).filter(
        WellbeingCheckIn.user_id == current_user.id,
        WellbeingCheckIn.date == d
    )
    record = (await db.execute(stmt)).scalars().first()
    if not record:
        return WellbeingCheckInResponse(
            id=None,
            user_id=current_user.id,
            date=d,
            status="pending",
            mood=None,
            notes="",
            created_at=None
        )
    return record


@router.post("/wellbeing", response_model=WellbeingCheckInResponse)
async def record_wellbeing_checkin(
    data: WellbeingCheckInCreate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Submits or updates daily wellbeing check-in (after 4 PM local time).
    status: 'answered' or 'skipped'
    mood: 'great', 'good', 'okay', 'tired', 'stressful' (if answered)
    Once answered or skipped, preserved in DB for the day.
    """
    if data.status not in ["answered", "skipped"]:
        raise HTTPException(status_code=400, detail="Status must be 'answered' or 'skipped'")

    valid_moods = ["great", "good", "okay", "tired", "stressful"]
    if data.status == "answered":
        if not data.mood or data.mood.lower() not in valid_moods:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mood. Must be one of: {', '.join(valid_moods)}"
            )
        clean_mood = data.mood.lower()
    else:
        clean_mood = None

    d = data.date or date.today()
    stmt = select(WellbeingCheckIn).filter(
        WellbeingCheckIn.user_id == current_user.id,
        WellbeingCheckIn.date == d
    )
    record = (await db.execute(stmt)).scalars().first()

    if not record:
        record = WellbeingCheckIn(
            user_id=current_user.id,
            date=d,
            status=data.status,
            mood=clean_mood,
            notes=data.notes or ""
        )
        db.add(record)
    else:
        record.status = data.status
        record.mood = clean_mood
        if data.notes is not None:
            record.notes = data.notes

    await db.commit()
    await db.refresh(record)
    return record

