import math
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.models import ClassOccurrence, Attendance, Subject, Profile, TimetableRule
from app.schemas.schemas import (
    SubjectAttendanceSummary, OverallAttendanceSummary,
    ClassOccurrenceResponse, ClassSlotAttendance
)


class AttendanceService:
    @staticmethod
    async def get_subject_attendance_summary(
        db: AsyncSession,
        user_id: str,
        subject: Subject,
        target_percentage: float
    ) -> SubjectAttendanceSummary:
        # Fetch all occurrences for this user and subject with their attendance record, topics, and subject
        stmt = (
            select(ClassOccurrence)
            .options(
                selectinload(ClassOccurrence.attendance),
                selectinload(ClassOccurrence.topics),
                selectinload(ClassOccurrence.subject)
            )
            .filter(
                ClassOccurrence.user_id == user_id,
                ClassOccurrence.subject_id == subject.id
            )
            .order_by(ClassOccurrence.date.desc(), ClassOccurrence.start_time.desc())
        )
        result = await db.execute(stmt)
        occurrences = result.scalars().all()

        # Fetch active timetable rules for this user and subject to compute slot-level attendance
        rule_stmt = select(TimetableRule).filter(
            TimetableRule.user_id == user_id,
            TimetableRule.subject_id == subject.id,
            TimetableRule.is_active == True
        )
        rules = (await db.execute(rule_stmt)).scalars().all()

        DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        slots_map: Dict[str, Dict[str, Any]] = {}
        for r in rules:
            start_str = r.start_time.strftime("%H:%M") if r.start_time else ""
            end_str = r.end_time.strftime("%H:%M") if r.end_time else ""
            day_name = DAY_NAMES[r.day_of_week] if 0 <= r.day_of_week < 7 else f"Day {r.day_of_week}"
            slots_map[r.id] = {
                "rule_id": r.id,
                "day_of_week": r.day_of_week,
                "day_name": day_name,
                "start_time": start_str,
                "end_time": end_str,
                "room": r.room or "",
                "faculty": r.faculty or "",
                "classes_conducted": 0,
                "classes_attended": 0,
                "classes_missed": 0,
                "classes_cancelled": 0,
                "unconfirmed_classes": 0,
                "current_percentage": None
            }

        conducted = 0
        attended = 0
        missed = 0
        cancelled = 0
        unconfirmed = 0

        now_date = date.today()
        now_time = datetime.now().time()
        serialized_classes: List[ClassOccurrenceResponse] = []

        for occ in occurrences:
            # Skip archived occurrences or occurrences with archived attendance
            if getattr(occ, "is_archived", False) or (occ.attendance and getattr(occ.attendance, "is_archived", False)):
                continue

            # Skip occurrences before rule's effective_from or timetable start date if un-marked
            rule_obj = next((r for r in rules if r.id == occ.rule_id), None)
            rule_start = rule_obj.effective_from if rule_obj else None
            if not rule_start and rule_obj and rule_obj.created_at:
                rule_start = rule_obj.created_at.date()
            if rule_start and occ.date < rule_start and (not occ.attendance or occ.attendance.status == "not_marked"):
                continue

            # Serialize occurrence for individual class attendance list
            serialized_classes.append(ClassOccurrenceResponse.model_validate(occ))

            # Rule: Cancelled classes MUST NEVER count as conducted or reduce attendance percentage
            is_cancelled = (occ.status == "cancelled" or (occ.attendance and occ.attendance.status == "cancelled"))
            has_ended = occ.date < now_date or (occ.date == now_date and occ.end_time <= now_time)
            att = occ.attendance

            # Find matching slot for slot-level attendance
            target_slot_id = occ.rule_id
            if not target_slot_id:
                occ_day = occ.date.weekday()
                for r in rules:
                    if r.day_of_week == occ_day and r.start_time == occ.start_time and r.end_time == occ.end_time:
                        target_slot_id = r.id
                        break

            if not target_slot_id:
                target_slot_id = "extra"
                if "extra" not in slots_map:
                    slots_map["extra"] = {
                        "rule_id": None,
                        "day_of_week": None,
                        "day_name": "Special / Extra Class",
                        "start_time": "Varies",
                        "end_time": "Varies",
                        "room": "",
                        "faculty": "",
                        "classes_conducted": 0,
                        "classes_attended": 0,
                        "classes_missed": 0,
                        "classes_cancelled": 0,
                        "unconfirmed_classes": 0,
                        "current_percentage": None
                    }

            slot = slots_map.get(target_slot_id)

            if is_cancelled:
                cancelled += 1
                if slot:
                    slot["classes_cancelled"] += 1
                continue

            if att and att.status == "present":
                conducted += 1
                attended += 1
                if slot:
                    slot["classes_conducted"] += 1
                    slot["classes_attended"] += 1
            elif att and att.status == "absent":
                conducted += 1
                missed += 1
                if slot:
                    slot["classes_conducted"] += 1
                    slot["classes_missed"] += 1
            else:
                # If class was scheduled in the past or completed but not marked yet (and ended)
                if has_ended:
                    unconfirmed += 1
                    if slot:
                        slot["unconfirmed_classes"] += 1

        # Percentage calculation: Attended / Conducted * 100
        if conducted > 0:
            percentage = round((attended / conducted) * 100.0, 2)
            is_below = percentage < target_percentage
        else:
            percentage = None  # None when no classes conducted yet
            is_below = False

        target = target_percentage / 100.0
        # Calculate classes needed to reach target T: (A + x) / (C + x) >= T => x >= (T*C - A) / (1 - T)
        if target >= 1.0:
            target = 0.999

        if conducted > 0 and (attended / conducted) < target:
            needed = math.ceil((target * conducted - attended) / (1.0 - target))
            needed = max(0, needed)
            bunk_buffer = 0
        else:
            needed = 0
            if target > 0 and conducted > 0:
                # Bunk buffer: (A) / (C + y) >= T => y <= (A - T*C) / T
                bunk_buffer = math.floor((attended - target * conducted) / target)
                bunk_buffer = max(0, bunk_buffer)
            else:
                bunk_buffer = 0

        # Build ClassSlotAttendance objects
        class_slots = []
        for s_data in slots_map.values():
            c_conducted = s_data["classes_conducted"]
            c_attended = s_data["classes_attended"]
            if c_conducted > 0:
                s_data["current_percentage"] = round((c_attended / c_conducted) * 100.0, 1)
            else:
                s_data["current_percentage"] = None
            class_slots.append(ClassSlotAttendance(**s_data))

        # Sort slots by day_of_week, start_time
        class_slots.sort(key=lambda s: (s.day_of_week if s.day_of_week is not None else 99, s.start_time))

        return SubjectAttendanceSummary(
            subject_id=subject.id,
            subject_name=subject.name,
            subject_code=subject.code or "",
            subject_color=subject.color or "#0D9488",
            target_attendance=subject.target_attendance,
            classes_conducted=conducted,
            classes_attended=attended,
            classes_missed=missed,
            classes_cancelled=cancelled,
            unconfirmed_classes=unconfirmed,
            current_percentage=percentage,
            is_below_target=is_below,
            classes_needed_for_target=needed,
            bunk_buffer=bunk_buffer,
            class_slots=class_slots,
            classes=serialized_classes
        )

    @staticmethod
    async def get_overall_attendance_summary(
        db: AsyncSession,
        user_id: str
    ) -> OverallAttendanceSummary:
        await AttendanceService.sync_timetable_occurrences(db, user_id)

        # Get user profile for global target
        profile_res = await db.execute(select(Profile).filter(Profile.id == user_id))
        profile = profile_res.scalars().first()
        target_pct = profile.target_attendance_percentage if profile else 75.0

        # Get all subjects
        subj_res = await db.execute(select(Subject).filter(Subject.user_id == user_id))
        subjects = subj_res.scalars().all()

        subjects_summary: List[SubjectAttendanceSummary] = []
        total_conducted = 0
        total_attended = 0
        total_missed = 0
        total_unconfirmed = 0

        for subj in subjects:
            s_summary = await AttendanceService.get_subject_attendance_summary(
                db, user_id, subj, subj.target_attendance or target_pct
            )
            subjects_summary.append(s_summary)
            total_conducted += s_summary.classes_conducted
            total_attended += s_summary.classes_attended
            total_missed += s_summary.classes_missed
            total_unconfirmed += s_summary.unconfirmed_classes

        overall_percentage = (
            round((total_attended / total_conducted) * 100.0, 2)
            if total_conducted > 0 else None
        )

        # Pending confirmations: Past or today classes that are not cancelled, not marked, and have finished
        today = date.today()
        now_time = datetime.now().time()
        pending_stmt = (
            select(ClassOccurrence)
            .options(
                selectinload(ClassOccurrence.attendance),
                selectinload(ClassOccurrence.topics),
                selectinload(ClassOccurrence.subject)
            )
            .filter(
                ClassOccurrence.user_id == user_id,
                ClassOccurrence.status != "cancelled",
                ClassOccurrence.date <= today
            )
            .order_by(ClassOccurrence.date.desc(), ClassOccurrence.start_time.desc())
        )
        pending_res = await db.execute(pending_stmt)
        all_occurrences = pending_res.scalars().all()

        pending_confirmations = []
        for occ in all_occurrences:
            # Skip archived occurrences or occurrences with archived attendance
            if getattr(occ, "is_archived", False) or (occ.attendance and getattr(occ.attendance, "is_archived", False)):
                continue
            if occ.status == "cancelled" or (occ.attendance and occ.attendance.status == "cancelled"):
                continue
            # Time gate: do not mark pending if class has not ended yet today!
            if occ.date == today and occ.end_time > now_time:
                continue
            if not occ.attendance or occ.attendance.status == "not_marked":
                pending_confirmations.append(ClassOccurrenceResponse.model_validate(occ))

        # Generate intelligent alerts
        alerts = []
        for s in subjects_summary:
            if s.classes_conducted > 0 and s.current_percentage is not None and s.is_below_target:
                alerts.append({
                    "type": "critical",
                    "subject_id": s.subject_id,
                    "title": f"Low Attendance: {s.subject_name}",
                    "message": f"Your attendance in {s.subject_name} is {s.current_percentage}% (Target: {s.target_attendance}%). You need to attend the next {s.classes_needed_for_target} class{'es' if s.classes_needed_for_target > 1 else ''} to reach your target."
                })
            elif s.classes_conducted > 0 and s.current_percentage is not None and s.current_percentage < (s.target_attendance + 5.0):
                alerts.append({
                    "type": "warning",
                    "subject_id": s.subject_id,
                    "title": f"Approaching Target: {s.subject_name}",
                    "message": f"{s.subject_name} is at {s.current_percentage}%. You can safely miss at most {s.bunk_buffer} class{'es' if s.bunk_buffer != 1 else ''} before falling below {s.target_attendance}%."
                })

        total_cancelled = 0
        for s in subjects_summary:
            total_cancelled += s.classes_cancelled

        return OverallAttendanceSummary(
            total_conducted=total_conducted,
            total_attended=total_attended,
            total_missed=total_missed,
            total_cancelled=total_cancelled,
            total_unconfirmed=total_unconfirmed,
            overall_percentage=overall_percentage,
            target_percentage=target_pct,
            subjects_summary=subjects_summary,
            pending_confirmations=pending_confirmations,
            alerts=alerts
        )

    @staticmethod
    async def sync_timetable_occurrences(db: AsyncSession, user_id: str):
        """
        Ensures all active recurring timetable rules for the user have generated their
        occurrences up to today, so they appear in the attendance portal automatically
        the moment the class ends.
        Never generates occurrences before the timetable's effective start date.
        """
        from app.services.timetable_service import TimetableService
        today = date.today()

        # Clean up any past spurious auto-generated occurrences that violated start dates
        await TimetableService.cleanup_invalid_past_occurrences(db, user_id)

        # Look up user profile to get global timetable_start_date if any
        prof_stmt = select(Profile).filter(Profile.id == user_id)
        profile = (await db.execute(prof_stmt)).scalars().first()
        profile_start = profile.timetable_start_date if profile else None

        rule_stmt = select(TimetableRule).filter(
            TimetableRule.user_id == user_id,
            TimetableRule.is_active == True
        )
        rules = (await db.execute(rule_stmt)).scalars().all()
        if not rules:
            return

        # Find earliest rule start date
        starts = []
        if profile_start:
            starts.append(profile_start)
        for r in rules:
            if r.effective_from:
                starts.append(r.effective_from)
            elif r.created_at:
                starts.append(r.created_at.date())

        earliest_start = min(starts) if starts else today
        start_date = max(earliest_start, today - timedelta(days=60))

        if start_date <= today:
            await TimetableService.ensure_occurrences_generated(db, user_id, start_date, today)

    @staticmethod
    async def get_attendance_classes(
        db: AsyncSession,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Retrieves all ended classes from the timetable for attendance marking,
        plus upcoming classes scheduled for later today.
        Deduplicates occurrences and filters out archived ones.
        """
        await AttendanceService.sync_timetable_occurrences(db, user_id)

        today = date.today()
        now_time = datetime.now().time()

        # Fetch profile and rules for start date validation
        prof_stmt = select(Profile).filter(Profile.id == user_id)
        profile = (await db.execute(prof_stmt)).scalars().first()
        profile_start = profile.timetable_start_date if profile else None

        rule_stmt = select(TimetableRule).filter(TimetableRule.user_id == user_id)
        rules_map = {r.id: r for r in (await db.execute(rule_stmt)).scalars().all()}

        stmt = (
            select(ClassOccurrence)
            .options(
                selectinload(ClassOccurrence.subject),
                selectinload(ClassOccurrence.topics),
                selectinload(ClassOccurrence.attendance)
            )
            .filter(
                ClassOccurrence.user_id == user_id,
                ClassOccurrence.date <= today
            )
            .order_by(ClassOccurrence.date.desc(), ClassOccurrence.start_time.desc())
        )
        raw_classes = (await db.execute(stmt)).scalars().all()

        seen_slots = set()
        ended_classes = []
        upcoming_today = []

        for occ in raw_classes:
            if getattr(occ, "is_archived", False):
                continue

            # Exclude un-marked occurrences before effective start date
            rule_obj = rules_map.get(occ.rule_id)
            effective_start = rule_obj.effective_from if rule_obj else profile_start
            if not effective_start and rule_obj and rule_obj.created_at:
                effective_start = rule_obj.created_at.date()
            if not effective_start:
                effective_start = today

            if occ.date < effective_start and (not occ.attendance or occ.attendance.status == "not_marked"):
                continue

            slot_key = (occ.subject_id, str(occ.date), occ.start_time.strftime("%H:%M"), occ.end_time.strftime("%H:%M"))
            if slot_key in seen_slots:
                continue
            seen_slots.add(slot_key)

            has_ended = occ.date < today or (occ.date == today and occ.end_time <= now_time)
            occ_data = ClassOccurrenceResponse.model_validate(occ)
            if has_ended:
                ended_classes.append(occ_data)
            elif occ.date == today:
                upcoming_today.append(occ_data)

        pending_count = sum(
            1 for c in ended_classes
            if (not c.attendance or c.attendance.status == "not_marked") and c.status != "cancelled"
        )

        today_classes = []
        for occ in raw_classes:
            if getattr(occ, "is_archived", False):
                continue
            if occ.date == today:
                has_ended = occ.end_time <= now_time
                is_in_progress = occ.start_time <= now_time < occ.end_time
                is_upcoming = occ.start_time > now_time
                occ_dict = ClassOccurrenceResponse.model_validate(occ).model_dump()
                occ_dict["has_ended"] = has_ended
                occ_dict["is_in_progress"] = is_in_progress
                occ_dict["is_upcoming"] = is_upcoming
                today_classes.append(occ_dict)

        today_classes.sort(key=lambda c: c["start_time"])

        return {
            "ended_classes": ended_classes,
            "upcoming_today": upcoming_today,
            "today_classes": today_classes,
            "pending_count": pending_count
        }

    @staticmethod
    async def get_today_classes(
        db: AsyncSession,
        user_id: str
    ) -> List[ClassOccurrence]:
        """
        Retrieves today's scheduled class occurrences for quick attendance marking.
        Ensures recurring rules have generated occurrences for today.
        Deduplicates occurrences and filters out archived ones.
        """
        await AttendanceService.sync_timetable_occurrences(db, user_id)
        today = date.today()

        stmt = (
            select(ClassOccurrence)
            .options(
                selectinload(ClassOccurrence.subject),
                selectinload(ClassOccurrence.topics),
                selectinload(ClassOccurrence.attendance)
            )
            .filter(
                ClassOccurrence.user_id == user_id,
                ClassOccurrence.date == today
            )
            .order_by(ClassOccurrence.start_time.asc())
        )
        raw_classes = (await db.execute(stmt)).scalars().all()
        seen_ids = set()
        seen_slots = set()
        unique_classes = []
        for occ in raw_classes:
            if getattr(occ, "is_archived", False):
                continue
            if occ.id in seen_ids:
                continue
            seen_ids.add(occ.id)
            slot_key = (occ.subject_id, occ.start_time.strftime("%H:%M"), occ.end_time.strftime("%H:%M"))
            if slot_key in seen_slots:
                continue
            seen_slots.add(slot_key)
            unique_classes.append(occ)
        return unique_classes

    @staticmethod
    async def get_attendance_history(
        db: AsyncSession,
        user_id: str,
        subject_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        archive_status: Optional[str] = "all",
        archive_label: Optional[str] = None
    ) -> List[ClassOccurrence]:
        """
        Retrieves past class occurrences with their attendance records.
        """
        stmt = (
            select(ClassOccurrence)
            .options(
                selectinload(ClassOccurrence.subject),
                selectinload(ClassOccurrence.topics),
                selectinload(ClassOccurrence.attendance)
            )
            .filter(ClassOccurrence.user_id == user_id)
        )
        if subject_id:
            stmt = stmt.filter(ClassOccurrence.subject_id == subject_id)
        if start_date:
            stmt = stmt.filter(ClassOccurrence.date >= start_date)
        if end_date:
            stmt = stmt.filter(ClassOccurrence.date <= end_date)
        if archive_status == "active":
            stmt = stmt.filter(ClassOccurrence.is_archived == False)
        elif archive_status == "archived":
            stmt = stmt.filter(ClassOccurrence.is_archived == True)
        if archive_label:
            stmt = stmt.filter(ClassOccurrence.archive_label == archive_label)

        stmt = stmt.order_by(ClassOccurrence.date.desc(), ClassOccurrence.start_time.desc())
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def archive_semester(
        db: AsyncSession,
        user_id: str,
        semester_label: str
    ) -> Dict[str, Any]:
        """
        Archives current active attendance and past class occurrences under the given label.
        Fresh attendance counts begin from 0.
        """
        today = date.today()
        clean_label = semester_label.strip()

        # 1. Archive all unarchived Attendance records
        att_stmt = select(Attendance).filter(
            Attendance.user_id == user_id,
            Attendance.is_archived == False
        )
        att_records = (await db.execute(att_stmt)).scalars().all()
        for att in att_records:
            att.is_archived = True
            att.archive_label = clean_label

        # 2. Archive all unarchived ClassOccurrence records for past dates or today if marked
        occ_stmt = select(ClassOccurrence).options(
            selectinload(ClassOccurrence.attendance)
        ).filter(
            ClassOccurrence.user_id == user_id,
            ClassOccurrence.is_archived == False,
            ClassOccurrence.date <= today
        )
        occ_records = (await db.execute(occ_stmt)).scalars().all()
        for occ in occ_records:
            # If it's today and not marked at all, leave it active for today's classes
            if occ.date == today and (not occ.attendance or occ.attendance.status == "not_marked") and occ.status != "cancelled":
                continue
            occ.is_archived = True
            occ.archive_label = clean_label

        await db.commit()
        return {
            "status": "ok",
            "archived_attendance_count": len(att_records),
            "archived_occurrences_count": len(occ_records),
            "semester_label": clean_label
        }

    @staticmethod
    async def reset_attendance(
        db: AsyncSession,
        user_id: str,
        subject_id: Optional[str] = None,
        remove_topics: bool = False
    ) -> Dict[str, Any]:
        """
        Resets attendance data for a single subject or all subjects.
        Timetable rules and subjects are preserved.
        Attendance records/calculations are cleared.
        If remove_topics is True, saved class topics are also removed.
        """
        today = date.today()

        # Build query for occurrences
        occ_stmt = select(ClassOccurrence).options(
            selectinload(ClassOccurrence.attendance),
            selectinload(ClassOccurrence.topics)
        ).filter(ClassOccurrence.user_id == user_id)

        if subject_id and subject_id.strip():
            occ_stmt = occ_stmt.filter(ClassOccurrence.subject_id == subject_id.strip())

        occurrences = (await db.execute(occ_stmt)).scalars().all()

        reset_count = 0
        for occ in occurrences:
            # If requested, remove saved class topics
            if remove_topics and occ.topics:
                for t in list(occ.topics):
                    await db.delete(t)

            if occ.date < today:
                # Past class: delete occurrence if remove_topics is True, or archive with reset label if keeping topics
                if remove_topics:
                    await db.delete(occ)
                else:
                    occ.is_archived = True
                    occ.archive_label = "Reset"
                    occ.status = "scheduled"
                    if occ.attendance:
                        await db.delete(occ.attendance)
            else:
                # Today or future class: reset status to scheduled, delete or reset attendance
                occ.status = "scheduled"
                occ.is_archived = False
                occ.archive_label = ""
                if occ.attendance:
                    await db.delete(occ.attendance)
            reset_count += 1

        # Also delete any orphaned attendance records for this user (and subject if specified)
        if not subject_id or not subject_id.strip():
            all_att_stmt = select(Attendance).filter(Attendance.user_id == user_id)
            all_att = (await db.execute(all_att_stmt)).scalars().all()
            for a in all_att:
                await db.delete(a)

        await db.commit()
        return {
            "status": "ok",
            "reset_occurrences_count": reset_count,
            "subject_id": subject_id or "all"
        }
