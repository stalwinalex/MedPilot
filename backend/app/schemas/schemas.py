from typing import Optional, List, Dict, Any
from datetime import datetime, date, time, date as dt_date, time as dt_time
from pydantic import BaseModel, Field, ConfigDict


# -------------------------------------------------------------
# Base Schema Config
# -------------------------------------------------------------
class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------
# Auth & Profile Schemas
# -------------------------------------------------------------
class UserLogin(BaseModel):
    email: str
    password: str


class UserRegister(BaseModel):
    email: str
    password: str
    full_name: str
    college: Optional[str] = "Medical College"
    year_of_study: Optional[str] = "MBBS 1st Year"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    college: Optional[str] = None
    year_of_study: Optional[str] = None
    target_attendance_percentage: Optional[float] = None
    daily_study_target_minutes: Optional[int] = None


class ProfileResponse(BaseSchema):
    id: str
    email: Optional[str]
    full_name: str
    college: str
    year_of_study: str
    target_attendance_percentage: float
    daily_study_target_minutes: int
    created_at: datetime
    updated_at: datetime


# -------------------------------------------------------------
# Subject Schemas
# -------------------------------------------------------------
class SubjectCreate(BaseModel):
    name: str
    code: Optional[str] = ""
    color: Optional[str] = "#0D9488"
    target_attendance: Optional[float] = 75.0
    faculty: Optional[str] = ""
    academic_year: Optional[str] = ""


class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    color: Optional[str] = None
    target_attendance: Optional[float] = None
    faculty: Optional[str] = None
    academic_year: Optional[str] = None


class SubjectResponse(BaseSchema):
    id: str
    user_id: str
    name: str
    code: str
    color: str
    target_attendance: float
    faculty: str = ""
    academic_year: str = ""
    created_at: datetime


class SubjectDetailResponse(BaseSchema):
    id: str
    user_id: str
    name: str
    code: str
    color: str
    target_attendance: float
    faculty: str = ""
    academic_year: str = ""
    created_at: datetime
    classes_conducted: int = 0
    classes_attended: int = 0
    classes_missed: int = 0
    classes_cancelled: int = 0
    current_percentage: Optional[float] = None
    is_below_target: bool = False
    classes_needed_for_target: int = 0
    bunk_buffer: int = 0


# -------------------------------------------------------------
# Timetable Schemas (2-Level Architecture)
# -------------------------------------------------------------
class ClassTopicCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    order_index: Optional[int] = 0


class ClassTopicUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    order_index: Optional[int] = None
    study_status: Optional[str] = None  # study, later, skip
    snooze_until: Optional[date] = None
    skip_reason: Optional[str] = None  # skip_this_plan, already_know, dont_suggest


class TopicStatusUpdateRequest(BaseModel):
    study_status: str  # study, later, skip
    snooze_days: Optional[int] = None  # e.g., 1 (tomorrow), 3 (3 days), 7 (1 week)
    snooze_until: Optional[date] = None
    skip_reason: Optional[str] = None  # skip_this_plan, already_know, dont_suggest


class ClassTopicBatchCreate(BaseModel):
    topics: List[str]
    description: Optional[str] = ""


class ClassTopicResponse(BaseSchema):
    id: str
    occurrence_id: str
    title: str
    description: str
    order_index: int
    study_status: Optional[str] = "study"
    snooze_until: Optional[date] = None
    skip_reason: Optional[str] = None
    created_at: datetime


# Level A: Recurring Rule
class TimetableRuleCreate(BaseModel):
    subject_id: str
    day_of_week: int = Field(ge=0, le=6, description="0=Monday, ..., 6=Sunday")
    start_time: time
    end_time: time
    faculty: Optional[str] = ""
    room: Optional[str] = ""
    is_active: Optional[bool] = True
    effective_from: Optional[date] = None


