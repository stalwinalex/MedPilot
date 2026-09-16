from datetime import datetime, date, time, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.models import (
    ClassOccurrence, Exam, StudyTask, StudySession, Habit, HabitLog,
    Subject, Notification, GeneratedResource, Profile, WellbeingCheckIn
)
from app.services.attendance_service import AttendanceService
from app.services.timetable_service import TimetableService


class AgentTools:
    @staticmethod
    def get_current_time() -> Dict[str, Any]:
        now = datetime.now()
        return {
            "current_time": now.strftime("%I:%M %p"),
            "current_date": now.strftime("%Y-%m-%d"),
            "day_of_week": now.strftime("%A"),
            "iso": now.isoformat()
        }

    @staticmethod
    async def get_today_timetable(db: AsyncSession, user_id: str, target_date: Optional[date] = None) -> List[Dict[str, Any]]:
        d = target_date or date.today()
        occurrences = await TimetableService.get_occurrences_for_range(db, user_id, d, d)
        results = []
        for occ in occurrences:
            topics = [t.title for t in occ.topics]
            att_status = occ.attendance.status if occ.attendance else "not_marked"
            results.append({
                "occurrence_id": occ.id,
                "subject": occ.subject.name if occ.subject else "Unknown",
                "start_time": occ.start_time.strftime("%I:%M %p"),
                "end_time": occ.end_time.strftime("%I:%M %p"),
                "status": occ.status,
                "faculty": occ.faculty,
                "room": occ.room,
                "topics": topics,
                "attendance_status": att_status,
                "is_extra_class": occ.is_extra_class
            })
        return results

    @staticmethod
    async def get_upcoming_classes(db: AsyncSession, user_id: str, hours_ahead: int = 6) -> List[Dict[str, Any]]:
        today = date.today()
        now_time = datetime.now().time()
        occurrences = await TimetableService.get_occurrences_for_range(db, user_id, today, today)
        upcoming = []
        for occ in occurrences:
            if occ.status != "cancelled" and occ.start_time >= now_time:
                upcoming.append({
                    "occurrence_id": occ.id,
                    "subject": occ.subject.name if occ.subject else "",
                    "start_time": occ.start_time.strftime("%I:%M %p"),
                    "room": occ.room,
                    "faculty": occ.faculty,
                    "topics": [t.title for t in occ.topics]
                })
        return upcoming

    @staticmethod
    async def get_attendance(db: AsyncSession, user_id: str) -> Dict[str, Any]:
        summary = await AttendanceService.get_overall_attendance_summary(db, user_id)
        return summary.model_dump(mode="json")

    @staticmethod
    async def get_upcoming_exams(db: AsyncSession, user_id: str, days_ahead: int = 30) -> List[Dict[str, Any]]:
        today = date.today()
        max_date = today + timedelta(days=days_ahead)
        stmt = (
            select(Exam)
            .options(selectinload(Exam.subject))
            .filter(Exam.user_id == user_id, Exam.exam_date >= today, Exam.exam_date <= max_date)
            .order_by(Exam.exam_date.asc())
        )
        exams = (await db.execute(stmt)).scalars().all()
        results = []
        for e in exams:
            days_left = (e.exam_date - today).days
            results.append({
                "exam_id": e.id,
                "subject": e.subject.name if e.subject else "",
                "name": e.name,
                "date": e.exam_date.strftime("%Y-%m-%d"),
                "days_remaining": days_left,
                "prep_status": e.prep_status,
                "important_topics": e.important_topics or []
            })
        return results

    @staticmethod
    async def get_study_tasks(db: AsyncSession, user_id: str, target_date: Optional[date] = None) -> List[Dict[str, Any]]:
        d = target_date or date.today()
        stmt = (
            select(StudyTask)
            .options(selectinload(StudyTask.subject), selectinload(StudyTask.exam))
            .filter(StudyTask.user_id == user_id, StudyTask.scheduled_date == d)
            .order_by(StudyTask.is_completed.asc(), StudyTask.order_index.asc())
        )
        tasks = (await db.execute(stmt)).scalars().all()
        results = []
        for t in tasks:
            results.append({
                "task_id": t.id,
                "title": t.title,
                "priority": t.priority,
                "estimated_minutes": t.estimated_minutes,
                "is_completed": t.is_completed,
                "subject": t.subject.name if t.subject else None
            })
        return results

    @staticmethod
    async def get_habits_status(db: AsyncSession, user_id: str, target_date: Optional[date] = None) -> List[Dict[str, Any]]:
        d = target_date or date.today()
        stmt = select(Habit).filter(Habit.user_id == user_id, Habit.is_active == True)
        habits = (await db.execute(stmt)).scalars().all()

        log_stmt = select(HabitLog).filter(HabitLog.user_id == user_id, HabitLog.date == d)
        logs = (await db.execute(log_stmt)).scalars().all()
        log_map = {l.habit_id: l.status for l in logs}

        results = []
        for h in habits:
            results.append({
                "habit_id": h.id,
                "name": h.name,
                "category": h.category,
                "status": log_map.get(h.id, "missed")  # missed / completed
            })
        return results

    @staticmethod
    async def get_wellbeing_status(db: AsyncSession, user_id: str, target_date: Optional[date] = None) -> Dict[str, Any]:
        d = target_date or date.today()
        stmt = select(WellbeingCheckIn).filter(
            WellbeingCheckIn.user_id == user_id,
            WellbeingCheckIn.date == d
        )
        wb = (await db.execute(stmt)).scalars().first()
        if not wb:
            return {"status": "pending", "mood": None}
        return {"status": wb.status, "mood": wb.mood}

    @staticmethod
    async def get_available_study_time(db: AsyncSession, user_id: str, target_date: Optional[date] = None) -> Dict[str, Any]:
        d = target_date or date.today()
        occurrences = await TimetableService.get_occurrences_for_range(db, user_id, d, d)
        scheduled_minutes = 0
        for occ in occurrences:
            if occ.status != "cancelled":
                # calculate class duration
                start_dt = datetime.combine(d, occ.start_time)
                end_dt = datetime.combine(d, occ.end_time)
                scheduled_minutes += int((end_dt - start_dt).total_seconds() / 60)

        # Assuming active day 8:00 AM to 10:00 PM = 14 hours = 840 mins
        total_day_minutes = 840
        free_minutes = max(0, total_day_minutes - scheduled_minutes - 180) # minus 3 hours for meals/breaks
        return {
            "scheduled_class_minutes": scheduled_minutes,
            "estimated_free_minutes": free_minutes,
            "estimated_free_hours": round(free_minutes / 60.0, 1)
        }

    @staticmethod
    async def create_study_task(
        db: AsyncSession,
        user_id: str,
        title: str,
        subject_id: Optional[str] = None,
        priority: str = "medium",
        estimated_minutes: int = 45,
        scheduled_date: Optional[date] = None
    ) -> Dict[str, Any]:
        d = scheduled_date or date.today()
        task = StudyTask(
            user_id=user_id,
            subject_id=subject_id,
            title=title,
            priority=priority,
            estimated_minutes=estimated_minutes,
            scheduled_date=d
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return {"status": "created", "task_id": task.id, "title": task.title}

    @staticmethod
    def search_medical_references(query: str) -> List[str]:
        """
        Returns authoritative, subject-appropriate reference textbook suggestions.
        Clearly designated as suggested academic reading for the requested topic.
        """
        q_lower = query.lower()

        # Biochemistry
        if any(w in q_lower for w in ["glycolysis", "biochem", "enzyme", "metabolism", "cycle", "glucose", "atp", "vitamin", "lipid", "protein synthesis"]):
            return [
                "Harper's Illustrated Biochemistry, 32nd Ed. (Metabolic Pathways)",
                "Vasudevan Textbook of Biochemistry for Medical Students, 10th Ed."
            ]

        # Pathology
        if any(w in q_lower for w in ["apoptosis", "necrosis", "patholog", "cell injury", "inflammation", "neoplasia", "tumor", "infarct", "granuloma"]):
            return [
                "Robbins & Cotran Pathologic Basis of Disease, 10th Ed. (Cellular Pathology)",
                "Harsh Mohan Textbook of Pathology, 8th Ed."
            ]

        # Anatomy
        if any(w in q_lower for w in ["limb", "plexus", "artery", "nerve", "bone", "muscle", "anatomy", "brachial", "triangle", "fossa", "foramen"]):
            return [
                "Gray's Anatomy for Students, 4th Ed. (Regional Anatomy)",
                "B.D. Chaurasia's Human Anatomy, Regional & Applied (Vol 1-3)"
            ]

        # Pharmacology
        if any(w in q_lower for w in ["drug", "pharm", "blocker", "agonist", "antagonist", "receptor", "toxicity", "adverse", "dose"]):
            return [
                "KD Tripathi's Essentials of Medical Pharmacology, 8th Ed.",
                "Goodman & Gilman's The Pharmacological Basis of Therapeutics, 14th Ed."
            ]

        # Physiology
        if any(w in q_lower for w in ["physio", "action potential", "cardiac cycle", "blood pressure", "nephron", "gfr", "ventilation"]):
            return [
                "Guyton and Hall Textbook of Medical Physiology, 14th Ed.",
                "Ganong's Review of Medical Physiology, 26th Ed."
            ]

        # Clinical / Medicine
        return [
            "Harrison's Principles of Internal Medicine, 21st Ed.",
            "Standard MBBS Curriculum Competency Guidelines"
        ]
