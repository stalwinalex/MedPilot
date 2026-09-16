import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles,
  CheckSquare,
  Clock,
  GraduationCap,
  BookOpen,
  HeartPulse,
  Calendar,
  Check,
  ChevronRight,
  RefreshCw,
  Plus,
  Play,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  X
} from 'lucide-react';
import { apiRequest } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useAttendanceNotification } from '../context/AttendanceNotificationContext';
import ClassCheckInModal from '../components/ClassCheckInModal';

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { unmarkedClasses, unmarkedCount, openQueueCheckIn, markAttendance, markingId } = useAttendanceNotification();

  // State
  const [loading, setLoading] = useState(true);
  const [attendance, setAttendance] = useState(null);
  const [todayClasses, setTodayClasses] = useState([]);
  const [upcomingExams, setUpcomingExams] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [habits, setHabits] = useState([]);
  const [wellbeingCheckIn, setWellbeingCheckIn] = useState(null);
  const [wbSubmitting, setWbSubmitting] = useState(false);
  const [simulateAfter4PM, setSimulateAfter4PM] = useState(false);

  // Check-in modal states
  const [checkInOcc, setCheckInOcc] = useState(null);

  // Subtle AI Assistant recommendation state
  const [recommendation, setRecommendation] = useState(null);
  const [recLoading, setRecLoading] = useState(false);

  // Before/After class briefing modal
  const [briefingModal, setBriefingModal] = useState(null);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const todayStr = new Date().toISOString().split('T')[0];

      const [attData, occData, examData, taskData, habitData, wbData] = await Promise.all([
        apiRequest('/attendance/summary'),
        apiRequest(`/timetable/occurrences?start_date=${todayStr}&end_date=${todayStr}`),
        apiRequest('/exams/'),
        apiRequest(`/planner/tasks?scheduled_date=${todayStr}`),
        apiRequest(`/habits/?target_date=${todayStr}`),
        apiRequest('/habits/wellbeing/today').catch(() => ({ status: 'pending', mood: null }))
      ]);

      setAttendance(attData);
      setTodayClasses(occData);
      setUpcomingExams(examData.slice(0, 3));
      setTasks(taskData);
      setHabits(habitData);
      setWellbeingCheckIn(wbData);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const triggerWhatShouldIDoNow = async () => {
    setRecLoading(true);
    try {
      const data = await apiRequest('/agent/what-should-i-do-now', { method: 'POST' });
      setRecommendation(data);
    } catch (err) {
      console.error('Error in What Should I Do Now agent:', err);
    } finally {
      setRecLoading(false);
    }
  };

  const toggleTaskCompleted = async (taskId, currentStatus) => {
    try {
      await apiRequest(`/planner/tasks/${taskId}`, {
        method: 'PUT',
        body: JSON.stringify({ is_completed: !currentStatus })
      });
      fetchDashboardData();
    } catch (err) {
      console.error('Error toggling task:', err);
    }
  };

  const toggleHabit = async (habitId, currentStatus) => {
    try {
      const nextStatus = currentStatus === 'completed' ? 'missed' : 'completed';
      const todayStr = new Date().toISOString().split('T')[0];
      await apiRequest('/habits/log', {
        method: 'POST',
        body: JSON.stringify({ habit_id: habitId, date: todayStr, status: nextStatus })
      });
      fetchDashboardData();
    } catch (err) {
      console.error('Error logging habit:', err);
    }
  };

  const showBeforeClass = async (occId) => {
    try {
      const data = await apiRequest(`/agent/before-class/${occId}`);
      setBriefingModal({ type: 'before', data });
    } catch (err) {
      alert(err.message);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[65vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-[#72C9BE] border-t-transparent animate-spin" />
          <p className="text-xs text-[#6E7785] font-medium">Preparing your academic day...</p>
        </div>
      </div>
    );
  }

  // Greeting helper
  const hour = new Date().getHours();
  const timeGreeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const firstName = user?.full_name?.split(' ')[0] || 'Alex';

  // Overview metrics calculation
  const nowTimeStr = new Date().toTimeString().slice(0, 5);
  const nextClass = todayClasses.find((c) => c.end_time.slice(0, 5) > nowTimeStr && c.status !== 'cancelled');
  const todayStr = new Date().toISOString().split('T')[0];
  const todayUnmarked = unmarkedClasses.filter((c) => c.date === todayStr);
  const earlierUnmarked = unmarkedClasses.filter((c) => c.date !== todayStr);
  const completedTasksCount = tasks.filter((t) => t.is_completed).length;
  const nextExam = upcomingExams[0];

  return (
    <div className="space-y-8 pb-12">
      {/* 1. EDITORIAL GREETING */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="space-y-1">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#26313F]">
            {timeGreeting}, {firstName}
          </h1>
          <p className="text-sm text-[#6E7785]">
            Here's what's happening today.
          </p>
        </div>

        {/* Discreet testing link if before 4 PM */}
        {new Date().getHours() < 16 && !simulateAfter4PM && wellbeingCheckIn?.status === 'pending' && (
          <button
            type="button"
            onClick={() => setSimulateAfter4PM(true)}
            className="text-[11px] text-[#6E7785] hover:text-[#26313F] font-medium self-start sm:self-auto underline decoration-dashed"
          >
            Simulate 4:00 PM Check-in
          </button>
        )}
      </div>

      {/* Subtle Daily Wellbeing Check-in Card (After 4:00 PM) */}
      {(new Date().getHours() >= 16 || simulateAfter4PM) && wellbeingCheckIn?.status === 'pending' && (
        <div className="p-4 sm:p-5 rounded-2xl bg-white border border-[#E7EAF0] shadow-card flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-all">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="p-1 rounded-lg bg-[#CFEDE7] text-[#1A4B43]">
                <HeartPulse className="w-4 h-4" />
              </span>
              <h3 className="text-sm font-bold text-[#26313F]">How did today feel?</h3>
              {simulateAfter4PM && (
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-[#F3DFAB]/50 text-[#6B4E17]">
                  Demo 4:00 PM
                </span>
              )}
            </div>
            <p className="text-xs text-[#6E7785]">
              Optional 1-tap check-in to pace tonight's study workload recommendations.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {[
              { id: 'great', emoji: '😄', label: 'Great', bg: 'hover:bg-[#CFEDE7] hover:border-[#72C9BE] text-[#1A4B43]' },
              { id: 'good', emoji: '🙂', label: 'Good', bg: 'hover:bg-[#B7D4F4]/40 hover:border-[#B7D4F4] text-[#1E3A8A]' },
              { id: 'okay', emoji: '😐', label: 'Okay', bg: 'hover:bg-[#F2F5F8] hover:border-[#CADFCB] text-[#26313F]' },
              { id: 'tired', emoji: '😴', label: 'Tired', bg: 'hover:bg-[#F3DFAB]/40 hover:border-[#F3DFAB] text-[#6B4E17]' },
              { id: 'stressful', emoji: '😣', label: 'Stressful', bg: 'hover:bg-[#EABFC5]/40 hover:border-[#EABFC5] text-[#69242E]' },
            ].map((opt) => (
              <button
                key={opt.id}
                type="button"
                disabled={wbSubmitting}
                onClick={async () => {
                  setWbSubmitting(true);
                  try {
                    const res = await apiRequest('/habits/wellbeing', {
                      method: 'POST',
                      body: JSON.stringify({ status: 'answered', mood: opt.id })
                    });
                    setWellbeingCheckIn(res);
                  } catch (e) {
                    console.error(e);
                  } finally {
                    setWbSubmitting(false);
                  }
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-[#E7EAF0] bg-[#F7F8FC] text-xs font-semibold transition-all cursor-pointer ${opt.bg}`}
              >
                <span>{opt.emoji}</span>
                <span>{opt.label}</span>
              </button>
            ))}

            <button
              type="button"
              disabled={wbSubmitting}
              onClick={async () => {
                setWbSubmitting(true);
                try {
                  const res = await apiRequest('/habits/wellbeing', {
                    method: 'POST',
                    body: JSON.stringify({ status: 'skipped' })
                  });
                  setWellbeingCheckIn(res);
                } catch (e) {
                  console.error(e);
                } finally {
                  setWbSubmitting(false);
                }
              }}
              className="text-xs text-[#6E7785] hover:text-[#26313F] font-medium ml-1 cursor-pointer underline"
            >
              Skip
            </button>
          </div>
        </div>
      )}

      {/* 2. FOUR SUBTLE OVERVIEW CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Next Class */}
        <div
          onClick={() => navigate('/timetable')}
          className="bg-white rounded-2xl p-5 border border-[#E7EAF0] shadow-card hover:border-[#72C9BE]/50 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-xs text-[#6E7785] mb-2">
            <span className="font-medium">Next Class</span>
            <div className="p-1.5 rounded-xl bg-[#CFEDE7]/50 text-[#1A4B43] group-hover:bg-[#CFEDE7] transition-colors">
              <Calendar className="w-3.5 h-3.5" />
            </div>
          </div>
          {nextClass ? (
            <div className="space-y-0.5">
              <h4 className="text-base font-bold text-[#26313F] truncate">{nextClass.subject?.name}</h4>
              <p className="text-xs text-[#6E7785] flex items-center gap-1 font-mono">
                <Clock className="w-3 h-3 text-[#72C9BE]" />
                <span>{nextClass.start_time.slice(0, 5)} {nextClass.room ? `• ${nextClass.room}` : ''}</span>
              </p>
            </div>
          ) : (
            <div className="space-y-0.5">
              <h4 className="text-base font-bold text-[#26313F]">All clear</h4>
              <p className="text-xs text-[#6E7785]">No upcoming classes today</p>
            </div>
          )}
        </div>

        {/* Attendance */}
        <div
          onClick={() => navigate('/attendance')}
          className="bg-white rounded-2xl p-5 border border-[#E7EAF0] shadow-card hover:border-[#72C9BE]/50 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-xs text-[#6E7785] mb-2">
            <span className="font-medium">Attendance</span>
            <div className="p-1.5 rounded-xl bg-[#CADFCB]/40 text-[#1A4B43] group-hover:bg-[#CADFCB]/70 transition-colors">
              <CheckSquare className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="space-y-0.5">
            <div className="flex items-baseline gap-2">
              <h4 className="text-2xl font-bold text-[#26313F]">
                {attendance?.total_conducted > 0 && attendance?.overall_percentage !== null
                  ? `${attendance.overall_percentage}%`
                  : '—'}
              </h4>
              <span className="text-xs text-[#6E7785]">target {attendance?.target_percentage || 75}%</span>
            </div>
            <p className="text-xs text-[#6E7785]">
              {attendance?.total_attended || 0} of {attendance?.total_conducted || 0} attended
            </p>
          </div>
        </div>

        {/* Study Tasks */}
        <div
          onClick={() => navigate('/planner')}
          className="bg-white rounded-2xl p-5 border border-[#E7EAF0] shadow-card hover:border-[#72C9BE]/50 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-xs text-[#6E7785] mb-2">
            <span className="font-medium">Study Tasks</span>
            <div className="p-1.5 rounded-xl bg-[#B7D4F4]/40 text-[#1E3A8A] group-hover:bg-[#B7D4F4]/70 transition-colors">
              <BookOpen className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="space-y-0.5">
            <h4 className="text-base font-bold text-[#26313F]">
              {tasks.length > 0 ? `${completedTasksCount} of ${tasks.length} done` : 'No tasks today'}
            </h4>
            <p className="text-xs text-[#6E7785]">
              {tasks.length > 0
                ? `${tasks.length - completedTasksCount} tasks remaining`
                : 'Plan your study goals'}
            </p>
          </div>
        </div>

        {/* Next Exam */}
        <div
          onClick={() => navigate('/exams')}
          className="bg-white rounded-2xl p-5 border border-[#E7EAF0] shadow-card hover:border-[#72C9BE]/50 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-xs text-[#6E7785] mb-2">
            <span className="font-medium">Next Exam</span>
            <div className="p-1.5 rounded-xl bg-[#D4C8F4]/40 text-[#3C2D69] group-hover:bg-[#D4C8F4]/70 transition-colors">
              <GraduationCap className="w-3.5 h-3.5" />
            </div>
          </div>
          {nextExam ? (
            <div className="space-y-0.5">
              <h4 className="text-base font-bold text-[#26313F] truncate">{nextExam.name}</h4>
              <p className="text-xs text-[#6E7785]">
                {nextExam.days_remaining === 0 ? 'Today' : `${nextExam.days_remaining} days away`} • {nextExam.subject?.name || 'Exam'}
              </p>
            </div>
          ) : (
            <div className="space-y-0.5">
              <h4 className="text-base font-bold text-[#26313F]">No upcoming exams</h4>
              <p className="text-xs text-[#6E7785]">Add internal or university tests</p>
            </div>
          )}
        </div>
      </div>

      {/* 3. CALM ATTENDANCE SUMMARY (Instead of 41 alarm cards) */}
      {unmarkedCount > 0 && (
        <div className="bg-white rounded-2xl border border-[#F3DFAB] p-5 shadow-soft flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-[#F3DFAB]/50 text-[#6B4E17] flex items-center justify-center shrink-0">
              <CheckSquare className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[#26313F]">Attendance to complete</h3>
              <p className="text-xs text-[#6E7785] mt-0.5">
                <span className="font-semibold text-[#26313F]">{unmarkedCount} classes waiting</span>
                {' • '}
                <span>{todayUnmarked.length} today</span>
                {earlierUnmarked.length > 0 && <span>, {earlierUnmarked.length} earlier</span>}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
            {todayUnmarked.length > 0 && (
              <button
                type="button"
                onClick={openQueueCheckIn}
                className="px-3.5 py-1.5 rounded-xl bg-[#CFEDE7] hover:bg-[#b5e7dc] text-[#1A4B43] text-xs font-semibold transition-all cursor-pointer"
              >
                Complete today's
              </button>
            )}
            <button
              type="button"
              onClick={() => navigate('/attendance')}
              className="px-3.5 py-1.5 rounded-xl bg-[#F2F5F8] hover:bg-[#E7EAF0] text-[#26313F] text-xs font-medium border border-[#E7EAF0] transition-all cursor-pointer"
            >
              View all
            </button>
          </div>
        </div>
      )}

      {/* 4. SUBTLE AI COMPANION CARD (Non-intrusive) */}
      <div className="bg-white rounded-2xl border border-[#E7EAF0] p-5 shadow-card space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-[#CFEDE7] text-[#1A4B43] shrink-0">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[#26313F]">Study Recommendation</h3>
              <p className="text-xs text-[#6E7785]">
                Ask MedPilot to inspect your live schedule, exams, and attendance to suggest what to do next.
              </p>
            </div>
          </div>

          <button
            onClick={triggerWhatShouldIDoNow}
            disabled={recLoading}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-[#72C9BE] text-[#13443e] hover:bg-[#5db8ad] text-xs font-semibold transition-all shadow-sm active:scale-98 disabled:opacity-50 shrink-0 cursor-pointer"
          >
            <Sparkles className={`w-3.5 h-3.5 ${recLoading ? 'animate-spin' : ''}`} />
            <span>{recLoading ? 'Checking schedule...' : 'What should I do now?'}</span>
          </button>
        </div>

        {/* Recommendation details if opened */}
        {recommendation && (
          <div className="pt-3 border-t border-[#E7EAF0] space-y-3 animate-in fade-in">
            <div className="p-4 rounded-xl bg-[#F7F8FC] border border-[#E7EAF0] text-xs leading-relaxed text-[#26313F] whitespace-pre-line">
              {recommendation.reply}
            </div>

            {recommendation.recommended_actions?.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {recommendation.recommended_actions.map((act, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      if (act.action_type === 'create_task') {
                        apiRequest('/planner/tasks', {
                          method: 'POST',
                          body: JSON.stringify({
                            title: act.payload.title,
                            priority: act.payload.priority || 'high',
                            estimated_minutes: act.payload.estimated_minutes || 45,
                            scheduled_date: new Date().toISOString().split('T')[0]
                          })
                        }).then(() => {
                          fetchDashboardData();
                          alert(`Task created: "${act.payload.title}"`);
                        });
                      } else if (act.action_type === 'study_session') {
                        navigate('/assistant?study_mode=true');
                      }
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[#CFEDE7]/60 text-[#1A4B43] hover:bg-[#CFEDE7] transition-colors"
                  >
                    <Play className="w-3 h-3 text-[#3D8C82]" />
                    <span>{act.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 5. MAIN CONTENT LAYOUT: Today's Schedule & Study Plan */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* COLUMN 1 & 2: TODAY'S SCHEDULE */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-[#26313F]">Today's Schedule</h2>
              <p className="text-xs text-[#6E7785]">
                {new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}
              </p>
            </div>
            <button
              onClick={() => navigate('/timetable')}
              className="text-xs font-semibold text-[#3D8C82] hover:underline flex items-center gap-1"
            >
              <span>Weekly View</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {todayClasses.length === 0 ? (
            <div className="p-8 rounded-2xl bg-white border border-[#E7EAF0] text-center space-y-2 shadow-soft">
              <Calendar className="w-8 h-8 text-[#8E97A6] mx-auto mb-1" />
              <p className="text-[#26313F] text-sm font-semibold">Your timetable is clear today</p>
              <p className="text-xs text-[#6E7785]">Enjoy your free hours or catch up on revision.</p>
              <button
                onClick={() => navigate('/timetable')}
                className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#F2F5F8] text-[#26313F] border border-[#E7EAF0] text-xs font-medium hover:bg-[#E7EAF0]"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Class</span>
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {todayClasses.map((occ) => {
                const attStatus = occ.attendance?.status || 'not_marked';
                const isCancelled = occ.status === 'cancelled';
                const startTimeStr = occ.start_time.slice(0, 5);
                const endTimeStr = occ.end_time.slice(0, 5);
                const isPast = endTimeStr <= nowTimeStr;
                const isInProgress = startTimeStr <= nowTimeStr && nowTimeStr < endTimeStr;

                return (
                  <div
                    key={occ.id}
                    className={`p-4 rounded-2xl border transition-all bg-white shadow-soft ${
                      isCancelled
                        ? 'opacity-60 border-[#E7EAF0]'
                        : 'border-[#E7EAF0] hover:border-[#72C9BE]/50'
                    }`}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="space-y-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-bold text-[#26313F] text-sm">
                            {occ.subject?.name || 'Class'}
                          </span>
                          {occ.subject?.code && (
                            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[#F2F5F8] text-[#6E7785]">
                              {occ.subject.code}
                            </span>
                          )}
                          {isCancelled ? (
                            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#E7EAF0] text-[#4B5563]">
                              Cancelled
                            </span>
                          ) : attStatus === 'present' ? (
                            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#CFEDE7] text-[#1A4B43] flex items-center gap-1">
                              <Check className="w-3 h-3 stroke-[2.5]" /> Present
                            </span>
                          ) : attStatus === 'absent' ? (
                            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#EABFC5]/40 text-[#69242E]">
                              Absent
                            </span>
                          ) : isInProgress ? (
                            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#CFEDE7] text-[#1A4B43]">
                              In Progress
                            </span>
                          ) : isPast ? (
                            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#F3DFAB]/50 text-[#6B4E17]">
                              Waiting Check-in
                            </span>
                          ) : (
                            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#B7D4F4]/30 text-[#1E3A8A]">
                              Upcoming
                            </span>
                          )}
                        </div>

                        <div className="flex flex-wrap items-center gap-3 text-xs text-[#6E7785]">
                          <span className="flex items-center gap-1 font-mono text-[#26313F]">
                            <Clock className="w-3.5 h-3.5 text-[#72C9BE]" />
                            {startTimeStr} – {endTimeStr}
                          </span>
                          {occ.room && <span>Room {occ.room}</span>}
                          {occ.faculty && <span>• {occ.faculty}</span>}
                        </div>
                      </div>

                      {/* Action buttons */}
                      <div className="flex items-center gap-2 shrink-0 pt-2 sm:pt-0">
                        {isCancelled ? (
                          <button
                            onClick={async () => {
                              await apiRequest(`/timetable/occurrences/${occ.id}/toggle-cancel`, { method: 'POST' });
                              fetchDashboardData();
                            }}
                            className="px-3 py-1.5 rounded-xl bg-[#F2F5F8] text-[#26313F] text-xs font-medium hover:bg-[#E7EAF0]"
                          >
                            Restore
                          </button>
                        ) : (
                          <>
                            {isPast || attStatus !== 'not_marked' ? (
                              <button
                                onClick={() => setCheckInOcc(occ)}
                                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                                  attStatus === 'not_marked'
                                    ? 'bg-[#CFEDE7] hover:bg-[#b5e7dc] text-[#1A4B43]'
                                    : 'bg-[#F2F5F8] hover:bg-[#E7EAF0] text-[#26313F] border border-[#E7EAF0]'
                                }`}
                              >
                                {attStatus === 'not_marked' ? 'Check In' : 'Edit'}
                              </button>
                            ) : (
                              <span className="text-[11px] text-[#8E97A6]">
                                {isInProgress ? 'Check-in opens when class ends' : `Starts at ${startTimeStr}`}
                              </span>
                            )}

                            <button
                              onClick={() => showBeforeClass(occ.id)}
                              title="Before-class high-yield preview"
                              className="px-2.5 py-1.5 rounded-xl text-xs text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] transition-colors"
                            >
                              Preview
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* TODAY'S STUDY PLAN */}
          <div className="pt-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-[#26313F]">Today's Study Plan</h2>
                <p className="text-xs text-[#6E7785]">Focused tasks for your academic goals</p>
              </div>
              <button
                onClick={() => navigate('/planner')}
                className="text-xs font-semibold text-[#3D8C82] hover:underline flex items-center gap-1"
              >
                <span>Full Planner</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>

            {tasks.length === 0 ? (
              <div className="p-6 rounded-2xl bg-white border border-[#E7EAF0] text-center text-xs text-[#6E7785] shadow-soft">
                Nothing planned for today. Tap below to add a quick task!
                <div className="mt-2">
                  <button
                    onClick={() => navigate('/planner')}
                    className="inline-flex items-center gap-1 text-xs text-[#3D8C82] font-semibold hover:underline"
                  >
                    <Plus className="w-3 h-3" /> Add Study Task
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                {tasks.map((t) => (
                  <div
                    key={t.id}
                    onClick={() => toggleTaskCompleted(t.id, t.is_completed)}
                    className="p-3.5 rounded-xl bg-white border border-[#E7EAF0] hover:border-[#72C9BE]/50 flex items-center justify-between gap-3 cursor-pointer transition-all shadow-soft"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div
                        className={`w-4 h-4 rounded-md border flex items-center justify-center transition-colors ${
                          t.is_completed
                            ? 'bg-[#72C9BE] border-[#72C9BE] text-[#13443e]'
                            : 'border-[#D9DDE5] bg-white'
                        }`}
                      >
                        {t.is_completed && <Check className="w-3 h-3 stroke-[3]" />}
                      </div>
                      <span
                        className={`text-sm font-medium truncate ${
                          t.is_completed ? 'line-through text-[#8E97A6]' : 'text-[#26313F]'
                        }`}
                      >
                        {t.title}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[11px] text-[#6E7785] font-mono">{t.estimated_minutes}m</span>
                      <span
                        className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                          t.priority === 'high'
                            ? 'bg-[#EABFC5]/40 text-[#69242E]'
                            : t.priority === 'medium'
                            ? 'bg-[#F3DFAB]/50 text-[#6B4E17]'
                            : 'bg-[#F2F5F8] text-[#6E7785]'
                        }`}
                      >
                        {t.priority}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* COLUMN 3: ROUTINE CHECK-IN & EXAMS */}
        <div className="space-y-6">
          {/* Routine & Wellbeing Widget */}
          <div className="p-5 rounded-2xl bg-white border border-[#E7EAF0] shadow-card space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-[#26313F] text-sm flex items-center gap-2">
                <HeartPulse className="w-4 h-4 text-[#72C9BE]" />
                <span>Routine & Wellbeing</span>
              </h3>
              <button
                onClick={() => navigate('/habits')}
                className="text-xs text-[#3D8C82] font-medium hover:underline"
              >
                Manage
              </button>
            </div>
            <p className="text-xs text-[#6E7785]">
              Calm daily habits. Missed routines are simply marked missed—never penalized.
            </p>

            <div className="space-y-2 pt-1">
              {habits.length === 0 ? (
                <p className="text-xs text-[#8E97A6] text-center py-3">No routines scheduled for today.</p>
              ) : (
                habits.slice(0, 4).map((h) => (
                  <div
                    key={h.id}
                    onClick={() => toggleHabit(h.id, h.today_status)}
                    className="flex items-center justify-between p-2.5 rounded-xl bg-[#F7F8FC] border border-[#E7EAF0] hover:border-[#72C9BE]/50 cursor-pointer text-xs transition-colors"
                  >
                    <span
                      className={`truncate ${
                        h.today_status === 'completed'
                          ? 'text-[#8E97A6] line-through'
                          : h.today_status === 'skipped'
                          ? 'text-[#8E97A6] line-through'
                          : 'text-[#26313F]'
                      }`}
                    >
                      {h.name}
                    </span>
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                        h.today_status === 'completed'
                          ? 'bg-[#CFEDE7] text-[#1A4B43]'
                          : h.today_status === 'partial'
                          ? 'bg-[#B7D4F4]/40 text-[#1E3A8A]'
                          : h.today_status === 'skipped'
                          ? 'bg-[#F2F5F8] text-[#6E7785] border border-[#E7EAF0]'
                          : 'bg-white text-[#6E7785] border border-[#E7EAF0]'
                      }`}
                    >
                      {h.today_status === 'completed'
                        ? 'Done'
                        : h.today_status === 'partial'
                        ? 'Partly'
                        : h.today_status === 'skipped'
                        ? 'Skipped'
                        : 'Check in'}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Upcoming Exams Widget */}
          <div className="p-5 rounded-2xl bg-white border border-[#E7EAF0] shadow-card space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-[#26313F] text-sm flex items-center gap-2">
                <GraduationCap className="w-4 h-4 text-[#D4C8F4]" />
                <span>Upcoming Exams</span>
              </h3>
              <button
                onClick={() => navigate('/exams')}
                className="text-xs text-[#3D8C82] font-medium hover:underline"
              >
                All Exams
              </button>
            </div>

            {upcomingExams.length === 0 ? (
              <p className="text-xs text-[#8E97A6] py-2">No upcoming exams scheduled.</p>
            ) : (
              <div className="space-y-2.5 pt-1">
                {upcomingExams.map((e) => (
                  <div key={e.id} className="p-3 rounded-xl bg-[#F7F8FC] border border-[#E7EAF0] space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-[#26313F] text-xs truncate">{e.name}</span>
                      <span
                        className={`text-[10px] font-medium px-2 py-0.5 rounded-full shrink-0 ${
                          e.days_remaining <= 5
                            ? 'bg-[#F4D5C2] text-[#69242E]'
                            : 'bg-[#D4C8F4]/40 text-[#3C2D69]'
                        }`}
                      >
                        {e.days_remaining === 0 ? 'Today' : `${e.days_remaining}d left`}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-[#6E7785]">
                      <span>{e.subject?.name || 'Subject'}</span>
                      <span>{e.exam_date}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Check-In Modal */}
      {checkInOcc && (
        <ClassCheckInModal
          occurrence={checkInOcc}
          onClose={() => setCheckInOcc(null)}
          onSuccess={() => {
            setCheckInOcc(null);
            fetchDashboardData();
          }}
        />
      )}

      {/* Before / After Class Briefing Modal */}
      {briefingModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#26313F]/30 backdrop-blur-sm">
          <div className="bg-white border border-[#E7EAF0] rounded-3xl max-w-lg w-full p-6 space-y-4 shadow-float animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <h3 className="text-base font-bold text-[#26313F] flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#72C9BE]" />
                <span>{briefingModal.type === 'before' ? 'Pre-Class Briefing' : 'After-Class Debrief'}</span>
              </h3>
              <button
                onClick={() => setBriefingModal(null)}
                className="p-1 rounded-lg text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-xs text-[#26313F] leading-relaxed max-h-[60vh] overflow-y-auto space-y-3">
              <p className="whitespace-pre-line">{briefingModal.data?.briefing || briefingModal.data?.summary || 'No briefing notes available.'}</p>
            </div>

            <div className="flex justify-end pt-2 border-t border-[#E7EAF0]">
              <button
                onClick={() => setBriefingModal(null)}
                className="px-4 py-2 bg-[#F2F5F8] hover:bg-[#E7EAF0] text-[#26313F] rounded-xl text-xs font-semibold"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