class TimetableRuleUpdate(BaseModel):
    subject_id: Optional[str] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6, description="0=Monday, ..., 6=Sunday")
    start_time: Optional[dt_time] = None
    end_time: Optional[dt_time] = None
    faculty: Optional[str] = None
    room: Optional[str] = None
    is_active: Optional[bool] = None
    update_future_occurrences: Optional[bool] = True
    start_from_date: Optional[dt_date] = None
    effective_from: Optional[date] = None


class TimetableRuleResponse(BaseSchema):
    id: str
    user_id: str
    subject_id: str
    day_of_week: int
    start_time: time
    end_time: time
    faculty: str
    room: str
    is_active: bool
    effective_from: Optional[date] = None
    created_at: datetime
    subject: Optional[SubjectResponse] = None


class ClassSlotInput(BaseModel):
    subject_id: str
    start_time: time
    end_time: time
    faculty: Optional[str] = ""
    room: Optional[str] = ""


class DayScheduleBatchRequest(BaseModel):
    day_of_week: int = Field(ge=0, le=6, description="0=Monday, ..., 6=Sunday")
    apply_to_days: Optional[List[int]] = []
    replace_existing: bool = False
    effective_from: Optional[date] = None
    slots: List[ClassSlotInput]


# Level B: Class Occurrence
class ClassOccurrenceCreate(BaseModel):
    subject_id: str
    rule_id: Optional[str] = None
    date: date
    start_time: time
    end_time: time
    faculty: Optional[str] = ""
    room: Optional[str] = ""
    status: Optional[str] = "scheduled"  # scheduled, completed, cancelled, rescheduled
    is_extra_class: Optional[bool] = False
    notes: Optional[str] = ""
    topics: Optional[List[str]] = []


class ClassOccurrenceUpdate(BaseModel):
    subject_id: Optional[str] = None
    date: Optional[dt_date] = None
    start_time: Optional[dt_time] = None
    end_time: Optional[dt_time] = None
    faculty: Optional[str] = None
    room: Optional[str] = None
    status: Optional[str] = None  # scheduled, completed, cancelled, rescheduled
    notes: Optional[str] = None


class ClassSwapRequest(BaseModel):
    occurrence_id_1: str
    occurrence_id_2: str


class ClassRescheduleRequest(BaseModel):
    occurrence_id: str
    new_date: date
    new_start_time: time
    new_end_time: time
    notes: Optional[str] = ""


class AttendanceBriefResponse(BaseSchema):
    id: str
    status: str
    marked_at: Optional[datetime]
    notes: Optional[str]
    is_archived: bool = False
    archive_label: Optional[str] = ""


class ClassOccurrenceResponse(BaseSchema):
    id: str
    user_id: str
    rule_id: Optional[str]
    subject_id: str
    date: date
    start_time: time
    end_time: time
    faculty: str
    room: str
    status: str
    original_date: Optional[date]
    original_start_time: Optional[time]
    is_extra_class: bool
    is_archived: bool = False
    archive_label: Optional[str] = ""
    notes: str
    created_at: datetime
    updated_at: datetime
    subject: Optional[SubjectResponse] = None
    topics: List[ClassTopicResponse] = []
    attendance: Optional[AttendanceBriefResponse] = None


# -------------------------------------------------------------
# Attendance Schemas
# -------------------------------------------------------------
class AttendanceMarkRequest(BaseModel):
    occurrence_id: str
    status: str = Field(description="'present', 'absent', 'cancelled', or 'not_marked'")
    notes: Optional[str] = ""


class ManualAttendanceCreate(BaseModel):
    subject_id: str
    date: date
    start_time: time
    end_time: time
    status: str = "present"  # present, absent, cancelled
    faculty: Optional[str] = ""
    room: Optional[str] = ""
    notes: Optional[str] = ""


