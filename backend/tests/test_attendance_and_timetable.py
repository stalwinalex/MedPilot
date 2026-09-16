import pytest
import pytest_asyncio
from datetime import date, time, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.models.models import Base, Profile, Subject, TimetableRule, ClassOccurrence, ClassTopic, Attendance
from app.services.attendance_service import AttendanceService
from app.services.timetable_service import TimetableService
from app.schemas.schemas import ClassOccurrenceCreate, ClassRescheduleRequest, ClassSwapRequest


# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    
    await engine.dispose()


@pytest.mark.asyncio
async def test_attendance_calculations_and_cancelled_classes(db_session: AsyncSession):
    # 1. Setup Student & Subject
    profile = Profile(
        id="student-1",
        email="mbbs@medpilot.io",
        full_name="Dr. Med Student",
        target_attendance_percentage=75.0
    )
    subject = Subject(
        id="subj-anatomy",
        user_id="student-1",
        name="Anatomy",
        target_attendance=75.0
    )
    db_session.add(profile)
    db_session.add(subject)
    await db_session.commit()

    # 2. Add 2 conducted classes: 1 Present, 1 Absent
    today = date.today()
    occ1 = ClassOccurrence(
        id="occ-1",
        user_id="student-1",
        subject_id="subj-anatomy",
        date=today - timedelta(days=2),
        start_time=time(10, 0),
        end_time=time(11, 0),
        status="completed"
    )
    att1 = Attendance(user_id="student-1", occurrence_id="occ-1", status="present")

    occ2 = ClassOccurrence(
        id="occ-2",
        user_id="student-1",
        subject_id="subj-anatomy",
        date=today - timedelta(days=1),
        start_time=time(10, 0),
        end_time=time(11, 0),
        status="completed"
    )
    att2 = Attendance(user_id="student-1", occurrence_id="occ-2", status="absent")

    db_session.add_all([occ1, att1, occ2, att2])
    await db_session.commit()

    # Verify 1 attended / 2 conducted = 50.0%
    summary = await AttendanceService.get_subject_attendance_summary(db_session, "student-1", subject, 75.0)
    assert summary.classes_conducted == 2
    assert summary.classes_attended == 1
    assert summary.classes_missed == 1
    assert summary.current_percentage == 50.0
    assert summary.is_below_target is True
    # Formula: needed = ceil((0.75 * 2 - 1) / 0.25) = ceil(0.5 / 0.25) = 2 classes
    assert summary.classes_needed_for_target == 2

    # 3. Add a CANCELLED class
    # CRITICAL REQUIREMENT: Cancelled classes must NEVER count as conducted and must NOT reduce attendance %
    occ_cancelled = ClassOccurrence(
        id="occ-cancelled",
        user_id="student-1",
        subject_id="subj-anatomy",
        date=today,
        start_time=time(12, 0),
        end_time=time(13, 0),
        status="cancelled"
    )
    db_session.add(occ_cancelled)
    await db_session.commit()

    summary_after_cancel = await AttendanceService.get_subject_attendance_summary(db_session, "student-1", subject, 75.0)
    assert summary_after_cancel.classes_conducted == 2  # Still 2, not 3!
    assert summary_after_cancel.current_percentage == 50.0  # Still 50%, not reduced!

    # 4. Add an unconfirmed class (not marked)
    occ_unconfirmed = ClassOccurrence(
        id="occ-unconfirmed",
        user_id="student-1",
        subject_id="subj-anatomy",
        date=today,
        start_time=time(0, 0),
        end_time=time(0, 30),
        status="scheduled"
    )
    att_unconfirmed = Attendance(user_id="student-1", occurrence_id="occ-unconfirmed", status="not_marked")
    db_session.add_all([occ_unconfirmed, att_unconfirmed])
    await db_session.commit()

    summary_unconf = await AttendanceService.get_subject_attendance_summary(db_session, "student-1", subject, 75.0)
    # Unconfirmed class does NOT count as absent!
    assert summary_unconf.classes_conducted == 2
    assert summary_unconf.unconfirmed_classes == 1
    assert summary_unconf.classes_missed == 1


