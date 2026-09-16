import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  CheckSquare,
  Clock,
  RefreshCw,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Search,
  BookOpen,
  Check,
  X,
  Slash,
  ArrowUpRight,
  Sparkles,
  RotateCcw
} from 'lucide-react';
import { apiRequest } from '../api/client';
import ClassCheckInModal from '../components/ClassCheckInModal';

export default function AttendancePage() {
  const [attendance, setAttendance] = useState(null);
  const [endedClasses, setEndedClasses] = useState([]);
  const [upcomingToday, setUpcomingToday] = useState([]);
  const [todayClasses, setTodayClasses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [markingId, setMarkingId] = useState(null);
  const [selectedSubjectId, setSelectedSubjectId] = useState('all');
  const [expandedSubjects, setExpandedSubjects] = useState({});
  const [classFilter, setClassFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Topic Check-in modal
  const [checkInOcc, setCheckInOcc] = useState(null);

  const loadAllData = async () => {
    try {
      setLoading(true);
      const [sumData, classesData] = await Promise.all([
        apiRequest('/attendance/summary'),
        apiRequest('/attendance/classes').catch(() => ({
          ended_classes: [],
          upcoming_today: [],
          today_classes: []
        }))
      ]);
      setAttendance(sumData);
      setEndedClasses(classesData.ended_classes || []);
      setUpcomingToday(classesData.upcoming_today || []);
      setTodayClasses(classesData.today_classes || []);
    } catch (err) {
      console.error('Failed to load attendance data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllData();

    const handleFocus = () => loadAllData();
    window.addEventListener('focus', handleFocus);

    const interval = setInterval(() => {
      loadAllData();
    }, 30000);

    return () => {
      window.removeEventListener('focus', handleFocus);
      clearInterval(interval);
    };
  }, []);

  const markAttendance = async (occurrenceId, status) => {
    try {
      setMarkingId(occurrenceId);
      await apiRequest('/attendance/mark', {
        method: 'POST',
        body: JSON.stringify({ occurrence_id: occurrenceId, status })
      });
      const [sumData, classesData] = await Promise.all([
        apiRequest('/attendance/summary'),
        apiRequest('/attendance/classes').catch(() => ({
          ended_classes: [],
          upcoming_today: [],
          today_classes: []
        }))
      ]);
      setAttendance(sumData);
      setEndedClasses(classesData.ended_classes || []);
      setUpcomingToday(classesData.upcoming_today || []);
      setTodayClasses(classesData.today_classes || []);
    } catch (err) {
      alert(`Error updating attendance: ${err.message}`);
    } finally {
      setMarkingId(null);
    }
  };

  const toggleSubjectExpanded = (subjectId) => {
    setExpandedSubjects((prev) => ({
      ...prev,
      [subjectId]: !prev[subjectId]
    }));
  };

  const todayStrFormatted = new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });

  const subjects = attendance?.subjects_summary || [];

  const subjectsToShow = useMemo(() => {
    if (selectedSubjectId === 'all') return subjects;
    return subjects.filter((s) => s.subject_id === selectedSubjectId);
  }, [subjects, selectedSubjectId]);

  // Pending classes list (ended, not cancelled, not marked)
  const pendingClasses = useMemo(() => {
    return endedClasses.filter((c) => {
      const att = c.attendance?.status;
      const isCancelled = c.status === 'cancelled' || att === 'cancelled';
      return !isCancelled && (!att || att === 'not_marked');
    });
  }, [endedClasses]);

  if (loading && !attendance) {
    return (
      <div className="flex items-center justify-center min-h-[65vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-[#72C9BE] border-t-transparent animate-spin" />
          <p className="text-xs text-[#6E7785] font-medium">Syncing attendance with your timetable...</p>
        </div>
      </div>
    );
  }

  const overallPct = attendance?.overall_percentage;
  const targetPct = attendance?.target_percentage || 75;
  const isOnTrack = overallPct !== null && overallPct !== undefined && overallPct >= targetPct;

  return (
    <div className="space-y-8 pb-16">
      {/* -------------------------------------------------------------
          1. HEADER: CLEAN & SIMPLE
      ------------------------------------------------------------- */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#E7EAF0] pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-[#26313F] flex items-center gap-2.5">
              <span className="p-2 rounded-xl bg-[#CADFCB]/40 text-[#1A4B43]">
                <CheckSquare className="w-5 h-5 stroke-[2.2]" />
              </span>
              <span>Attendance</span>
            </h1>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-[#CFEDE7] text-[#1A4B43]">
              Timetable Synced
            </span>
          </div>
          <p className="text-xs text-[#6E7785] mt-1">
            Driven automatically by your schedule. No stressful alarms or visual pressure.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/timetable"
            className="px-3.5 py-2 rounded-xl bg-white border border-[#E7EAF0] text-[#26313F] hover:bg-[#F2F5F8] transition-all flex items-center gap-1.5 text-xs font-semibold shadow-soft"
          >
            <span>Timetable</span>
            <ArrowUpRight className="w-3.5 h-3.5 text-[#3D8C82]" />
          </Link>

          <button
            type="button"
            onClick={loadAllData}
            title="Refresh attendance"
            className="p-2 rounded-xl bg-white border border-[#E7EAF0] text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] transition-all shadow-soft cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* -------------------------------------------------------------
          2. OVERALL PROGRESS (CALM, CLEAN)
      ------------------------------------------------------------- */}
      <div className="bg-white rounded-2xl border border-[#E7EAF0] p-6 shadow-card space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <span className="text-xs font-medium text-[#6E7785] uppercase tracking-wider">Overall Attendance</span>
            <div className="flex items-baseline gap-3 mt-1">
              <span className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#26313F]">
                {attendance?.total_conducted > 0 && overallPct !== null && overallPct !== undefined
                  ? `${overallPct}%`
                  : '—'}
              </span>
              <span
                className={`text-xs font-medium px-2.5 py-0.5 rounded-full ${
                  isOnTrack
                    ? 'bg-[#CFEDE7] text-[#1A4B43]'
                    : 'bg-[#F3DFAB]/60 text-[#6B4E17]'
                }`}
              >
                Target {targetPct}%
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs text-[#6E7785] flex-wrap">
            <div>
              <span className="block text-[10px] text-[#8E97A6]">Conducted</span>
              <span className="font-semibold text-[#26313F] text-sm">{attendance?.total_conducted || 0}</span>
            </div>
            <div className="w-px h-6 bg-[#E7EAF0]" />
            <div>
              <span className="block text-[10px] text-[#8E97A6]">Attended</span>
              <span className="font-semibold text-[#1A4B43] text-sm">{attendance?.total_attended || 0}</span>
            </div>
            <div className="w-px h-6 bg-[#E7EAF0]" />
            <div>
              <span className="block text-[10px] text-[#8E97A6]">Missed</span>
              <span className="font-semibold text-[#69242E] text-sm">{attendance?.total_missed || 0}</span>
            </div>
            <div className="w-px h-6 bg-[#E7EAF0]" />
            <div>
              <span className="block text-[10px] text-[#8E97A6]">Cancelled</span>
              <span className="font-semibold text-[#6E7785] text-sm">{attendance?.total_cancelled || 0}</span>
            </div>
          </div>
        </div>

        {/* Soft Linear Progress Bar */}
        <div className="w-full h-2 rounded-full bg-[#F2F5F8] overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              isOnTrack ? 'bg-[#72C9BE]' : 'bg-[#F3DFAB]'
            }`}
            style={{ width: `${Math.min(100, overallPct || 0)}%` }}
          />
        </div>
      </div>

      {/* -------------------------------------------------------------
          3. PENDING CHECK-INS (CALM VERTICAL LIST)
      ------------------------------------------------------------- */}
      {pendingClasses.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-[#26313F] uppercase tracking-wider">
              Pending Check-ins ({pendingClasses.length})
            </h2>
            <span className="text-xs text-[#6E7785]">Concluded classes waiting for attendance</span>
          </div>

          <div className="space-y-2">
            {pendingClasses.map((occ) => {
              const formattedDate = new Date(occ.date + 'T00:00:00').toLocaleDateString(undefined, {
                weekday: 'short',
                month: 'short',
                day: 'numeric'
              });

              return (
                <div
                  key={occ.id}
                  className="p-4 rounded-2xl bg-white border border-[#E7EAF0] shadow-soft flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition-all hover:border-[#72C9BE]/50"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-bold text-[#26313F]">{occ.subject?.name || 'Class'}</h4>
                      {occ.subject?.code && (
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[#F2F5F8] text-[#6E7785]">
                          {occ.subject.code}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[#6E7785] flex items-center gap-1.5 font-mono">
                      <Clock className="w-3.5 h-3.5 text-[#72C9BE]" />
                      <span>{formattedDate} • {occ.start_time?.slice(0, 5)} – {occ.end_time?.slice(0, 5)}</span>
                      {occ.room && <span>• Room {occ.room}</span>}
                    </p>
                  </div>

                  {/* Actions: Present / Absent / + Topic */}
                  <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
                    <button
                      type="button"
                      disabled={markingId === occ.id}
                      onClick={() => markAttendance(occ.id, 'present')}
                      className="px-3.5 py-1.5 rounded-xl bg-[#CFEDE7] hover:bg-[#b5e7dc] text-[#1A4B43] text-xs font-semibold transition-all cursor-pointer shadow-soft"
                    >
                      Present
                    </button>
                    <button
                      type="button"
                      disabled={markingId === occ.id}
                      onClick={() => markAttendance(occ.id, 'absent')}
                      className="px-3.5 py-1.5 rounded-xl bg-[#EABFC5]/40 hover:bg-[#EABFC5]/70 text-[#69242E] text-xs font-semibold transition-all cursor-pointer shadow-soft"
                    >
                      Absent
                    </button>
                    <button
                      type="button"
                      onClick={() => setCheckInOcc(occ)}
                      className="px-3 py-1.5 rounded-xl bg-[#F2F5F8] hover:bg-[#E7EAF0] text-[#26313F] text-xs font-medium border border-[#E7EAF0] transition-all cursor-pointer"
                    >
                      + Add topic
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* -------------------------------------------------------------
          4. TODAY'S CLASSES
      ------------------------------------------------------------- */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[#26313F] uppercase tracking-wider">
            Today's Classes ({todayClasses.length})
          </h2>
          <span className="text-xs text-[#6E7785]">{todayStrFormatted}</span>
        </div>

        {todayClasses.length === 0 ? (
          <div className="p-6 rounded-2xl bg-white border border-[#E7EAF0] text-center text-xs text-[#6E7785] shadow-soft">
            No classes scheduled for today.
          </div>
        ) : (
          <div className="space-y-2">
            {todayClasses.map((cls) => {
              const currentStatus =
                cls.attendance?.status || (cls.status === 'cancelled' ? 'cancelled' : 'not_marked');
              const isCancelled = cls.status === 'cancelled' || currentStatus === 'cancelled';
              const isPending = cls.has_ended && currentStatus === 'not_marked' && !isCancelled;

              return (
                <div
                  key={cls.id}
                  className="p-4 rounded-2xl bg-white border border-[#E7EAF0] shadow-soft flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span
                        className="w-2.5 h-2.5 rounded-full shrink-0"
                        style={{ backgroundColor: cls.subject?.color || '#72C9BE' }}
                      />
                      <h4 className="text-sm font-bold text-[#26313F]">{cls.subject?.name}</h4>
                      {isCancelled ? (
                        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#E7EAF0] text-[#4B5563]">
                          Cancelled
                        </span>
                      ) : cls.is_in_progress ? (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#CFEDE7] text-[#1A4B43]">
                          In Progress
                        </span>
                      ) : isPending ? (
                        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#F3DFAB]/60 text-[#6B4E17]">
                          Waiting Check-in
                        </span>
                      ) : currentStatus === 'present' ? (
                        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#CFEDE7] text-[#1A4B43]">
                          Present
                        </span>
                      ) : currentStatus === 'absent' ? (
                        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#EABFC5]/40 text-[#69242E]">
                          Absent
                        </span>
                      ) : (
                        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#B7D4F4]/30 text-[#1E3A8A]">
                          Upcoming
                        </span>
                      )}
                    </div>

                    <p className="text-xs text-[#6E7785] flex items-center gap-1.5 font-mono">
                      <Clock className="w-3.5 h-3.5 text-[#72C9BE]" />
                      <span>{cls.start_time?.slice(0, 5)} – {cls.end_time?.slice(0, 5)}</span>
                      {cls.room && <span>• Room {cls.room}</span>}
                    </p>

                    {/* Topics Section for ended class */}
                    {cls.has_ended && !isCancelled && (
                      <div className="mt-1">
                        {cls.topics && cls.topics.length > 0 ? (
                          <div className="flex flex-wrap items-center gap-1.5">
                            {cls.topics.map((t) => (
                              <button
                                key={t.id}
                                type="button"
                                onClick={() => setCheckInOcc(cls)}
                                title="Click to edit topic"
                                className="text-[10px] px-2 py-0.5 rounded-md bg-[#CFEDE7]/50 text-[#1A4B43] border border-[#72C9BE]/30 font-medium cursor-pointer hover:bg-[#CFEDE7] transition-colors"
                              >
                                {t.title}
                              </button>
                            ))}
                            <button
                              type="button"
                              onClick={() => setCheckInOcc(cls)}
                              className="text-[10px] text-[#3D8C82] hover:underline font-semibold cursor-pointer"
                            >
                              Edit Topic
                            </button>
                          </div>
                        ) : (currentStatus === 'present' || currentStatus === 'absent') ? (
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] text-[#8E97A6] font-medium bg-[#F2F5F8] border border-dashed border-[#CBD5E1] px-2 py-0.5 rounded-full">
                              Topic not added
                            </span>
                            <button
                              type="button"
                              onClick={() => setCheckInOcc(cls)}
                              className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#1A4B43] hover:underline cursor-pointer"
                            >
                              <BookOpen className="w-3 h-3 text-[#72C9BE]" />
                              <span>Add Topic</span>
                            </button>
                          </div>
                        ) : null}
                      </div>
                    )}
                  </div>

                  {cls.has_ended && (
                    <div className="flex items-center gap-1.5 self-start sm:self-auto shrink-0">
                      {isCancelled ? (
                        <button
                          type="button"
                          disabled={markingId === cls.id}
                          onClick={() => markAttendance(cls.id, 'not_marked')}
                          className="px-3 py-1 rounded-xl text-xs font-semibold bg-[#F2F5F8] text-[#26313F] hover:bg-[#E7EAF0] transition-all cursor-pointer shadow-soft flex items-center gap-1"
                          title="Undo cancellation and restore class"
                        >
                          <RotateCcw className="w-3 h-3 text-[#6E7785]" />
                          <span>Undo Cancel</span>
                        </button>
                      ) : (
                        <>
                          <button
                            type="button"
                            disabled={markingId === cls.id}
                            onClick={() => markAttendance(cls.id, 'present')}
                            className={`px-3 py-1 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                              currentStatus === 'present'
                                ? 'bg-[#CFEDE7] text-[#1A4B43] shadow-sm'
                                : 'bg-[#F2F5F8] text-[#6E7785] hover:text-[#26313F]'
                            }`}
                          >
                            Present
                          </button>
                          <button
                            type="button"
                            disabled={markingId === cls.id}
                            onClick={() => markAttendance(cls.id, 'absent')}
                            className={`px-3 py-1 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                              currentStatus === 'absent'
                                ? 'bg-[#EABFC5]/60 text-[#69242E] shadow-sm'
                                : 'bg-[#F2F5F8] text-[#6E7785] hover:text-[#26313F]'
                            }`}
                          >
                            Absent
                          </button>
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* -------------------------------------------------------------
          5. SUBJECTS: COMPACT LIST VIEW
      ------------------------------------------------------------- */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-[#26313F] uppercase tracking-wider">
              Subjects ({subjects.length})
            </h2>
            <p className="text-xs text-[#6E7785]">Attendance breakdown by individual subject</p>
          </div>

          {/* Quick Filter tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
            <button
              type="button"
              onClick={() => setClassFilter('all')}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                classFilter === 'all'
                  ? 'bg-[#CFEDE7] text-[#1A4B43] font-semibold'
                  : 'text-[#6E7785] hover:text-[#26313F]'
              }`}
            >
              All
            </button>
            <button
              type="button"
              onClick={() => setClassFilter('present')}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                classFilter === 'present'
                  ? 'bg-[#CFEDE7] text-[#1A4B43] font-semibold'
                  : 'text-[#6E7785] hover:text-[#26313F]'
              }`}
            >
              Present
            </button>
            <button
              type="button"
              onClick={() => setClassFilter('absent')}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                classFilter === 'absent'
                  ? 'bg-[#EABFC5]/50 text-[#69242E] font-semibold'
                  : 'text-[#6E7785] hover:text-[#26313F]'
              }`}
            >
              Absent
            </button>
          </div>
        </div>

        {subjectsToShow.length === 0 ? (
          <div className="p-8 rounded-2xl bg-white border border-[#E7EAF0] text-center text-xs text-[#6E7785]">
            No subjects found in timetable.
          </div>
        ) : (
          <div className="space-y-3">
            {subjectsToShow.map((s) => {
              const hasConducted = s.classes_conducted > 0;
              const isExpanded = expandedSubjects[s.subject_id];

              return (
                <div
                  key={s.subject_id}
                  className="bg-white rounded-2xl border border-[#E7EAF0] p-5 shadow-card space-y-4"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-3 h-8 rounded-full shrink-0"
                        style={{ backgroundColor: s.subject_color || '#72C9BE' }}
                      />
                      <div>
                        <h3 className="text-base font-bold text-[#26313F]">{s.subject_name}</h3>
                        <p className="text-xs text-[#6E7785]">
                          {s.classes_attended} of {s.classes_conducted} attended
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <span className="text-2xl font-extrabold text-[#26313F] block">
                          {hasConducted && s.current_percentage !== null ? `${s.current_percentage}%` : '—'}
                        </span>
                        <span className="text-[11px] text-[#6E7785]">
                          target {s.target_attendance}%
                        </span>
                      </div>

                      <button
                        type="button"
                        onClick={() => toggleSubjectExpanded(s.subject_id)}
                        className="p-1.5 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] transition-colors"
                        title={isExpanded ? 'Collapse classes' : 'Expand classes'}
                      >
                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  {/* Expanded class details list */}
                  {isExpanded && (
                    <div className="pt-3 border-t border-[#E7EAF0] space-y-2 animate-in fade-in">
                      <span className="text-xs font-semibold text-[#26313F] block">
                        Class Attendance Log ({s.classes?.length || 0})
                      </span>

                      <div className="space-y-1.5 max-h-60 overflow-y-auto pr-1">
                        {(s.classes || []).map((occ) => {
                          const status =
                            occ.attendance?.status || (occ.status === 'cancelled' ? 'cancelled' : 'not_marked');
                          const dateStr = new Date(occ.date + 'T00:00:00').toLocaleDateString(undefined, {
                            month: 'short',
                            day: 'numeric',
                            weekday: 'short'
                          });

                          return (
                            <div
                              key={occ.id}
                              className="p-2.5 rounded-xl bg-[#F7F8FC] border border-[#E7EAF0] flex items-center justify-between text-xs"
                            >
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-[#26313F] font-medium">{dateStr}</span>
                                <span className="text-[#6E7785] font-mono text-[11px]">
                                  {occ.start_time.slice(0, 5)}–{occ.end_time.slice(0, 5)}
                                </span>
                                {occ.topics && occ.topics.length > 0 ? (
                                  <div className="flex flex-wrap items-center gap-1">
                                    {occ.topics.map((t) => (
                                      <button
                                        key={t.id}
                                        type="button"
                                        onClick={() => setCheckInOcc(occ)}
                                        className="text-[10px] px-1.5 py-0.2 rounded bg-[#CFEDE7]/50 text-[#1A4B43] border border-[#72C9BE]/30 font-medium hover:bg-[#CFEDE7] cursor-pointer"
                                        title="Click to edit topic"
                                      >
                                        {t.title}
                                      </button>
                                    ))}
                                  </div>
                                ) : (status === 'present' || status === 'absent') ? (
                                  <button
                                    type="button"
                                    onClick={() => setCheckInOcc(occ)}
                                    className="text-[10px] text-[#8E97A6] hover:text-[#1A4B43] italic border border-dashed border-[#CBD5E1] px-1.5 py-0.2 rounded hover:underline cursor-pointer"
                                  >
                                    + Add Topic
                                  </button>
                                ) : null}
                              </div>

                              <div className="flex items-center gap-1.5">
                                <button
                                  type="button"
                                  onClick={() => markAttendance(occ.id, 'present')}
                                  className={`px-2 py-0.5 rounded-lg text-[11px] font-medium transition-all ${
                                    status === 'present'
                                      ? 'bg-[#CFEDE7] text-[#1A4B43] font-semibold'
                                      : 'text-[#6E7785] hover:text-[#26313F]'
                                  }`}
                                >
                                  Present
                                </button>
                                <button
                                  type="button"
                                  onClick={() => markAttendance(occ.id, 'absent')}
                                  className={`px-2 py-0.5 rounded-lg text-[11px] font-medium transition-all ${
                                    status === 'absent'
                                      ? 'bg-[#EABFC5]/50 text-[#69242E] font-semibold'
                                      : 'text-[#6E7785] hover:text-[#26313F]'
                                  }`}
                                >
                                  Absent
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Check In Modal */}
      <ClassCheckInModal
        isOpen={Boolean(checkInOcc)}
        occurrence={checkInOcc}
        onClose={() => setCheckInOcc(null)}
        onCheckInComplete={loadAllData}
      />
    </div>
  );
}
