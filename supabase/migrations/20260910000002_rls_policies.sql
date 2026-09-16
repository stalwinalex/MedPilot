-- ============================================================
-- ROW LEVEL SECURITY (RLS) POLICIES FOR MEDPILOT
-- ============================================================

-- Enable RLS on all tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE timetable_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE class_occurrences ENABLE ROW LEVEL SECURITY;
ALTER TABLE class_topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE exams ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE habits ENABLE ROW LEVEL SECURITY;
ALTER TABLE habit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_resources ENABLE ROW LEVEL SECURITY;
ALTER TABLE pyq_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE friends ENABLE ROW LEVEL SECURITY;
ALTER TABLE friend_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE shared_resources ENABLE ROW LEVEL SECURITY;

-- Profiles: user can only select/update their own profile
CREATE POLICY "Users can view own profile" ON profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile" ON profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- Standard User Data Policies: user can CRUD where user_id = auth.uid()
CREATE POLICY "Users can CRUD own subjects" ON subjects
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own timetable_rules" ON timetable_rules
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own class_occurrences" ON class_occurrences
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD class_topics on own occurrences" ON class_topics
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM class_occurrences
            WHERE class_occurrences.id = class_topics.occurrence_id
            AND class_occurrences.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can CRUD own attendance" ON attendance
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own exams" ON exams
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own study_plans" ON study_plans
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own study_tasks" ON study_tasks
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own study_sessions" ON study_sessions
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own habits" ON habits
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own habit_logs" ON habit_logs
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own notifications" ON notifications
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own generated_resources" ON generated_resources
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own pyq_analyses" ON pyq_analyses
    FOR ALL USING (auth.uid() = user_id);

-- Friends & Private Sharing RLS
CREATE POLICY "Users can view their friendships" ON friends
    FOR SELECT USING (auth.uid() = user_id OR auth.uid() = friend_user_id);

CREATE POLICY "Users can manage their friendships" ON friends
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view their friend requests" ON friend_requests
    FOR SELECT USING (auth.uid() = sender_id OR auth.uid() = receiver_id);

CREATE POLICY "Users can send friend requests" ON friend_requests
    FOR INSERT WITH CHECK (auth.uid() = sender_id);

CREATE POLICY "Receivers can update friend request status" ON friend_requests
    FOR UPDATE USING (auth.uid() = receiver_id);

-- Shared Resources RLS: sender or recipient can access
CREATE POLICY "Senders can manage shared resources" ON shared_resources
    FOR ALL USING (auth.uid() = sender_id);

CREATE POLICY "Recipients can view resources shared with them" ON shared_resources
    FOR SELECT USING (auth.uid() = receiver_id);

CREATE POLICY "Recipients can view shared resource content" ON generated_resources
    FOR SELECT USING (
        auth.uid() = user_id OR
        EXISTS (
            SELECT 1 FROM shared_resources
            WHERE shared_resources.resource_id = generated_resources.id
            AND shared_resources.receiver_id = auth.uid()
        )
    );
