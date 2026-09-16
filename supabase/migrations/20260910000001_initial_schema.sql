-- ============================================================
-- MEDPILOT DATABASE SCHEMA MIGRATION
-- "Your AI Academic Companion" for MBBS Students
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Profiles Table
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY, -- references auth.users(id) in Supabase
    email TEXT,
    full_name TEXT NOT NULL DEFAULT '',
    college TEXT NOT NULL DEFAULT '',
    year_of_study TEXT NOT NULL DEFAULT 'MBBS 1st Year',
    target_attendance_percentage NUMERIC(5, 2) NOT NULL DEFAULT 75.00,
    daily_study_target_minutes INT NOT NULL DEFAULT 180,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Subjects Table
CREATE TABLE IF NOT EXISTS subjects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT DEFAULT '',
    color TEXT NOT NULL DEFAULT '#0D9488',
    target_attendance NUMERIC(5, 2) NOT NULL DEFAULT 75.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Timetable Rules (Level A - Recurring Rules)
CREATE TABLE IF NOT EXISTS timetable_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    day_of_week INT NOT NULL CHECK (day_of_week >= 0 AND day_of_week <= 6), -- 0=Mon, 6=Sun
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    faculty TEXT DEFAULT '',
    room TEXT DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Class Occurrences (Level B - Individual Occurrences)
CREATE TABLE IF NOT EXISTS class_occurrences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    rule_id UUID REFERENCES timetable_rules(id) ON DELETE SET NULL,
    subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    faculty TEXT DEFAULT '',
    room TEXT DEFAULT '',
    status TEXT NOT NULL CHECK (status IN ('scheduled', 'completed', 'cancelled', 'rescheduled')) DEFAULT 'scheduled',
    original_date DATE,
    original_start_time TIME,
    is_extra_class BOOLEAN NOT NULL DEFAULT false,
    notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Class Topics (Multiple topics per individual class occurrence)
CREATE TABLE IF NOT EXISTS class_topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    occurrence_id UUID NOT NULL REFERENCES class_occurrences(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    order_index INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. Attendance Table
CREATE TABLE IF NOT EXISTS attendance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    occurrence_id UUID NOT NULL REFERENCES class_occurrences(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('present', 'absent', 'not_marked')) DEFAULT 'not_marked',
    marked_at TIMESTAMPTZ,
    notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_user_occurrence UNIQUE(user_id, occurrence_id)
);

-- 7. Exams Table
CREATE TABLE IF NOT EXISTS exams (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    exam_date DATE NOT NULL,
    exam_type TEXT NOT NULL DEFAULT 'Internal Assessment',
    target_score NUMERIC(5, 2) DEFAULT 75.0,
    important_topics JSONB DEFAULT '[]'::jsonb,
    prep_status TEXT NOT NULL CHECK (prep_status IN ('not_started', 'in_progress', 'well_prepared', 'revision_needed')) DEFAULT 'not_started',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. Study Plans & Tasks
CREATE TABLE IF NOT EXISTS study_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    total_planned_minutes INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'archived')) DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS study_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    plan_id UUID REFERENCES study_plans(id) ON DELETE CASCADE,
    subject_id UUID REFERENCES subjects(id) ON DELETE SET NULL,
    exam_id UUID REFERENCES exams(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    priority TEXT NOT NULL CHECK (priority IN ('high', 'medium', 'low')) DEFAULT 'medium',
    estimated_minutes INT NOT NULL DEFAULT 45,
    scheduled_date DATE NOT NULL,
    scheduled_time TIME,
    is_completed BOOLEAN NOT NULL DEFAULT false,
    completed_at TIMESTAMPTZ,
    order_index INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. Study Sessions
CREATE TABLE IF NOT EXISTS study_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    subject_id UUID REFERENCES subjects(id) ON DELETE SET NULL,
    task_id UUID REFERENCES study_tasks(id) ON DELETE SET NULL,
    duration_minutes INT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('30_min', '1_hour', '2_hour', 'custom')) DEFAULT 'custom',
    session_breakdown JSONB DEFAULT '{}'::jsonb,
    notes TEXT DEFAULT '',
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. Health & Habits (Non-punitive)
CREATE TABLE IF NOT EXISTS habits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('sleep', 'hydration', 'nutrition', 'break', 'routine')) DEFAULT 'routine',
    target_frequency TEXT NOT NULL DEFAULT 'daily',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS habit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    habit_id UUID NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'missed', 'skipped')) DEFAULT 'missed',
    notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_habit_user_date UNIQUE(habit_id, user_id, date)
);

-- 11. Notifications & Reminders
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('attendance_reminder', 'low_attendance_alert', 'exam_countdown', 'study_reminder', 'habit_reminder')),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    related_occurrence_id UUID REFERENCES class_occurrences(id) ON DELETE SET NULL,
    is_read BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 12. Generated Study Resources
CREATE TABLE IF NOT EXISTS generated_resources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    subject_id UUID REFERENCES subjects(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    resource_type TEXT NOT NULL CHECK (resource_type IN ('summary', 'revision_sheet', 'mcq_bank', 'flashcards', 'study_notes', 'pyq_analysis')),
    content_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    pdf_storage_path TEXT,
    source_citations JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 13. PYQ Analyses
CREATE TABLE IF NOT EXISTS pyq_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    subject_id UUID REFERENCES subjects(id) ON DELETE SET NULL,
    exam_name TEXT NOT NULL,
    years_covered TEXT NOT NULL,
    topic_frequencies JSONB NOT NULL DEFAULT '[]'::jsonb,
    repeated_patterns JSONB NOT NULL DEFAULT '[]'::jsonb,
    high_yield_topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    guidance_notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 14. Friends & Private Resource Sharing
CREATE TABLE IF NOT EXISTS friends (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    friend_user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_friendship UNIQUE(user_id, friend_user_id)
);

CREATE TABLE IF NOT EXISTS friend_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sender_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    receiver_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('pending', 'accepted', 'rejected')) DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_friend_request UNIQUE(sender_id, receiver_id)
);

CREATE TABLE IF NOT EXISTS shared_resources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resource_id UUID NOT NULL REFERENCES generated_resources(id) ON DELETE CASCADE,
    sender_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    receiver_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    permission TEXT NOT NULL CHECK (permission IN ('view', 'download')) DEFAULT 'view',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_shared_resource UNIQUE(resource_id, receiver_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_occurrences_user_date ON class_occurrences(user_id, date);
CREATE INDEX IF NOT EXISTS idx_attendance_user_occurrence ON attendance(user_id, occurrence_id);
CREATE INDEX IF NOT EXISTS idx_tasks_user_date ON study_tasks(user_id, scheduled_date);
CREATE INDEX IF NOT EXISTS idx_habit_logs_date ON habit_logs(user_id, date);