class TimetableImportItem(BaseModel):
    id: Optional[str] = None
    day_of_week: int  # 0=Monday, 6=Sunday
    day_name: str
    start_time: str   # "HH:MM"
    end_time: str     # "HH:MM"
    subject_name: str
    matched_subject_id: Optional[str] = None
    matched_subject_name: Optional[str] = None
    is_new_subject: bool = False
    faculty: Optional[str] = ""
    room: Optional[str] = ""
    confidence: float = 1.0
    notes: Optional[str] = ""
    has_conflict: bool = False


class TimetableImportPreview(BaseModel):
    extracted_items: List[TimetableImportItem]
    raw_text: str = ""
    warnings: List[str] = []
    duplicate_count: int = 0


class TimetableImportConfirmRequest(BaseModel):
    items: List[TimetableImportItem]
    duplicate_mode: str = "skip"  # 'skip', 'replace', 'keep_all'
    schedule_starts_from: Optional[date] = None


class TimetableSettingsResponse(BaseModel):
    timetable_start_date: Optional[date] = None
    total_rules: int = 0
    earliest_rule_date: Optional[date] = None


class TimetableSettingsUpdate(BaseModel):
    timetable_start_date: date


class AttendanceResponse(BaseSchema):
    id: str
    user_id: str
    occurrence_id: str
    status: str
    marked_at: Optional[datetime]
    notes: str
    is_archived: bool = False
    archive_label: Optional[str] = ""
    created_at: datetime
    updated_at: datetime


class AttendanceCheckInRequest(BaseModel):
    occurrence_id: str
    status: str  # 'present', 'absent', 'cancelled', 'not_marked'
    topic_title: Optional[str] = None
    notes: Optional[str] = None


class AttendanceResetRequest(BaseModel):
    subject_id: Optional[str] = None  # None or empty string means all subjects
    remove_topics: bool = False
    confirmation: str  # Must be "RESET"


class SemesterArchiveRequest(BaseModel):
    semester_label: str = Field(min_length=1, max_length=100, description="Label for semester archive")


class AttendanceHistoryUpdateRequest(BaseModel):
    status: str = Field(description="'present', 'absent', 'cancelled', or 'not_marked'")
    topic_title: Optional[str] = None
    notes: Optional[str] = None


class ClassSlotAttendance(BaseModel):
    rule_id: Optional[str] = None
    day_of_week: Optional[int] = None
    day_name: Optional[str] = None
    start_time: str
    end_time: str
    room: Optional[str] = ""
    faculty: Optional[str] = ""
    classes_conducted: int = 0
    classes_attended: int = 0
    classes_missed: int = 0
    classes_cancelled: int = 0
    unconfirmed_classes: int = 0
    current_percentage: Optional[float] = None


class SubjectAttendanceSummary(BaseModel):
    subject_id: str
    subject_name: str
    subject_code: str
    subject_color: str
    target_attendance: float
    classes_conducted: int
    classes_attended: int
    classes_missed: int
    classes_cancelled: int = 0
    unconfirmed_classes: int
    current_percentage: Optional[float] = None
    is_below_target: bool = False
    classes_needed_for_target: int = 0
    bunk_buffer: int = 0  # Classes student can safely skip while staying above target
    class_slots: List[ClassSlotAttendance] = []
    classes: List[ClassOccurrenceResponse] = []


class OverallAttendanceSummary(BaseModel):
    total_conducted: int
    total_attended: int
    total_missed: int
    total_cancelled: int = 0
    total_unconfirmed: int
    overall_percentage: Optional[float] = None
    target_percentage: float
    subjects_summary: List[SubjectAttendanceSummary]
    pending_confirmations: List[ClassOccurrenceResponse]
    alerts: List[Dict[str, Any]]


# -------------------------------------------------------------
# Exam Schemas
# -------------------------------------------------------------
class ExamCreate(BaseModel):
    subject_id: str
    name: str
    exam_date: date
    exam_type: Optional[str] = "Internal Assessment"
    target_score: Optional[float] = 75.0
    important_topics: Optional[List[str]] = []
    syllabus_portion: Optional[str] = None
    prep_status: Optional[str] = "not_started"


