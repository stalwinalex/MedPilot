import uuid
from datetime import datetime, date, time
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, Date, Time, DateTime,
    ForeignKey, UniqueConstraint, JSON
)
from sqlalchemy.orm import relationship
from app.core.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=True)
    full_name = Column(String(255), nullable=False, default="")
    college = Column(String(255), nullable=False, default="")
    year_of_study = Column(String(50), nullable=False, default="MBBS 1st Year")
    target_attendance_percentage = Column(Float, nullable=False, default=75.0)
    daily_study_target_minutes = Column(Integer, nullable=False, default=180)
    timetable_start_date = Column(Date, nullable=True)
    hashed_password = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    subjects = relationship("Subject", back_populates="profile", cascade="all, delete-orphan")
    timetable_rules = relationship("TimetableRule", back_populates="profile", cascade="all, delete-orphan")
    occurrences = relationship("ClassOccurrence", back_populates="profile", cascade="all, delete-orphan")
    attendance_records = relationship("Attendance", back_populates="profile", cascade="all, delete-orphan")
    exams = relationship("Exam", back_populates="profile", cascade="all, delete-orphan")
    study_plans = relationship("StudyPlan", back_populates="profile", cascade="all, delete-orphan")
    study_tasks = relationship("StudyTask", back_populates="profile", cascade="all, delete-orphan")
    study_sessions = relationship("StudySession", back_populates="profile", cascade="all, delete-orphan")
    habits = relationship("Habit", back_populates="profile", cascade="all, delete-orphan")
    habit_logs = relationship("HabitLog", back_populates="profile", cascade="all, delete-orphan")
    routine_settings = relationship("RoutineSetting", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="profile", cascade="all, delete-orphan")
    generated_resources = relationship("GeneratedResource", back_populates="profile", cascade="all, delete-orphan")
    pyq_analyses = relationship("PYQAnalysis", back_populates="profile", cascade="all, delete-orphan")
    wellbeing_checkins = relationship("WellbeingCheckIn", back_populates="profile", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="profile", cascade="all, delete-orphan")


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(20), default="")
    color = Column(String(20), default="#0D9488")
    target_attendance = Column(Float, default=75.0)
    faculty = Column(String(100), default="")
    academic_year = Column(String(50), default="")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    profile = relationship("Profile", back_populates="subjects")
    timetable_rules = relationship("TimetableRule", back_populates="subject", cascade="all, delete-orphan")
    occurrences = relationship("ClassOccurrence", back_populates="subject", cascade="all, delete-orphan")
    exams = relationship("Exam", back_populates="subject", cascade="all, delete-orphan")


class TimetableRule(Base):
    """Level A: Recurring Timetable Rule (e.g. Every Monday at 10:00 AM)"""
    __tablename__ = "timetable_rules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    faculty = Column(String(100), default="")
    room = Column(String(50), default="")
    is_active = Column(Boolean, default=True)
    effective_from = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    profile = relationship("Profile", back_populates="timetable_rules")
    subject = relationship("Subject", back_populates="timetable_rules")
    occurrences = relationship("ClassOccurrence", back_populates="rule")


class ClassOccurrence(Base):
    """Level B: Individual Class Occurrence (e.g. Monday 15 Sep at 10:00 AM)"""
    __tablename__ = "class_occurrences"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = Column(String(36), ForeignKey("timetable_rules.id", ondelete="SET NULL"), nullable=True)
    subject_id = Column(String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    faculty = Column(String(100), default="")
    room = Column(String(50), default="")
    status = Column(String(20), nullable=False, default="scheduled")  # scheduled, completed, cancelled, rescheduled
    original_date = Column(Date, nullable=True)
    original_start_time = Column(Time, nullable=True)
    is_extra_class = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False, nullable=False, index=True)
    archive_label = Column(String(100), default="", nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="occurrences")
    rule = relationship("TimetableRule", back_populates="occurrences")
    subject = relationship("Subject", back_populates="occurrences")
    topics = relationship("ClassTopic", back_populates="occurrence", cascade="all, delete-orphan", order_by="ClassTopic.order_index")
    attendance = relationship("Attendance", back_populates="occurrence", uselist=False, cascade="all, delete-orphan")