@pytest.mark.asyncio
async def test_flexible_timetable_rules_and_occurrences(db_session: AsyncSession):
    # Setup Student & Subject
    profile = Profile(id="student-2", email="test2@medpilot.io", full_name="Student Two")
    subject_phys = Subject(id="subj-phys", user_id="student-2", name="Physiology")
    subject_biochem = Subject(id="subj-biochem", user_id="student-2", name="Biochemistry")
    db_session.add_all([profile, subject_phys, subject_biochem])
    await db_session.commit()

    # Level A: Recurring Rule: Every Monday at 9:00 AM Physiology
    rule = TimetableRule(
        id="rule-mon-phys",
        user_id="student-2",
        subject_id="subj-phys",
        day_of_week=0, # Monday
        start_time=time(9, 0),
        end_time=time(10, 0),
        room="LT-1"
    )
    db_session.add(rule)
    await db_session.commit()

    # Ensure occurrences generated for 2 consecutive Mondays
    # Find next Monday
    today = date.today()
    days_to_monday = (0 - today.weekday()) % 7
    monday1 = today + timedelta(days=days_to_monday)
    monday2 = monday1 + timedelta(days=7)

    await TimetableService.ensure_occurrences_generated(db_session, "student-2", monday1, monday2)

    occ_mon1 = (await db_session.execute(
        ClassOccurrence.__table__.select().where(
            ClassOccurrence.user_id == "student-2",
            ClassOccurrence.date == monday1
        )
    )).fetchone()
    assert occ_mon1 is not None
    assert occ_mon1.subject_id == "subj-phys"

    # Override individual occurrence: Change Monday 1 to Biochemistry (Swap or Edit)
    occ1_model = (await db_session.execute(
        ClassOccurrence.__table__.select().where(ClassOccurrence.id == occ_mon1.id)
    )).fetchone()

    # Edit occurrence 1 subject to Biochemistry
    await db_session.execute(
        ClassOccurrence.__table__.update()
        .where(ClassOccurrence.id == occ_mon1.id)
        .values(subject_id="subj-biochem")
    )
    await db_session.commit()

    # Verify: Occurrence 1 is now Biochemistry
    updated_occ1 = (await db_session.execute(
        ClassOccurrence.__table__.select().where(ClassOccurrence.id == occ_mon1.id)
    )).fetchone()
    assert updated_occ1.subject_id == "subj-biochem"

    # CRITICAL: Recurring Rule must remain UNCHANGED!
    stored_rule = (await db_session.execute(
        TimetableRule.__table__.select().where(TimetableRule.id == "rule-mon-phys")
    )).fetchone()
    assert stored_rule.subject_id == "subj-phys"

    # And Occurrence 2 (next Monday) must still be Physiology!
    occ_mon2 = (await db_session.execute(
        ClassOccurrence.__table__.select().where(
            ClassOccurrence.user_id == "student-2",
            ClassOccurrence.date == monday2
        )
    )).fetchone()
    assert occ_mon2.subject_id == "subj-phys"


@pytest.mark.asyncio
async def test_extra_class_and_multiple_topics(db_session: AsyncSession):
    profile = Profile(id="student-3", email="test3@medpilot.io", full_name="Student Three")
    subject = Subject(id="subj-path", user_id="student-3", name="Pathology")
    db_session.add_all([profile, subject])
    await db_session.commit()

    # Add extra class with multiple topics
    data = ClassOccurrenceCreate(
        subject_id="subj-path",
        date=date.today(),
        start_time=time(15, 0),
        end_time=time(16, 0),
        room="Histology Lab",
        faculty="Dr. Sharma",
        topics=["Granulomatous Inflammation", "Tuberculosis Caseous Necrosis", "Giant Cell Types"]
    )
    extra_class = await TimetableService.add_extra_class(db_session, "student-3", data)
    assert extra_class.is_extra_class is True
    assert extra_class.rule_id is None

    # Verify topics linked to occurrence
    topics_res = await db_session.execute(
        ClassTopic.__table__.select().where(ClassTopic.occurrence_id == extra_class.id)
    )
    topics = topics_res.fetchall()
    assert len(topics) == 3
    assert topics[0].title == "Granulomatous Inflammation"
    assert topics[1].title == "Tuberculosis Caseous Necrosis"
    assert topics[2].title == "Giant Cell Types"