class ExamUpdate(BaseModel):
    name: Optional[str] = None
    exam_date: Optional[date] = None
    exam_type: Optional[str] = None
    target_score: Optional[float] = None
    important_topics: Optional[List[str]] = None
    syllabus_portion: Optional[str] = None
    prep_status: Optional[str] = None


class TopicValidationRequest(BaseModel):
    subject_id: str
    topic: str


class TopicValidationResponse(BaseModel):
    is_valid: bool
    warning: Optional[str] = None
    suggested_subject: Optional[str] = None


class TopicSuggestionResponse(BaseModel):
    subject_id: str
    subject_name: str
    portion: Optional[str] = None
    matched_portion: Optional[str] = None
    confidence: Optional[str] = None  # "high", "medium", "low", or None
    confidence_score: Optional[float] = None
    match_message: Optional[str] = None
    available_portions: List[str] = []
    suggestions: List[str]
    ai_ranked: Optional[bool] = False
    ai_provider: Optional[str] = None


class ExamResponse(BaseSchema):
    id: str
    user_id: str
    subject_id: str
    name: str
    exam_date: date
    exam_type: str
    target_score: float
    important_topics: List[Any]
    syllabus_portion: Optional[str] = None
    prep_status: str
    days_remaining: int = 0
    created_at: datetime
    subject: Optional[SubjectResponse] = None
    topic_warnings: Optional[List[dict]] = None


# -------------------------------------------------------------
# Study Planner & Task Schemas
# -------------------------------------------------------------
class StudyTaskCreate(BaseModel):
    subject_id: Optional[str] = None
    exam_id: Optional[str] = None
    plan_id: Optional[str] = None
    title: str
    topic_name: Optional[str] = None
    description: Optional[str] = ""
    reason: Optional[str] = None
    planning_score: Optional[float] = None
    missed_class_date: Optional[date] = None
    syllabus_portion: Optional[str] = None
    priority: Optional[str] = "medium"  # high, medium, low
    estimated_minutes: Optional[int] = 45
    actual_minutes: Optional[int] = None
    feedback: Optional[str] = None  # easy, okay, hard, need_more_time
    scheduled_date: date
    scheduled_time: Optional[time] = None
    confirm_budget_override: Optional[bool] = False


class StudyTaskUpdate(BaseModel):
    subject_id: Optional[str] = None
    title: Optional[str] = None
    topic_name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    estimated_minutes: Optional[int] = None
    actual_minutes: Optional[int] = None
    feedback: Optional[str] = None  # easy, okay, hard, need_more_time
    reason: Optional[str] = None
    planning_score: Optional[float] = None
    missed_class_date: Optional[date] = None
    syllabus_portion: Optional[str] = None
    scheduled_date: Optional[date] = None
    scheduled_time: Optional[time] = None
    is_completed: Optional[bool] = None
    confirm_budget_override: Optional[bool] = False


class TaskFeedbackRequest(BaseModel):
    feedback: Optional[str] = None  # easy, okay, hard, need_more_time
    actual_minutes: Optional[int] = None


class ReplanNeedMoreTimeRequest(BaseModel):
    extra_minutes: Optional[int] = 30
    actual_minutes: Optional[int] = None
    strategy: Optional[str] = "auto"  # auto, rebalance_tomorrow, spread_later, move_lower_priority, increase_study_time
    increase_daily_limit: Optional[bool] = False
    target_date: Optional[date] = None
    move_task_id: Optional[str] = None


class ReplanNeedMoreTimeResponse(BaseModel):
    success: bool
    requires_user_action: bool = False
    status: str
    message: Optional[str] = None
    explanation: Optional[str] = None
    scheduled_date: Optional[date] = None
    task_id: Optional[str] = None
    moved_task: Optional[Dict[str, Any]] = None
    options: Optional[List[Dict[str, Any]]] = None
    tomorrow_tasks: Optional[List[Dict[str, Any]]] = None
    daily_limit_minutes: Optional[int] = None