class ClassTopic(Base):
    """Multiple topics belonging to an individual class occurrence"""
    __tablename__ = "class_topics"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    occurrence_id = Column(String(36), ForeignKey("class_occurrences.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    order_index = Column(Integer, default=0)
    study_status = Column(String(20), default="study", nullable=False)  # study, later, skip
    snooze_until = Column(Date, nullable=True)
    skip_reason = Column(String(50), nullable=True)  # skip_this_plan, already_know, dont_suggest
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    occurrence = relationship("ClassOccurrence", back_populates="topics")


class Attendance(Base):
    """Student attendance confirmation for an individual class occurrence"""
    __tablename__ = "attendance"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    occurrence_id = Column(String(36), ForeignKey("class_occurrences.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="not_marked")  # present, absent, not_marked
    marked_at = Column(DateTime(timezone=True), nullable=True)
    is_archived = Column(Boolean, default=False, nullable=False, index=True)
    archive_label = Column(String(100), default="", nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "occurrence_id", name="uq_attendance_user_occurrence"),
    )

    profile = relationship("Profile", back_populates="attendance_records")
    occurrence = relationship("ClassOccurrence", back_populates="attendance")


class Exam(Base):
    __tablename__ = "exams"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    exam_date = Column(Date, nullable=False, index=True)
    exam_type = Column(String(50), default="Internal Assessment")
    target_score = Column(Float, default=75.0)
    important_topics = Column(JSON, default=list)
    syllabus_portion = Column(String(255), nullable=True)
    prep_status = Column(String(30), default="not_started")  # not_started, in_progress, well_prepared, revision_needed
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="exams")
    subject = relationship("Subject", back_populates="exams")
    tasks = relationship("StudyTask", back_populates="exam")


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    daily_study_budget_minutes = Column(Integer, default=120, nullable=True)
    total_planned_minutes = Column(Integer, default=0)
    status = Column(String(20), default="active")  # active, completed, archived
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="study_plans")
    tasks = relationship("StudyTask", back_populates="plan", cascade="all, delete-orphan")


class StudyTask(Base):
    __tablename__ = "study_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(String(36), ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=True)
    subject_id = Column(String(36), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    exam_id = Column(String(36), ForeignKey("exams.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    priority = Column(String(10), default="medium")  # high, medium, low
    estimated_minutes = Column(Integer, default=45)
    scheduled_date = Column(Date, nullable=False, index=True)
    scheduled_time = Column(Time, nullable=True)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    order_index = Column(Integer, default=0)
    actual_minutes = Column(Integer, nullable=True)
    feedback = Column(String(30), nullable=True)  # easy, okay, hard, need_more_time
    reason = Column(String(255), default="")  # short human-readable reason for duration & priority
    topic_name = Column(String(255), nullable=True)  # normalized topic name for learning feedback loops
    planning_score = Column(Float, nullable=True)  # calculated internal weight for transparency
    missed_class_date = Column(Date, nullable=True)  # date of missed class if derived from absence
    syllabus_portion = Column(String(255), nullable=True)  # exam portion / unit / syllabus topic context
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    profile = relationship("Profile", back_populates="study_tasks")
    plan = relationship("StudyPlan", back_populates="tasks")
    exam = relationship("Exam", back_populates="tasks")
    subject = relationship("Subject")


class StudySession(Base):
    __tablename__ = "study_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    task_id = Column(String(36), ForeignKey("study_tasks.id", ondelete="SET NULL"), nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    mode = Column(String(20), default="custom")  # 30_min, 1_hour, 2_hour, custom
    session_breakdown = Column(JSON, default=dict)
    notes = Column(Text, default="")
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    profile = relationship("Profile", back_populates="study_sessions")


class Habit(Base):
    """Non-punitive student routine tracker"""
    __tablename__ = "habits"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    category = Column(String(30), default="routine")  # sleep, hydration, nutrition, break, routine
    target_frequency = Column(String(20), default="daily")
    selected_days = Column(String(50), default="0,1,2,3,4,5,6")  # Comma separated: 0=Mon, 6=Sun
    reminder_time = Column(String(30), default="")  # "", "morning", "afternoon", "evening", or "08:00"
    note = Column(Text, default="")
    is_paused = Column(Boolean, default=False)
    order_index = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    profile = relationship("Profile", back_populates="habits")
    logs = relationship("HabitLog", back_populates="habit", cascade="all, delete-orphan")


class RoutineSetting(Base):
    """User preferences for routine reminders, quiet hours, and timetable integration"""
    __tablename__ = "routine_settings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    reminders_enabled = Column(Boolean, default=True)
    pause_reminders_today = Column(Boolean, default=False)
    paused_until_date = Column(Date, nullable=True)
    quiet_hours_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(String(10), default="22:00")
    quiet_hours_end = Column(String(10), default="07:00")
    morning_time = Column(String(10), default="08:00")
    afternoon_time = Column(String(10), default="14:00")
    evening_time = Column(String(10), default="20:00")
    avoid_during_classes = Column(Boolean, default=True)
    combine_nearby = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="routine_settings")


class HabitLog(Base):
    __tablename__ = "habit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    habit_id = Column(String(36), ForeignKey("habits.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    status = Column(String(20), default="missed")  # completed, missed, skipped
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("habit_id", "user_id", "date", name="uq_habit_user_date"),
    )

    profile = relationship("Profile", back_populates="habit_logs")
    habit = relationship("Habit", back_populates="logs")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False)  # attendance_reminder, low_attendance_alert, exam_countdown, study_reminder
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    related_occurrence_id = Column(String(36), ForeignKey("class_occurrences.id", ondelete="SET NULL"), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    profile = relationship("Profile", back_populates="notifications")


class GeneratedResource(Base):
    __tablename__ = "generated_resources"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    resource_type = Column(String(30), nullable=False)  # summary, revision_sheet, mcq_bank, flashcards, study_notes, pyq_analysis
    content_json = Column(JSON, default=dict)
    pdf_storage_path = Column(String(500), nullable=True)
    source_citations = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    profile = relationship("Profile", back_populates="generated_resources")
    shared_copies = relationship("SharedResource", back_populates="resource", cascade="all, delete-orphan")
    subject = relationship("Subject")


class PYQAnalysis(Base):
    __tablename__ = "pyq_analyses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    exam_name = Column(String(255), nullable=False)
    years_covered = Column(String(100), nullable=False)
    topic_frequencies = Column(JSON, default=list)
    repeated_patterns = Column(JSON, default=list)
    high_yield_topics = Column(JSON, default=list)
    guidance_notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    profile = relationship("Profile", back_populates="pyq_analyses")
    subject = relationship("Subject")


class Friend(Base):
    __tablename__ = "friends"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    friend_user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "friend_user_id", name="uq_friendship"),
    )