@pytest.mark.asyncio
async def test_timetable_change_automatically_updates_attendance(db_session: AsyncSession):
    # 1. Setup Student & 2 Subjects
    profile = Profile(id="student-auto", email="auto@medpilot.io", full_name="Student Auto", target_attendance_percentage=75.0)
    subj_anat = Subject(id="subj-anat-1", user_id="student-auto", name="Anatomy", target_attendance=75.0)
    subj_biochem = Subject(id="subj-biochem-1", user_id="student-auto", name="Biochemistry", target_attendance=75.0)
    db_session.add_all([profile, subj_anat, subj_biochem])
    await db_session.commit()

    # 2. Add an occurrence for Anatomy yesterday
    yesterday = date.today() - timedelta(days=1)
    occ = ClassOccurrence(
        id="occ-sync-1",
        user_id="student-auto",
        subject_id="subj-anat-1",
        date=yesterday,
        start_time=time(9, 0),
        end_time=time(10, 0),
        status="completed"
    )
    att = Attendance(user_id="student-auto", occurrence_id="occ-sync-1", status="present")
    db_session.add_all([occ, att])
    await db_session.commit()

    # Verify Anatomy has 1 attended, Biochem has 0
    anat_sum = await AttendanceService.get_subject_attendance_summary(db_session, "student-auto", subj_anat, 75.0)
    biochem_sum = await AttendanceService.get_subject_attendance_summary(db_session, "student-auto", subj_biochem, 75.0)
    assert anat_sum.classes_conducted == 1
    assert anat_sum.classes_attended == 1
    assert anat_sum.current_percentage == 100.0
    assert biochem_sum.classes_conducted == 0

    # 3. Timetable changes: occurrence subject updated to Biochemistry (via API update flow)
    occ_to_edit = await db_session.get(ClassOccurrence, "occ-sync-1")
    occ_to_edit.subject_id = "subj-biochem-1"
    await db_session.commit()

    # Verify Attendance automatically recalculated!
    anat_sum2 = await AttendanceService.get_subject_attendance_summary(db_session, "student-auto", subj_anat, 75.0)
    biochem_sum2 = await AttendanceService.get_subject_attendance_summary(db_session, "student-auto", subj_biochem, 75.0)
    assert anat_sum2.classes_conducted == 0
    assert biochem_sum2.classes_conducted == 1
    assert biochem_sum2.classes_attended == 1
    assert biochem_sum2.current_percentage == 100.0

    # 4. Occurrence cancelled in timetable
    occ_to_cancel = await db_session.get(ClassOccurrence, "occ-sync-1")
    occ_to_cancel.status = "cancelled"
    await db_session.commit()

    biochem_sum3 = await AttendanceService.get_subject_attendance_summary(db_session, "student-auto", subj_biochem, 75.0)
    assert biochem_sum3.classes_conducted == 0
    assert biochem_sum3.classes_attended == 0

    # 5. Check get_attendance_classes returns today_classes correctly
    today_occ = ClassOccurrence(
        id="occ-today-1",
        user_id="student-auto",
        subject_id="subj-anat-1",
        date=date.today(),
        start_time=time(0, 0),
        end_time=time(0, 30),
        status="scheduled"
    )
    db_session.add(today_occ)
    await db_session.commit()

    classes_dict = await AttendanceService.get_attendance_classes(db_session, "student-auto")
    assert "today_classes" in classes_dict
    today_item = next((c for c in classes_dict["today_classes"] if c["id"] == "occ-today-1"), None)
    assert today_item is not None
    assert today_item["has_ended"] is True