class StudyTaskResponse(BaseSchema):
    id: str
    user_id: str
    plan_id: Optional[str]
    subject_id: Optional[str]
    exam_id: Optional[str]
    title: str
    description: str
    priority: str
    estimated_minutes: int
    actual_minutes: Optional[int] = None
    feedback: Optional[str] = None
    reason: Optional[str] = ""
    topic_name: Optional[str] = None
    planning_score: Optional[float] = None
    missed_class_date: Optional[date] = None
    syllabus_portion: Optional[str] = None
    scheduled_date: date
    scheduled_time: Optional[time]
    is_completed: bool
    completed_at: Optional[datetime]
    order_index: int
    created_at: datetime
    subject: Optional[SubjectResponse] = None
    exam: Optional[ExamResponse] = None


class StudyPlanGenerateRequest(BaseModel):
    subject_ids: Optional[List[str]] = None
    exam_ids: Optional[List[str]] = None
    plan_days: Optional[int] = 7
    study_hours: Optional[int] = None
    study_minutes: Optional[int] = None
    daily_study_hours: Optional[float] = None
    subject_mode: Optional[str] = "all"  # 'all', 'choose', 'auto'
    planning_style: Optional[str] = "balanced"  # 'balanced', 'priority_aware'
    until_next_exam: Optional[bool] = False
    quick_review_mode: Optional[bool] = False
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    preferences: Optional[str] = None


class StudySessionLog(BaseModel):
    subject_id: Optional[str] = None
    task_id: Optional[str] = None
    duration_minutes: int
    mode: str = "custom"  # 30_min, 1_hour, 2_hour, custom
    session_breakdown: Optional[Dict[str, Any]] = {}
    notes: Optional[str] = ""
    started_at: datetime
    completed_at: datetime


class StudyWorkloadRecommendation(BaseModel):
    mood: Optional[str] = None  # great, good, okay, tired, stressful, or None
    checkin_status: str = "pending"  # pending, answered, skipped
    workload_mode: str  # high-focus, normal, paced, light-revision, essential-only
    headline: str
    guidance: List[str] = []
    suggested_block_minutes: int = 45
    urgent_exam_alert: Optional[str] = None
    today_task_count: int = 0
    unfinished_task_count: int = 0
    today_estimated_minutes: int = 0
    reschedule_candidates_count: int = 0
    disclaimer: str = "Academic workload pacing only. MedPilot does not provide medical or mental-health advice."


class StudyTaskRescheduleRequest(BaseModel):
    task_ids: Optional[List[str]] = None
    target_date: Optional[date] = None


class PlannerFeasibilityCheckRequest(BaseModel):
    plan_days: Optional[int] = 7
    study_hours: Optional[int] = None
    study_minutes: Optional[int] = None
    subject_mode: Optional[str] = "all"
    subject_ids: Optional[List[str]] = None
    planning_style: Optional[str] = "balanced"


class PlannerFeasibilityCheckResponse(BaseModel):
    is_insufficient: bool
    total_available_minutes: int
    available_hours: float
    candidate_topic_count: int
    estimated_needed_minutes: int
    estimated_needed_hours: float
    message: Optional[str] = None
    warning: Optional[str] = None
    options: List[str] = []


class ExamSyncStatusResponse(BaseModel):
    exam_sync_needed: bool
    message: Optional[str] = None
    changed_exams: List[Dict[str, Any]] = []
    unfinished_task_count: int = 0