class FriendRequest(Base):
    __tablename__ = "friend_requests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    sender_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), default="pending")  # pending, accepted, rejected
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("sender_id", "receiver_id", name="uq_friend_request"),
    )


class SharedResource(Base):
    __tablename__ = "shared_resources"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    resource_id = Column(String(36), ForeignKey("generated_resources.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    permission = Column(String(20), default="view")  # view, download
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("resource_id", "receiver_id", name="uq_shared_resource"),
    )

    resource = relationship("GeneratedResource", back_populates="shared_copies")


class WellbeingCheckIn(Base):
    """Daily wellbeing check-in for student study load balancing"""
    __tablename__ = "wellbeing_checkins"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    status = Column(String(20), nullable=False)  # "answered" or "skipped"
    mood = Column(String(20), nullable=True)  # "great", "good", "okay", "tired", "stressful"
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_wellbeing_user_date"),
    )

    profile = relationship("Profile", back_populates="wellbeing_checkins")


class Conversation(Base):
    """Stores persistent AI Assistant chat sessions per student"""
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="New Conversation")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="conversations")
    messages = relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at.asc()"
    )


class ChatMessage(Base):
    """Stores individual messages within a persistent AI conversation"""
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False, default="")
    model = Column(String(100), nullable=True)  # e.g., "gemini-3.8-flash", "gemini-3.6-flash fallback"
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    extra_data = Column(JSON, default=dict)  # citations, diagrams, flashcards, sources, attachments, actions

    conversation = relationship("Conversation", back_populates="messages")