@pytest.mark.asyncio
async def test_separate_class_attendance_for_every_subject(db_session: AsyncSession):
    # 1. Setup Student & Anatomy Subject
    profile = Profile(id="student-slots", email="slots@medpilot.io", full_name="Student Slots", target_attendance_percentage=75.0)
    subj_anat = Subject(id="subj-anat-slots", user_id="student-slots", name="Anatomy", target_attendance=75.0)
    db_session.add_all([profile, subj_anat])
    await db_session.commit()

    # 2. Add 2 recurring rules:
    # Rule 1: Monday 9:00 - 10:00 (Lecture)
    rule_mon = TimetableRule(
        id="rule-mon-lecture",
        user_id="student-slots",
        subject_id="subj-anat-slots",
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(10, 0),
        room="LT-1",
        faculty="Dr. Sharma"
    )
    # Rule 2: Thursday 14:00 - 16:00 (Dissection Lab)
    rule_thu = TimetableRule(
        id="rule-thu-lab",
        user_id="student-slots",
        subject_id="subj-anat-slots",
        day_of_week=3,
        start_time=time(14, 0),
        end_time=time(16, 0),
        room="Dissection Hall",
        faculty="Dr. Verma"
    )
    db_session.add_all([rule_mon, rule_thu])
    await db_session.commit()

    # 3. Add 2 classes for Monday (1 Present, 1 Absent)
    mon_date1 = date.today() - timedelta(days=14)
    mon_date2 = date.today() - timedelta(days=7)
    occ_mon1 = ClassOccurrence(
        id="occ-mon-1",
        user_id="student-slots",
        rule_id="rule-mon-lecture",
        subject_id="subj-anat-slots",
        date=mon_date1,
        start_time=time(9, 0),
        end_time=time(10, 0),
        room="LT-1",
        faculty="Dr. Sharma",
        status="completed"
    )
    att_mon1 = Attendance(user_id="student-slots", occurrence_id="occ-mon-1", status="present")

    occ_mon2 = ClassOccurrence(
        id="occ-mon-2",
        user_id="student-slots",
        rule_id="rule-mon-lecture",
        subject_id="subj-anat-slots",
        date=mon_date2,
        start_time=time(9, 0),
        end_time=time(10, 0),
        room="LT-1",
        faculty="Dr. Sharma",
        status="completed"
    )
    att_mon2 = Attendance(user_id="student-slots", occurrence_id="occ-mon-2", status="absent")

    # 4. Add 1 class for Thursday (1 Present)
    thu_date1 = date.today() - timedelta(days=3)
    occ_thu1 = ClassOccurrence(
        id="occ-thu-1",
        user_id="student-slots",
        rule_id="rule-thu-lab",
        subject_id="subj-anat-slots",
        date=thu_date1,
        start_time=time(14, 0),
        end_time=time(16, 0),
        room="Dissection Hall",
        faculty="Dr. Verma",
        status="completed"
    )
    att_thu1 = Attendance(user_id="student-slots", occurrence_id="occ-thu-1", status="present")

    db_session.add_all([occ_mon1, att_mon1, occ_mon2, att_mon2, occ_thu1, att_thu1])
    await db_session.commit()

    # 5. Get Subject Summary
    summary = await AttendanceService.get_subject_attendance_summary(db_session, "student-slots", subj_anat, 75.0)

    # Verify overall subject statistics: 3 conducted, 2 attended, 1 missed = 66.67%
    assert summary.classes_conducted == 3
    assert summary.classes_attended == 2
    assert summary.classes_missed == 1
    assert summary.current_percentage == 66.67

    # Verify separate class slot attendance:
    assert len(summary.class_slots) == 2
    slot_mon = next((s for s in summary.class_slots if s.rule_id == "rule-mon-lecture"), None)
    assert slot_mon is not None
    assert slot_mon.classes_conducted == 2
    assert slot_mon.classes_attended == 1
    assert slot_mon.classes_missed == 1
    assert slot_mon.current_percentage == 50.0

    slot_thu = next((s for s in summary.class_slots if s.rule_id == "rule-thu-lab"), None)
    assert slot_thu is not None
    assert slot_thu.classes_conducted == 1
    assert slot_thu.classes_attended == 1
    assert slot_thu.classes_missed == 0
    assert slot_thu.current_percentage == 100.0

    # Verify individual class-by-class occurrences:
    assert len(summary.classes) == 3
    occ_ids = {c.id for c in summary.classes}
    assert occ_ids == {"occ-mon-1", "occ-mon-2", "occ-thu-1"}
    
    # Check individual attendance record per class
    c_mon1 = next(c for c in summary.classes if c.id == "occ-mon-1")
    assert c_mon1.attendance is not None
    assert c_mon1.attendance.status == "present"
    
    c_mon2 = next(c for c in summary.classes if c.id == "occ-mon-2")
    assert c_mon2.attendance is not None
    assert c_mon2.attendance.status == "absent"