# -------------------------------------------------------------
# Habit & Health Schemas (Non-punitive Routine & Wellbeing)
# -------------------------------------------------------------
class HabitCreate(BaseModel):
    name: str
    category: Optional[str] = "routine"  # sleep, hydration, nutrition, break, routine
    target_frequency: Optional[str] = "daily"
    selected_days: Optional[str] = "0,1,2,3,4,5,6"  # Comma-separated: 0=Mon..6=Sun
    reminder_time: Optional[str] = ""  # "", "morning", "afternoon", "evening", or "08:00"
    note: Optional[str] = ""
    is_paused: Optional[bool] = False
    order_index: Optional[int] = 0


class HabitUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    target_frequency: Optional[str] = None
    selected_days: Optional[str] = None
    reminder_time: Optional[str] = None
    note: Optional[str] = None
    is_paused: Optional[bool] = None
    order_index: Optional[int] = None
    is_active: Optional[bool] = None


class HabitResponse(BaseSchema):
    id: str
    user_id: str
    name: str
    category: str
    target_frequency: str
    selected_days: str = "0,1,2,3,4,5,6"
    reminder_time: str = ""
    note: str = ""
    is_paused: bool = False
    order_index: int = 0
    is_active: bool
    created_at: datetime
    today_completed: Optional[bool] = False
    today_status: Optional[str] = None
    today_notes: Optional[str] = ""


class HabitLogCreate(BaseModel):
    habit_id: str
    date: date
    status: str = "completed"  # completed, partial, skipped, missed
    notes: Optional[str] = ""


class HabitLogResponse(BaseSchema):
    id: str
    user_id: str
    habit_id: str
    date: date
    status: str
    notes: str
    created_at: datetime


class RoutineSettingUpdate(BaseModel):
    reminders_enabled: Optional[bool] = None
    pause_reminders_today: Optional[bool] = None
    paused_until_date: Optional[date] = None
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    morning_time: Optional[str] = None
    afternoon_time: Optional[str] = None
    evening_time: Optional[str] = None
    avoid_during_classes: Optional[bool] = None
    combine_nearby: Optional[bool] = None


class RoutineSettingResponse(BaseSchema):
    id: str
    user_id: str
    reminders_enabled: bool
    pause_reminders_today: bool
    paused_until_date: Optional[date] = None
    quiet_hours_enabled: bool
    quiet_hours_start: str
    quiet_hours_end: str
    morning_time: str
    afternoon_time: str
    evening_time: str
    avoid_during_classes: bool
    combine_nearby: bool


class WeeklySummaryDay(BaseModel):
    date: date
    day_name: str
    completed_count: int = 0
    partial_count: int = 0
    skipped_count: int = 0
    missed_count: int = 0
    total_count: int = 0
    percentage: float = 0.0


class WeeklySummaryResponse(BaseModel):
    days: List[WeeklySummaryDay]
    total_completed: int = 0
    total_partial: int = 0
    total_skipped: int = 0
    total_missed: int = 0
    total_routines: int = 0
    overall_percentage: float = 0.0


class WellbeingCheckInCreate(BaseModel):
    status: str = "answered"  # "answered" or "skipped"
    mood: Optional[str] = None  # "great", "good", "okay", "tired", "stressful"
    date: Optional[date] = None
    notes: Optional[str] = ""


class WellbeingCheckInResponse(BaseSchema):
    id: Optional[str] = None
    user_id: Optional[str] = None
    date: date
    status: str  # "pending", "answered", "skipped"
    mood: Optional[str] = None
    notes: Optional[str] = ""
    created_at: Optional[datetime] = None




# -------------------------------------------------------------
# Generated Resources & PYQ Schemas
# -------------------------------------------------------------
class ResourceGenerateRequest(BaseModel):
    subject_id: Optional[str] = None
    topic: str
    resource_type: str = "summary"  # summary, revision_sheet, mcq_bank, flashcards, study_notes
    additional_instructions: Optional[str] = ""


