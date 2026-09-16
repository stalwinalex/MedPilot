from typing import List, Optional
from datetime import date, timedelta, datetime
from sqlalchemy import or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.models import TimetableRule, ClassOccurrence, ClassTopic, Attendance, Subject, Profile
from app.schemas.schemas import (
    ClassOccurrenceCreate, ClassOccurrenceUpdate, ClassSwapRequest,
    ClassRescheduleRequest, TimetableRuleUpdate
)


class TimetableService:
    @staticmethod
    async def cleanup_invalid_past_occurrences(
        db: AsyncSession,
        user_id: str
    ) -> int:
        """
        Removes only automatically generated recurring occurrences that predate
        the timetable rule's effective_from or profile timetable_start_date,
        where the student has NOT marked attendance and no custom topics/notes exist.
        Preserves all legitimate intentional history.
        """
        prof_stmt = select(Profile).filter(Profile.id == user_id)
        profile = (await db.execute(prof_stmt)).scalars().first()
        profile_start = profile.timetable_start_date if profile else None

        rule_stmt = select(TimetableRule).filter(TimetableRule.user_id == user_id)
        rules = {r.id: r for r in (await db.execute(rule_stmt)).scalars().all()}

        occ_stmt = (
            select(ClassOccurrence)
            .options(
                selectinload(ClassOccurrence.attendance),
                selectinload(ClassOccurrence.topics)
            )
            .filter(
                ClassOccurrence.user_id == user_id,
                ClassOccurrence.rule_id.isnot(None),
                ClassOccurrence.is_extra_class == False
            )
        )
        occurrences = (await db.execute(occ_stmt)).scalars().all()

        deleted_count = 0
        for occ in occurrences:
            rule = rules.get(occ.rule_id)
            effective_start = rule.effective_from if rule else None
            if not effective_start and profile_start:
                effective_start = profile_start
            if not effective_start and rule and rule.created_at:
                effective_start = rule.created_at.date()
            if not effective_start:
                effective_start = date.today()

            if occ.date < effective_start:
                is_unmarked = not occ.attendance or occ.attendance.status == "not_marked"
                has_no_topics = not occ.topics or len(occ.topics) == 0
                has_no_notes = not occ.notes or occ.notes.strip() == ""

                if is_unmarked and has_no_topics and has_no_notes:
                    await db.delete(occ)
                    deleted_count += 1

        if deleted_count > 0:
            await db.commit()
        return deleted_count

    @staticmethod
    async def ensure_occurrences_generated(
        db: AsyncSession,
        user_id: str,
        start_date: date,
        end_date: date
    ):
        """
        Generates individual occurrences from recurring rules for dates where
        an occurrence linked to the rule does not already exist.
        STRICT RULE: Recurring classes must NEVER generate occurrences before
        the rule's effective_from or the timetable's effective_start_date.
        """
        # Fetch user profile to get global timetable_start_date if any
        prof_stmt = select(Profile).filter(Profile.id == user_id)
        profile = (await db.execute(prof_stmt)).scalars().first()
        profile_start = profile.timetable_start_date if profile else None

        # Fetch all active recurring rules for this user
        rule_stmt = select(TimetableRule).filter(
            TimetableRule.user_id == user_id,
            TimetableRule.is_active == True
        )
        rules = (await db.execute(rule_stmt)).scalars().all()
        if not rules:
            return

        current = start_date
        while current <= end_date:
            weekday = current.weekday()  # 0=Monday, 6=Sunday
            day_rules = [r for r in rules if r.day_of_week == weekday]

            for rule in day_rules:
                # Determine effective start date for this rule
                effective_start = rule.effective_from
                if not effective_start and profile_start:
                    effective_start = profile_start
                if not effective_start and rule.created_at:
                    effective_start = rule.created_at.date()
                if not effective_start:
                    effective_start = date.today()

                # STRICT RULE: Never generate occurrences before effective_start
                if current < effective_start:
                    continue

                # Check if an occurrence already exists for this rule or same subject/date/time
                occ_stmt = select(ClassOccurrence).filter(
                    ClassOccurrence.user_id == user_id,
                    or_(
                        ClassOccurrence.rule_id == rule.id,
                        and_(
                            ClassOccurrence.subject_id == rule.subject_id,
                            ClassOccurrence.start_time == rule.start_time,
                            ClassOccurrence.end_time == rule.end_time
                        )
                    ),
                    or_(
                        ClassOccurrence.date == current,
                        ClassOccurrence.original_date == current
                    )
                )
                existing = (await db.execute(occ_stmt)).scalars().first()
                if existing:
                    if not existing.rule_id:
                        existing.rule_id = rule.id
                    continue

                new_occ = ClassOccurrence(
                    user_id=user_id,
                    rule_id=rule.id,
                    subject_id=rule.subject_id,
                    date=current,
                    start_time=rule.start_time,
                    end_time=rule.end_time,
                    faculty=rule.faculty,
                    room=rule.room,
                    status="scheduled",
                    is_extra_class=False
                )
                db.add(new_occ)
                await db.flush()

                # Create default pending attendance record
                att = Attendance(
                    user_id=user_id,
                    occurrence_id=new_occ.id,
                    status="not_marked"
                )
                db.add(att)

            current += timedelta(days=1)
        
        await db.commit()

    @staticmethod
    async def get_occurrences_for_range(
        db: AsyncSession,
        user_id: str,
        start_date: date,
        end_date: date
    ) -> List[ClassOccurrence]:
        await TimetableService.cleanup_invalid_past_occurrences(db, user_id)
        await TimetableService.ensure_occurrences_generated(db, user_id, start_date, end_date)

        stmt = (
            select(ClassOccurrence)
            .options(
                selectinload(ClassOccurrence.subject),
                selectinload(ClassOccurrence.topics),
                selectinload(ClassOccurrence.attendance)
            )
            .filter(
                ClassOccurrence.user_id == user_id,
                ClassOccurrence.date >= start_date,
                ClassOccurrence.date <= end_date
            )
            .order_by(ClassOccurrence.date.asc(), ClassOccurrence.start_time.asc())
        )
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def add_extra_class(
        db: AsyncSession,
        user_id: str,
        data: ClassOccurrenceCreate
    ) -> ClassOccurrence:
        new_occ = ClassOccurrence(
            user_id=user_id,
            rule_id=None,
            subject_id=data.subject_id,
            date=data.date,
            start_time=data.start_time,
            end_time=data.end_time,
            faculty=data.faculty or "",
            room=data.room or "",
            status="scheduled",
            is_extra_class=True,
            notes=data.notes or ""
        )
        db.add(new_occ)
        await db.flush()

        # Add topics if provided
        if data.topics:
            for idx, topic_title in enumerate(data.topics):
                ct = ClassTopic(
                    occurrence_id=new_occ.id,
                    title=topic_title,
                    order_index=idx
                )
                db.add(ct)

        # Initialize attendance
        att = Attendance(
            user_id=user_id,
            occurrence_id=new_occ.id,
            status="not_marked"
        )
        db.add(att)
        await db.commit()
        await db.refresh(new_occ)
        return new_occ

    @staticmethod
    async def reschedule_class(
        db: AsyncSession,
        user_id: str,
        req: ClassRescheduleRequest
    ) -> ClassOccurrence:
        stmt = (
            select(ClassOccurrence)
            .options(selectinload(ClassOccurrence.attendance))
            .filter(ClassOccurrence.id == req.occurrence_id, ClassOccurrence.user_id == user_id)
        )
        occ = (await db.execute(stmt)).scalars().first()
        if not occ:
            raise ValueError("Class occurrence not found")

        # Record original timing if not already set
        if not occ.original_date:
            occ.original_date = occ.date
            occ.original_start_time = occ.start_time

        occ.date = req.new_date
        occ.start_time = req.new_start_time
        occ.end_time = req.new_end_time
        occ.status = "rescheduled"
        if req.notes:
            occ.notes = f"{occ.notes} | Rescheduled: {req.notes}".strip(" | ")

        await db.commit()
        await db.refresh(occ)
        return occ

    @staticmethod
    async def swap_classes(
        db: AsyncSession,
        user_id: str,
        req: ClassSwapRequest
    ):
        stmt1 = select(ClassOccurrence).filter(ClassOccurrence.id == req.occurrence_id_1, ClassOccurrence.user_id == user_id)
        stmt2 = select(ClassOccurrence).filter(ClassOccurrence.id == req.occurrence_id_2, ClassOccurrence.user_id == user_id)
        
        occ1 = (await db.execute(stmt1)).scalars().first()
        occ2 = (await db.execute(stmt2)).scalars().first()

        if not occ1 or not occ2:
            raise ValueError("One or both class occurrences not found")

        # Swap subject, faculty, room and notes
        occ1.subject_id, occ2.subject_id = occ2.subject_id, occ1.subject_id
        occ1.faculty, occ2.faculty = occ2.faculty, occ1.faculty
        occ1.room, occ2.room = occ2.room, occ1.room

        await db.commit()
        return occ1, occ2

    @staticmethod
    async def update_rule_and_future_occurrences(
        db: AsyncSession,
        user_id: str,
        rule_id: str,
        data: TimetableRuleUpdate
    ) -> TimetableRule:
        rule_stmt = select(TimetableRule).filter(
            TimetableRule.id == rule_id,
            TimetableRule.user_id == user_id
        )
        rule = (await db.execute(rule_stmt)).scalars().first()
        if not rule:
            raise ValueError("Timetable rule not found")

        old_day = rule.day_of_week
        if data.subject_id is not None:
            rule.subject_id = data.subject_id
        if data.day_of_week is not None:
            rule.day_of_week = data.day_of_week
        if data.start_time is not None:
            rule.start_time = data.start_time
        if data.end_time is not None:
            rule.end_time = data.end_time
        if data.faculty is not None:
            rule.faculty = data.faculty
        if data.room is not None:
            rule.room = data.room
        if data.is_active is not None:
            rule.is_active = data.is_active
        if data.effective_from is not None:
            rule.effective_from = data.effective_from

        if data.update_future_occurrences:
            threshold_date = data.start_from_date or date.today()
            # Find occurrences tied to this rule from threshold date that are scheduled or cancelled
            fut_stmt = (
                select(ClassOccurrence)
                .options(selectinload(ClassOccurrence.attendance))
                .filter(
                    ClassOccurrence.user_id == user_id,
                    ClassOccurrence.rule_id == rule.id,
                    ClassOccurrence.date >= threshold_date,
                    ClassOccurrence.status.in_(["scheduled", "cancelled"])
                )
            )
            fut_occs = (await db.execute(fut_stmt)).scalars().all()
            for occ in fut_occs:
                # If attendance was marked present/absent, leave history untouched
                if occ.attendance and occ.attendance.status in ["present", "absent"]:
                    continue

                if data.day_of_week is not None and data.day_of_week != old_day:
                    day_diff = data.day_of_week - occ.date.weekday()
                    occ.date = occ.date + timedelta(days=day_diff)

                if data.subject_id is not None:
                    occ.subject_id = data.subject_id
                if data.start_time is not None:
                    occ.start_time = data.start_time
                if data.end_time is not None:
                    occ.end_time = data.end_time
                if data.faculty is not None:
                    occ.faculty = data.faculty
                if data.room is not None:
                    occ.room = data.room

        await db.commit()
        await db.refresh(rule)
        return rule