class GeneratedResourceResponse(BaseSchema):
    id: str
    user_id: str
    subject_id: Optional[str]
    title: str
    resource_type: str
    content_json: Dict[str, Any]
    pdf_storage_path: Optional[str]
    source_citations: List[Any]
    created_at: datetime
    subject: Optional[SubjectResponse] = None


class PYQAnalyzeRequest(BaseModel):
    subject_id: str
    exam_name: str
    years_covered: str
    raw_questions: str


class PYQAnalysisResponse(BaseSchema):
    id: str
    user_id: str
    subject_id: Optional[str]
    exam_name: str
    years_covered: str
    topic_frequencies: List[Any]
    repeated_patterns: List[Any]
    high_yield_topics: List[Any]
    guidance_notes: str
    created_at: datetime
    subject: Optional[SubjectResponse] = None


# -------------------------------------------------------------
# Friends & Sharing Schemas
# -------------------------------------------------------------
class FriendRequestSend(BaseModel):
    recipient_email: str


class FriendRequestRespond(BaseModel):
    request_id: str
    action: str = Field(description="'accept' or 'reject'")


class ShareResourceRequest(BaseModel):
    resource_id: str
    recipient_user_id: str
    permission: str = "view"  # view, download


# -------------------------------------------------------------
# AI Agent Request & Response Schemas
# -------------------------------------------------------------
class AgentWebSource(BaseModel):
    title: str
    url: str
    snippet: Optional[str] = ""
    source_type: Optional[str] = "web"  # web, youtube, pubmed, guideline


class AgentGeneratedImage(BaseModel):
    image_url: str
    title: str
    caption: Optional[str] = ""
    diagram_type: Optional[str] = "schematic"
    mermaid_code: Optional[str] = None


class FlashcardItem(BaseModel):
    front: str
    back: str
    difficulty: Optional[str] = "medium"  # easy, medium, hard
    topic: Optional[str] = ""


class SaveFlashcardsRequest(BaseModel):
    title: str
    cards: List[FlashcardItem]
    subject_id: Optional[str] = None


class ChatMessageItem(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    model: Optional[str] = None
    created_at: Optional[datetime] = None
    extra_data: Optional[Dict[str, Any]] = {}


class ConversationSummary(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message_count: int = 0
    last_message_preview: Optional[str] = None


class ConversationDetail(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    messages: List[ChatMessageItem] = []


class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Conversation"


class UpdateConversationRequest(BaseModel):
    title: str


class AgentChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = []
    subject_id: Optional[str] = None
    file_attachment: Optional[Dict[str, Any]] = None


class AgentRecommendationAction(BaseModel):
    action_type: str  # create_task, log_attendance, set_reminder, study_session, navigate, save_flashcards
    payload: Dict[str, Any]
    label: str


class AgentChatResponse(BaseModel):
    reply: str
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    agent_name: str = "MedPilot Agent"
    source_type: str = "ai_generated"  # student_data, web_search, diagram, flashcards, uploaded_file, ai_generated, unconfigured
    citations: List[str] = []
    web_sources: List[AgentWebSource] = []
    generated_image: Optional[AgentGeneratedImage] = None
    flashcards: List[FlashcardItem] = []
    recommended_actions: List[AgentRecommendationAction] = []
    disclaimer: str = "Educational & academic support only. MedPilot does not provide medical diagnosis or treatment advice."


class FlexibleStudyModeRequest(BaseModel):
    duration_minutes: int = Field(description="30, 60, or 120 minutes")
    subject_id: Optional[str] = None
    topic: Optional[str] = None


# -------------------------------------------------------------
# Account & Data Management Schemas
# -------------------------------------------------------------
class ResetAllDataRequest(BaseModel):
    confirm_text: str = Field(description="Must match 'RESET'")


class DeleteAccountRequest(BaseModel):
    confirm_text: str = Field(description="Must match 'DELETE'")
    password: Optional[str] = ""


class AccountActionResponse(BaseModel):
    success: bool = True
    message: str
    details: Optional[Dict[str, Any]] = None

