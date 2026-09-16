import React, { useState, useEffect } from 'react';
import {
  HeartPulse,
  Plus,
  CheckCircle2,
  Circle,
  Sliders,
  X,
  Clock,
  Calendar,
  Moon,
  Droplet,
  Coffee,
  Sun,
  ShieldCheck,
  Bell,
  BellOff,
  History,
  PauseCircle,
  PlayCircle,
  Trash2,
  Edit3,
  Check,
  Sparkles,
  Info,
  AlertCircle,
  Minus,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { apiRequest } from '../api/client';

const CATEGORIES = [
  { id: 'routine', label: 'General Routine', icon: HeartPulse, color: 'text-teal-700 bg-teal-50 border-teal-200/60' },
  { id: 'hydration', label: 'Hydration', icon: Droplet, color: 'text-cyan-700 bg-cyan-50 border-cyan-200/60' },
  { id: 'sleep', label: 'Sleep & Rest', icon: Moon, color: 'text-indigo-700 bg-indigo-50 border-indigo-200/60' },
  { id: 'nutrition', label: 'Nutrition', icon: Coffee, color: 'text-amber-700 bg-amber-50 border-amber-200/60' },
  { id: 'break', label: 'Mindful Break', icon: Sun, color: 'text-emerald-700 bg-emerald-50 border-emerald-200/60' },
];

const DAYS_MAP = [
  { id: '0', label: 'M', full: 'Mon' },
  { id: '1', label: 'T', full: 'Tue' },
  { id: '2', label: 'W', full: 'Wed' },
  { id: '3', label: 'T', full: 'Thu' },
  { id: '4', label: 'F', full: 'Fri' },
  { id: '5', label: 'S', full: 'Sat' },
  { id: '6', label: 'S', full: 'Sun' },
];

const WELLBEING_OPTIONS = [
  { id: 'great', emoji: '😄', label: 'Great', bg: 'bg-[#CFEDE7]/40', border: 'border-[#72C9BE]/40', text: 'text-[#1A4B43]' },
  { id: 'good', emoji: '🙂', label: 'Good', bg: 'bg-[#B7D4F4]/30', border: 'border-[#B7D4F4]/60', text: 'text-[#1E3A8A]' },
  { id: 'okay', emoji: '😐', label: 'Okay', bg: 'bg-[#F2F5F8]', border: 'border-[#E7EAF0]', text: 'text-[#26313F]' },
  { id: 'tired', emoji: '😴', label: 'Tired', bg: 'bg-[#F3DFAB]/30', border: 'border-[#F3DFAB]/60', text: 'text-[#6B4E17]' },
  { id: 'stressful', emoji: '😣', label: 'Stressful', bg: 'bg-[#EABFC5]/30', border: 'border-[#EABFC5]/60', text: 'text-[#69242E]' },
];

// Helper: smart, non-intrusive progress chips for partly completed routines
const getQuickProgressChips = (routineName = '') => {
  const lower = (routineName || '').toLowerCase();
  if (lower.includes('sleep') || lower.includes('rest')) {
    return ['5–6h', '6–7h', '7h+'];
  }
  if (lower.includes('water') || lower.includes('hydrat') || lower.includes('drink') || lower.includes('fluid')) {
    return ['< Half', '~ Half', 'Almost completed'];
  }
  if (
    lower.includes('walk') ||
    lower.includes('step') ||
    lower.includes('exercise') ||
    lower.includes('workout') ||
    lower.includes('gym') ||
    lower.includes('run')
  ) {
    return ['15 min', '30 min', '~ Half'];
  }
  if (
    lower.includes('read') ||
    lower.includes('meditat') ||
    lower.includes('mindful') ||
    lower.includes('study')
  ) {
    return ['10 min', '20 min', '~ Half'];
  }
  return ['Started', '~ Half', 'Almost completed'];
};

export default function HabitsPage() {
  // Main page data
  const [todayRoutines, setTodayRoutines] = useState([]);
  const [weeklySummary, setWeeklySummary] = useState({
    days: [],
    total_completed: 0,
    total_partial: 0,
    total_skipped: 0,
    total_missed: 0,
    total_routines: 0,
    overall_percentage: 0
  });
  const [loading, setLoading] = useState(true);
  const [snoozeMessages, setSnoozeMessages] = useState({});
  const [expandedRoutineId, setExpandedRoutineId] = useState(null);
  const [partialNotesDraft, setPartialNotesDraft] = useState({});

  // Add / Edit Routine Modal
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingRoutineId, setEditingRoutineId] = useState(null);
  const [routineForm, setRoutineForm] = useState({
    name: '',
    category: 'routine',
    selected_days: '0,1,2,3,4,5,6',
    reminder_preset: 'none', // none, morning, afternoon, evening, custom
    reminder_time: '',
    note: '',
    is_paused: false
  });

  // Manage Modal & Tabs
  const [manageModalOpen, setManageModalOpen] = useState(false);
  const [manageTab, setManageTab] = useState('my-routines'); // my-routines, settings, history, paused
  const [allRoutines, setAllRoutines] = useState([]);
  const [historyLogs, setHistoryLogs] = useState([]);
  const [settings, setSettings] = useState({
    reminders_enabled: true,
    pause_reminders_today: false,
    quiet_hours_enabled: false,
    quiet_hours_start: '22:00',
    quiet_hours_end: '07:00',
    morning_time: '08:00',
    afternoon_time: '14:00',
    evening_time: '20:00',
    avoid_during_classes: true,
    combine_nearby: true
  });
  const [settingsSavedMessage, setSettingsSavedMessage] = useState(false);

  // Daily Wellbeing Check-in State
  const [wellbeingCheckIn, setWellbeingCheckIn] = useState(null);
  const [wbSubmitting, setWbSubmitting] = useState(false);
  const [wbEditing, setWbEditing] = useState(false);
  const [simulateAfter4PM, setSimulateAfter4PM] = useState(false);

  // Load Main Dashboard Data
  const loadDashboardData = async () => {
    try {
      setLoading(true);
      const [todayData, summaryData, wbData] = await Promise.all([
        apiRequest('/habits/'),
        apiRequest('/habits/weekly-summary'),
        apiRequest('/habits/wellbeing/today').catch(() => ({ status: 'pending', mood: null }))
      ]);
      setTodayRoutines(todayData);
      setWeeklySummary(summaryData);
      setWellbeingCheckIn(wbData);
    } catch (err) {
      console.error('Error loading routine data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  // Load Manage Area Data when Manage Modal opens or tab changes
  const loadManageData = async () => {
    try {
      if (manageTab === 'my-routines' || manageTab === 'paused') {
        const data = await apiRequest('/habits/all');
        setAllRoutines(data);
      } else if (manageTab === 'settings') {
        const s = await apiRequest('/habits/settings');
        setSettings(s);
      } else if (manageTab === 'history') {
        const h = await apiRequest('/habits/history?days=14');
        setHistoryLogs(h);
      }
    } catch (err) {
      console.error('Error loading manage data:', err);
    }
  };

  useEffect(() => {
    if (manageModalOpen) {
      loadManageData();
    }
  }, [manageModalOpen, manageTab]);

  // Submit Daily Wellbeing Check-in
  const handleWellbeingSubmit = async (status, mood = null) => {
    try {
      setWbSubmitting(true);
      const res = await apiRequest('/habits/wellbeing', {
        method: 'POST',
        body: JSON.stringify({ status, mood })
      });
      setWellbeingCheckIn(res);
      setWbEditing(false);
    } catch (err) {
      console.error('Error saving wellbeing checkin:', err);
    } finally {
      setWbSubmitting(false);
    }
  };

  // Set routine status: completed, partial, skipped, missed
  const handleSetRoutineStatus = async (routineId, newStatus, customNotes = null) => {
    const todayStr = new Date().toISOString().split('T')[0];
    const routine = todayRoutines.find((r) => r.id === routineId);
    const finalNotes = customNotes !== null ? customNotes : (routine?.today_notes || '');

    // Optimistic UI update
    setTodayRoutines((prev) =>
      prev.map((r) => {
        if (r.id !== routineId) return r;
        return {
          ...r,
          today_completed: newStatus === 'completed',
          today_status: newStatus,
          today_notes: finalNotes,
        };
      })
    );

    if (customNotes !== null) {
      setPartialNotesDraft((prev) => ({ ...prev, [routineId]: customNotes }));
    }

    try {
      await apiRequest('/habits/log', {
        method: 'POST',
        body: JSON.stringify({
          habit_id: routineId,
          date: todayStr,
          status: newStatus,
          notes: finalNotes
        })
      });
      // Refresh weekly summary in background
      const summaryData = await apiRequest('/habits/weekly-summary');
      setWeeklySummary(summaryData);
    } catch (err) {
      console.error('Failed to update routine status:', err);
      // Revert if error
      loadDashboardData();
    }
  };

  // Toggle Done convenience handler
  const handleToggleDone = (routine) => {
    const isCurrentlyDone = routine.today_status === 'completed' || routine.today_completed;
    handleSetRoutineStatus(routine.id, isCurrentlyDone ? 'missed' : 'completed');
  };

  // Snooze / Later action
  const handleSnooze = (routineId) => {
    setSnoozeMessages((prev) => ({
      ...prev,
      [routineId]: 'Snoozed for 30 min'
    }));
    setTimeout(() => {
      setSnoozeMessages((prev) => {
        const copy = { ...prev };
        delete copy[routineId];
        return copy;
      });
    }, 4000);
  };

  // Open Add Routine Modal
  const openAddModal = () => {
    setEditingRoutineId(null);
    setRoutineForm({
      name: '',
      category: 'routine',
      selected_days: '0,1,2,3,4,5,6',
      reminder_preset: 'none',
      reminder_time: '',
      note: '',
      is_paused: false
    });
    setEditModalOpen(true);
  };

  // Open Edit Routine Modal
  const openEditModal = (routine) => {
    setEditingRoutineId(routine.id);
    let preset = 'none';
    let customTime = '';
    if (['morning', 'afternoon', 'evening'].includes(routine.reminder_time)) {
      preset = routine.reminder_time;
    } else if (routine.reminder_time) {
      preset = 'custom';
      customTime = routine.reminder_time;
    }

    setRoutineForm({
      name: routine.name,
      category: routine.category || 'routine',
      selected_days: routine.selected_days || '0,1,2,3,4,5,6',
      reminder_preset: preset,
      reminder_time: customTime,
      note: routine.note || '',
      is_paused: Boolean(routine.is_paused)
    });
    setEditModalOpen(true);
  };

  // Save Routine (Create or Update)
  const handleSaveRoutine = async (e) => {
    e.preventDefault();
    if (!routineForm.name.trim()) return;

    let finalReminderTime = '';
    if (routineForm.reminder_preset === 'custom') {
      finalReminderTime = routineForm.reminder_time || '08:00';
    } else if (routineForm.reminder_preset !== 'none') {
      finalReminderTime = routineForm.reminder_preset;
    }

    const payload = {
      name: routineForm.name.trim(),
      category: routineForm.category,
      selected_days: routineForm.selected_days,
      reminder_time: finalReminderTime,
      note: routineForm.note.trim(),
      is_paused: routineForm.is_paused
    };

    try {
      if (editingRoutineId) {
        await apiRequest(`/habits/${editingRoutineId}`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        });
      } else {
        await apiRequest('/habits/', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
      }
      setEditModalOpen(false);
      loadDashboardData();
      if (manageModalOpen) loadManageData();
    } catch (err) {
      alert(`Error saving routine: ${err.message}`);
    }
  };

  // Toggle Pause for Routine
  const handleTogglePause = async (routineId) => {
    try {
      await apiRequest(`/habits/${routineId}/toggle-pause`, {
        method: 'POST'
      });
      loadDashboardData();
      if (manageModalOpen) loadManageData();
    } catch (err) {
      alert(`Error toggling pause: ${err.message}`);
    }
  };

  // Delete Routine
  const handleDeleteRoutine = async (routineId, routineName) => {
    if (!window.confirm(`Delete "${routineName}"? All associated logs will be removed.`)) return;
    try {
      await apiRequest(`/habits/${routineId}`, {
        method: 'DELETE'
      });
      loadDashboardData();
      if (manageModalOpen) loadManageData();
    } catch (err) {
      alert(`Error deleting routine: ${err.message}`);
    }
  };

  // Save Routine Settings
  const handleSaveSettings = async (e) => {
    e.preventDefault();
    try {
      await apiRequest('/habits/settings', {
        method: 'PUT',
        body: JSON.stringify(settings)
      });
      setSettingsSavedMessage(true);
      setTimeout(() => setSettingsSavedMessage(false), 3500);
    } catch (err) {
      alert(`Error updating settings: ${err.message}`);
    }
  };

  // Helpers for Selected Days
  const toggleDay = (dayId) => {
    const currentDays = routineForm.selected_days
      ? routineForm.selected_days.split(',').map((s) => s.trim())
      : [];
    let updated;
    if (currentDays.includes(dayId)) {
      if (currentDays.length === 1) return; // keep at least 1
      updated = currentDays.filter((d) => d !== dayId);
    } else {
      updated = [...currentDays, dayId].sort();
    }
    setRoutineForm({ ...routineForm, selected_days: updated.join(',') });
  };

  const completedCount = todayRoutines.filter(
    (r) => r.today_status === 'completed' || (r.today_completed && !r.today_status)
  ).length;
  const partialCount = todayRoutines.filter((r) => r.today_status === 'partial').length;
  const skippedCount = todayRoutines.filter((r) => r.today_status === 'skipped').length;
  const unrecordedCount = todayRoutines.filter(
    (r) => !r.today_status || r.today_status === 'missed'
  ).length;
  const totalToday = todayRoutines.length;
  const activeTotal = Math.max(0, totalToday - skippedCount);
  const progressPercent =
    activeTotal > 0
      ? Math.min(100, Math.round(((completedCount + partialCount * 0.5) / activeTotal) * 100))
      : totalToday > 0 && skippedCount === totalToday
      ? 100
      : 0;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 space-y-6 pb-24">
      {/* 1. Header with Routine & Wellbeing, + Add Routine, and Manage */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#E7EAF0] pb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-800 flex items-center gap-2.5">
            <span className="p-2 rounded-xl bg-[#CFEDE7] text-[#1A4B43] shadow-xs">
              <HeartPulse className="w-5 h-5" />
            </span>
            <span>Routine & Wellbeing</span>
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Calm, non-punitive daily routine tracking for medical students. No broken streaks, no guilt.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={openAddModal}
            className="flex items-center gap-1.5 px-4 py-2 bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 font-semibold rounded-xl text-sm transition-all shadow-sm active:scale-95"
          >
            <Plus className="w-4 h-4 stroke-[2.5]" />
            <span>Add Routine</span>
          </button>

          <button
            onClick={() => setManageModalOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-white hover:bg-slate-50 text-slate-700 border border-[#E7EAF0] font-medium rounded-xl text-sm transition-all shadow-xs active:scale-95"
          >
            <Sliders className="w-4 h-4 text-[#72C9BE]" />
            <span>Manage</span>
          </button>
        </div>
      </div>

      {/* Daily Wellbeing Check-in Card (After 4:00 PM local time) */}
      {(() => {
        const localHour = new Date().getHours();
        const isTimeForCheckIn = localHour >= 16 || simulateAfter4PM;
        const isAnswered = wellbeingCheckIn?.status === 'answered' && !wbEditing;
        const isSkipped = wellbeingCheckIn?.status === 'skipped' && !wbEditing;
        const currentMoodObj = WELLBEING_OPTIONS.find((m) => m.id === wellbeingCheckIn?.mood);

        // If before 4 PM and not simulated, show a very subtle indicator with demo test toggle
        if (!isTimeForCheckIn && !isAnswered && !isSkipped) {
          return (
            <div className="flex items-center justify-between px-4 py-3 bg-white/70 border border-[#E7EAF0] rounded-2xl text-xs text-slate-500 shadow-soft">
              <div className="flex items-center gap-2">
                <Moon className="w-4 h-4 text-[#72C9BE]" />
                <span>Daily wellbeing check-in unlocks after 4:00 PM local time.</span>
              </div>
              <button
                type="button"
                onClick={() => setSimulateAfter4PM(true)}
                className="text-[11px] font-semibold text-[#1A4B43] bg-[#CFEDE7] hover:bg-[#bce5dd] px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
              >
                Simulate after 4:00 PM (Test)
              </button>
            </div>
          );
        }

        // If answered today
        if (isAnswered && currentMoodObj) {
          return (
            <div className={`p-4 sm:p-5 rounded-2xl border ${currentMoodObj.border} ${currentMoodObj.bg} shadow-soft flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition-all`}>
              <div className="flex items-center gap-3">
                <span className="text-2xl select-none">{currentMoodObj.emoji}</span>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-sm font-bold ${currentMoodObj.text}`}>
                      Today felt {currentMoodObj.label}
                    </span>
                    <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-white/80 text-slate-600 border border-slate-200/60">
                      Check-in recorded
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 mt-0.5">
                    Study Planner workload automatically adapted for tonight.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 self-end sm:self-auto">
                <button
                  type="button"
                  onClick={() => setWbEditing(true)}
                  className="text-xs font-semibold text-slate-600 hover:text-slate-800 bg-white/80 hover:bg-white px-3 py-1.5 rounded-xl border border-slate-200/80 transition-all cursor-pointer shadow-xs"
                >
                  Change
                </button>
              </div>
            </div>
          );
        }

        // If skipped today
        if (isSkipped) {
          return (
            <div className="p-4 rounded-2xl bg-white border border-[#E7EAF0] shadow-soft flex items-center justify-between gap-3 text-xs text-slate-500">
              <div className="flex items-center gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-slate-400" />
                <span>Check-in skipped for today. Your Study Planner will use standard balanced pacing.</span>
              </div>
              <button
                type="button"
                onClick={() => setWbEditing(true)}
                className="text-xs font-semibold text-[#1A4B43] bg-[#CFEDE7]/60 hover:bg-[#CFEDE7] px-3 py-1 rounded-xl transition-colors cursor-pointer"
              >
                Check In
              </button>
            </div>
          );
        }

        // Pending check-in after 4:00 PM (or in edit mode)
        return (
          <div className="bg-white border border-[#E7EAF0] rounded-2xl p-5 sm:p-6 shadow-card transition-all">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                  <span>How did today feel?</span>
                  {simulateAfter4PM && (
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-[#F3DFAB]/50 text-[#6B4E17]">
                      Demo (Simulated 4:00 PM)
                    </span>
                  )}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Optional daily check-in to pace tonight's study workload. Never shared or graded.
                </p>
              </div>

              <button
                type="button"
                disabled={wbSubmitting}
                onClick={() => handleWellbeingSubmit('skipped')}
                className="text-xs text-slate-500 hover:text-slate-700 underline font-medium self-start sm:self-auto cursor-pointer"
              >
                Skip for today
              </button>
            </div>

            {/* 5 Pastel Emoji Options */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
              {WELLBEING_OPTIONS.map((opt) => {
                const isSelected = wellbeingCheckIn?.mood === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    disabled={wbSubmitting}
                    onClick={() => handleWellbeingSubmit('answered', opt.id)}
                    className={`flex flex-col items-center justify-center p-3 sm:py-3.5 rounded-xl border transition-all cursor-pointer group ${
                      isSelected
                        ? `${opt.bg} ${opt.border} ring-2 ring-[#72C9BE]/30`
                        : 'bg-[#F7F8FC] border-[#E7EAF0] hover:bg-white hover:border-[#72C9BE]/50 hover:shadow-xs'
                    }`}
                  >
                    <span className="text-2xl mb-1 group-hover:scale-110 transition-transform">
                      {opt.emoji}
                    </span>
                    <span className="text-xs font-semibold text-slate-700">
                      {opt.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        );
      })()}

      {/* 2. Daily Summary: "3 completed • 1 partial • 1 skipped" */}
      <div className="bg-white border border-[#E7EAF0] rounded-2xl p-5 sm:p-6 shadow-card space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xl sm:text-2xl font-bold text-slate-800 tracking-tight">
                {completedCount} completed • {partialCount} partial • {skippedCount} skipped
              </span>
              {unrecordedCount > 0 && (
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600">
                  {unrecordedCount} remaining
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-1">
              {activeTotal > 0
                ? `${completedCount} of ${activeTotal} active routines completed today`
                : totalToday > 0
                ? 'All routines skipped for today'
                : 'No routines scheduled for today'}
            </p>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            {activeTotal > 0 && completedCount === activeTotal && (
              <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-[#CFEDE7] text-[#1A4B43]">
                <Sparkles className="w-3.5 h-3.5" /> All completed
              </span>
            )}
            <span className="text-base sm:text-lg font-bold text-[#1A4B43]">{progressPercent}%</span>
          </div>
        </div>

        {/* Multi-segment soft progress bar: Mint (completed), Soft Blue (partial), Slate (skipped) */}
        <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden flex">
          {totalToday > 0 ? (
            <>
              <div
                className="bg-[#72C9BE] h-full transition-all duration-500 ease-out"
                style={{ width: `${(completedCount / totalToday) * 100}%` }}
                title={`${completedCount} completed`}
              />
              <div
                className="bg-[#93C5FD] h-full transition-all duration-500 ease-out"
                style={{ width: `${(partialCount / totalToday) * 100}%` }}
                title={`${partialCount} partly`}
              />
              <div
                className="bg-slate-300 h-full transition-all duration-500 ease-out"
                style={{ width: `${(skippedCount / totalToday) * 100}%` }}
                title={`${skippedCount} skipped`}
              />
            </>
          ) : (
            <div className="w-full h-full bg-slate-100" />
          )}
        </div>

        {/* Status badges row */}
        <div className="flex items-center gap-2 flex-wrap pt-0.5">
          <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-lg bg-[#CFEDE7]/60 text-[#1A4B43] border border-[#72C9BE]/30">
            <Check className="w-3 h-3 stroke-[2.5]" />
            <span>{completedCount} Done</span>
          </span>
          <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-lg bg-[#B7D4F4]/30 text-[#1E3A8A] border border-[#B7D4F4]/60">
            <span className="text-xs font-bold leading-none">◐</span>
            <span>{partialCount} Partly</span>
          </span>
          <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-lg bg-[#F2F5F8] text-[#6E7785] border border-[#E7EAF0]">
            <Minus className="w-3 h-3 stroke-[2.5]" />
            <span>{skippedCount} Skipped</span>
          </span>
          {unrecordedCount > 0 && (
            <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-lg bg-white text-slate-500 border border-slate-200">
              <Circle className="w-3 h-3 text-slate-400" />
              <span>{unrecordedCount} Unrecorded</span>
            </span>
          )}
        </div>

        <p className="text-xs text-slate-400 flex items-center gap-1.5 pt-0.5">
          <ShieldCheck className="w-4 h-4 text-[#72C9BE] flex-shrink-0" />
          <span>Skipped routines are excluded from progress. Take things at your own pace—never penalized.</span>
        </p>
      </div>

      {/* 3. Today's Routines with One-tap "Done" Action */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">Today's Routines</h2>
          <span className="text-xs text-slate-400 font-medium">
            {new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}
          </span>
        </div>

        {loading ? (
          <div className="p-10 text-center bg-white border border-[#E7EAF0] rounded-2xl shadow-card">
            <div className="w-6 h-6 border-2 border-[#72C9BE] border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <p className="text-xs text-slate-500">Loading routines...</p>
          </div>
        ) : todayRoutines.length === 0 ? (
          <div className="p-10 text-center bg-white border border-dashed border-[#E7EAF0] rounded-2xl shadow-card">
            <HeartPulse className="w-9 h-9 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-700 font-semibold">No routines scheduled for today</p>
            <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
              Enjoy your free breathing room, or tap "+ Add Routine" to track something meaningful for your wellbeing.
            </p>
            <button
              onClick={openAddModal}
              className="mt-4 inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#CFEDE7] hover:bg-[#bce6dc] text-[#1A4B43] rounded-xl text-xs font-semibold transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add a Routine</span>
            </button>
          </div>
        ) : (
          <div className="grid gap-2.5">
            {todayRoutines.map((routine) => {
              const cat = CATEGORIES.find((c) => c.id === routine.category) || CATEGORIES[0];
              const Icon = cat.icon;
              const status = routine.today_status || (routine.today_completed ? 'completed' : 'missed');
              const isDone = status === 'completed';
              const isPartial = status === 'partial';
              const isSkipped = status === 'skipped';
              const isExpanded = expandedRoutineId === routine.id;
              const snoozeMsg = snoozeMessages[routine.id];
              const quickChips = getQuickProgressChips(routine.name);

              return (
                <div
                  key={routine.id}
                  className={`group rounded-2xl border transition-all duration-200 ${
                    isDone
                      ? 'bg-[#F2FBF9] border-[#CFEDE7] shadow-xs'
                      : isPartial
                      ? 'bg-[#F4F8FD] border-[#B7D4F4]/70 shadow-xs'
                      : isSkipped
                      ? 'bg-[#F9FAFC] border-[#E7EAF0] opacity-80'
                      : 'bg-white border-[#E7EAF0] hover:border-slate-300 shadow-card'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3 p-4">
                    <div
                      className="flex items-center gap-3.5 min-w-0 cursor-pointer flex-1"
                      onClick={() => setExpandedRoutineId(isExpanded ? null : routine.id)}
                    >
                      {/* Category Icon */}
                      <div className={`p-2 rounded-xl border flex-shrink-0 ${cat.color}`}>
                        <Icon className="w-4 h-4" />
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span
                            className={`text-sm font-medium tracking-tight truncate ${
                              isDone
                                ? 'text-slate-400 line-through decoration-slate-300'
                                : isSkipped
                                ? 'text-slate-400 line-through decoration-slate-200'
                                : 'text-slate-800'
                            }`}
                          >
                            {routine.name}
                          </span>

                          {/* Routine Note or Today Partial Notes Pill */}
                          {routine.today_notes && (
                            <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-md bg-[#B7D4F4]/30 text-[#1E3A8A] border border-[#B7D4F4]/60">
                              <span>◐</span> {routine.today_notes}
                            </span>
                          )}

                          {routine.reminder_time && (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200">
                              <Clock className="w-3 h-3 text-[#72C9BE]" />
                              {routine.reminder_time === 'morning'
                                ? 'Morning'
                                : routine.reminder_time === 'afternoon'
                                ? 'Afternoon'
                                : routine.reminder_time === 'evening'
                                ? 'Evening'
                                : routine.reminder_time}
                            </span>
                          )}

                          {snoozeMsg && (
                            <span className="text-[11px] px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">
                              {snoozeMsg}
                            </span>
                          )}
                        </div>

                        {routine.note && (
                          <p className="text-xs text-slate-400 mt-0.5 truncate">{routine.note}</p>
                        )}
                      </div>
                    </div>

                    {/* Right Actions: Snooze + Status Trigger */}
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {!isDone && !isSkipped && routine.reminder_time && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSnooze(routine.id);
                          }}
                          className="px-2.5 py-1.5 text-xs text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors font-medium"
                          title="Snooze reminder for later"
                        >
                          Later
                        </button>
                      )}

                      {/* Clean Status Button / Badge Trigger */}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setExpandedRoutineId(isExpanded ? null : routine.id);
                        }}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
                          isDone
                            ? 'bg-[#CFEDE7] text-[#1A4B43] border-[#72C9BE] shadow-xs'
                            : isPartial
                            ? 'bg-[#B7D4F4]/40 text-[#1E3A8A] border-[#93C5FD] shadow-xs'
                            : isSkipped
                            ? 'bg-[#F2F5F8] text-[#6E7785] border-slate-200'
                            : 'bg-white hover:bg-[#CFEDE7]/30 text-slate-600 hover:text-slate-900 border-slate-200 hover:border-[#72C9BE]/50'
                        }`}
                      >
                        {isDone ? (
                          <>
                            <Check className="w-3.5 h-3.5 stroke-[2.5]" />
                            <span>Done</span>
                          </>
                        ) : isPartial ? (
                          <>
                            <span className="text-xs leading-none font-bold">◐</span>
                            <span>Partly</span>
                          </>
                        ) : isSkipped ? (
                          <>
                            <Minus className="w-3.5 h-3.5 stroke-[2.5]" />
                            <span>Skipped</span>
                          </>
                        ) : (
                          <>
                            <Circle className="w-3.5 h-3.5 text-slate-400" />
                            <span>Record</span>
                          </>
                        )}
                        {isExpanded ? (
                          <ChevronUp className="w-3.5 h-3.5 ml-0.5 opacity-60" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5 ml-0.5 opacity-60" />
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Expanded 3-Option Selector Drawer */}
                  {isExpanded && (
                    <div className="px-4 pb-4 pt-1 border-t border-[#E7EAF0]/80 space-y-3 animate-in fade-in duration-150">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500">Choose today's status:</span>
                        {status && status !== 'missed' && (
                          <button
                            type="button"
                            onClick={() => handleSetRoutineStatus(routine.id, 'missed', '')}
                            className="text-[11px] text-slate-400 hover:text-slate-600 underline font-medium cursor-pointer"
                          >
                            Reset / Clear
                          </button>
                        )}
                      </div>

                      <div className="grid grid-cols-3 gap-2">
                        {/* 1. Done */}
                        <button
                          type="button"
                          onClick={() => handleSetRoutineStatus(routine.id, 'completed')}
                          className={`flex items-center justify-center gap-1.5 py-2 px-2.5 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
                            isDone
                              ? 'bg-[#CFEDE7] text-[#1A4B43] border-[#72C9BE] ring-2 ring-[#72C9BE]/30 shadow-xs'
                              : 'bg-white hover:bg-[#CFEDE7]/40 text-slate-700 border-[#E7EAF0]'
                          }`}
                        >
                          <Check className="w-3.5 h-3.5 stroke-[2.5]" />
                          <span>✓ Done</span>
                        </button>

                        {/* 2. Partly */}
                        <button
                          type="button"
                          onClick={() => handleSetRoutineStatus(routine.id, 'partial')}
                          className={`flex items-center justify-center gap-1.5 py-2 px-2.5 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
                            isPartial
                              ? 'bg-[#B7D4F4]/40 text-[#1E3A8A] border-[#93C5FD] ring-2 ring-[#93C5FD]/30 shadow-xs'
                              : 'bg-white hover:bg-[#B7D4F4]/20 text-slate-700 border-[#E7EAF0]'
                          }`}
                        >
                          <span className="text-xs leading-none font-bold">◐</span>
                          <span>Partly</span>
                        </button>

                        {/* 3. Skip today */}
                        <button
                          type="button"
                          onClick={() => handleSetRoutineStatus(routine.id, 'skipped')}
                          className={`flex items-center justify-center gap-1.5 py-2 px-2.5 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
                            isSkipped
                              ? 'bg-[#F2F5F8] text-[#26313F] border-slate-300 ring-2 ring-slate-200 shadow-xs'
                              : 'bg-white hover:bg-slate-50 text-slate-700 border-[#E7EAF0]'
                          }`}
                        >
                          <Minus className="w-3.5 h-3.5 stroke-[2.5]" />
                          <span>– Skip today</span>
                        </button>
                      </div>

                      {/* Optional progress chips & note when Partly is selected */}
                      {isPartial && (
                        <div className="p-3 rounded-xl bg-slate-50/80 border border-slate-200/80 space-y-2 animate-in fade-in duration-150">
                          <div className="flex items-center justify-between text-[11px] text-slate-500">
                            <span>Optional progress (tap a quick amount or leave empty):</span>
                          </div>

                          <div className="flex items-center gap-1.5 flex-wrap">
                            {quickChips.map((chip) => {
                              const isChipSelected = (routine.today_notes || '') === chip;
                              return (
                                <button
                                  key={chip}
                                  type="button"
                                  onClick={() =>
                                    handleSetRoutineStatus(
                                      routine.id,
                                      'partial',
                                      isChipSelected ? '' : chip
                                    )
                                  }
                                  className={`px-2.5 py-1 rounded-lg text-xs border transition-all cursor-pointer ${
                                    isChipSelected
                                      ? 'bg-[#B7D4F4] text-[#1E3A8A] border-[#93C5FD] font-semibold'
                                      : 'bg-white hover:bg-slate-100 text-slate-600 border-slate-200'
                                  }`}
                                >
                                  {chip}
                                </button>
                              );
                            })}
                          </div>

                          <div className="flex items-center gap-2 pt-0.5">
                            <input
                              type="text"
                              value={partialNotesDraft[routine.id] ?? (routine.today_notes || '')}
                              onChange={(e) =>
                                setPartialNotesDraft((prev) => ({
                                  ...prev,
                                  [routine.id]: e.target.value
                                }))
                              }
                              onBlur={(e) => {
                                if (e.target.value !== (routine.today_notes || '')) {
                                  handleSetRoutineStatus(
                                    routine.id,
                                    'partial',
                                    e.target.value.trim()
                                  );
                                }
                              }}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  e.preventDefault();
                                  handleSetRoutineStatus(
                                    routine.id,
                                    'partial',
                                    (partialNotesDraft[routine.id] ?? '').trim()
                                  );
                                }
                              }}
                              placeholder="Or type amount (e.g. 6h, 1.5L)..."
                              className="flex-1 text-xs px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-[#72C9BE] focus:border-[#72C9BE]"
                            />
                            {partialNotesDraft[routine.id] !== undefined &&
                              partialNotesDraft[routine.id] !== (routine.today_notes || '') && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    handleSetRoutineStatus(
                                      routine.id,
                                      'partial',
                                      (partialNotesDraft[routine.id] ?? '').trim()
                                    )
                                  }
                                  className="px-2.5 py-1.5 bg-[#CFEDE7] hover:bg-[#bce5dd] text-[#1A4B43] rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                                >
                                  Save
                                </button>
                              )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. Compact Weekly Summary */}
      <div className="bg-white border border-[#E7EAF0] rounded-2xl p-5 shadow-card space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-[#72C9BE]" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">Weekly Summary</h3>
          </div>
          <div className="flex items-center gap-2 flex-wrap text-xs">
            <span className="px-2 py-0.5 rounded-md bg-[#CFEDE7] text-[#1A4B43] font-semibold">
              ✓ {weeklySummary.total_completed || 0} completed
            </span>
            <span className="px-2 py-0.5 rounded-md bg-[#B7D4F4]/40 text-[#1E3A8A] font-semibold">
              ◐ {weeklySummary.total_partial || 0} partly
            </span>
            <span className="px-2 py-0.5 rounded-md bg-[#F2F5F8] text-[#6E7785] font-medium border border-[#E7EAF0]">
              – {weeklySummary.total_skipped || 0} skipped
            </span>
            <span className="text-slate-400 font-medium">
              ({weeklySummary.overall_percentage || 0}% active completion)
            </span>
          </div>
        </div>

        {/* 7-Day compact horizontal strip */}
        <div className="grid grid-cols-7 gap-1.5 sm:gap-2.5">
          {weeklySummary.days &&
            weeklySummary.days.map((day) => {
              const isToday =
                new Date(day.date).toDateString() === new Date().toDateString();
              const hasRoutines = (day.total_count || 0) > 0;
              const hasDone = (day.completed_count || 0) > 0;
              const hasPartly = (day.partial_count || 0) > 0;
              const hasSkipped = (day.skipped_count || 0) > 0;

              return (
                <div
                  key={day.date}
                  className={`flex flex-col items-center justify-between p-2 sm:p-2.5 rounded-xl text-center min-h-[82px] transition-all ${
                    isToday
                      ? 'bg-[#CFEDE7]/30 border-2 border-[#72C9BE] text-slate-800 shadow-xs'
                      : 'bg-[#F7F8FC] border border-[#E7EAF0] text-slate-600'
                  }`}
                >
                  <div>
                    <span className={`text-[11px] font-bold block ${isToday ? 'text-[#1A4B43]' : 'text-slate-600'}`}>
                      {day.day_name}
                    </span>
                    <span className="text-[10px] text-slate-400 block">
                      {new Date(day.date).getDate()}
                    </span>
                  </div>

                  <div className="mt-1 flex flex-col items-center gap-1 w-full">
                    {hasRoutines ? (
                      <div className="flex flex-wrap items-center justify-center gap-0.5">
                        {hasDone && (
                          <span
                            title={`${day.completed_count} completed`}
                            className="text-[9px] font-bold px-1 rounded bg-[#CFEDE7] text-[#1A4B43]"
                          >
                            ✓{day.completed_count}
                          </span>
                        )}
                        {hasPartly && (
                          <span
                            title={`${day.partial_count} partly completed`}
                            className="text-[9px] font-bold px-1 rounded bg-[#B7D4F4] text-[#1E3A8A]"
                          >
                            ◐{day.partial_count}
                          </span>
                        )}
                        {hasSkipped && (
                          <span
                            title={`${day.skipped_count} skipped`}
                            className="text-[9px] font-medium px-1 rounded bg-slate-200 text-slate-600"
                          >
                            –{day.skipped_count}
                          </span>
                        )}
                        {!hasDone && !hasPartly && !hasSkipped && (
                          <span className="text-[10px] text-slate-300 font-medium">0/{day.total_count}</span>
                        )}
                      </div>
                    ) : (
                      <span className="text-[10px] text-slate-300">-</span>
                    )}
                  </div>
                </div>
              );
            })}
        </div>
      </div>

      {/* ======================================================== */}
      {/* ADD / EDIT ROUTINE MODAL */}
      {/* ======================================================== */}
      {editModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
          <div className="bg-white border border-[#E7EAF0] rounded-2xl w-full max-w-lg overflow-hidden shadow-float animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between p-5 border-b border-[#E7EAF0]">
              <h3 className="text-base font-semibold text-slate-800 flex items-center gap-2">
                <span className="p-1.5 rounded-lg bg-[#CFEDE7] text-[#1A4B43]">
                  <HeartPulse className="w-4 h-4" />
                </span>
                <span>{editingRoutineId ? 'Edit Routine' : 'Add Routine'}</span>
              </h3>
              <button
                onClick={() => setEditModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveRoutine} className="p-5 space-y-4">
              {/* Routine Name */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Routine Name <span className="text-[#72C9BE]">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g., Morning Hydration (750ml), Clinical Prep, 20m Walk"
                  value={routineForm.name}
                  onChange={(e) => setRoutineForm({ ...routineForm, name: e.target.value })}
                  className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3.5 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                />
              </div>

              {/* Category */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">Category</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {CATEGORIES.map((c) => {
                    const isSelected = routineForm.category === c.id;
                    const Icon = c.icon;
                    return (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => setRoutineForm({ ...routineForm, category: c.id })}
                        className={`flex items-center gap-2 p-2 rounded-xl text-xs border text-left transition-all ${
                          isSelected
                            ? 'bg-[#CFEDE7] border-[#72C9BE] text-[#1A4B43] font-semibold'
                            : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                        }`}
                      >
                        <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                        <span className="truncate">{c.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Selected Days */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-semibold text-slate-700">Repeat Days</label>
                  <div className="flex gap-2 text-[11px] text-[#1A4B43]">
                    <button
                      type="button"
                      onClick={() => setRoutineForm({ ...routineForm, selected_days: '0,1,2,3,4,5,6' })}
                      className="hover:underline font-medium"
                    >
                      Everyday
                    </button>
                    <span className="text-slate-300">•</span>
                    <button
                      type="button"
                      onClick={() => setRoutineForm({ ...routineForm, selected_days: '0,1,2,3,4' })}
                      className="hover:underline font-medium"
                    >
                      Weekdays
                    </button>
                    <span className="text-slate-300">•</span>
                    <button
                      type="button"
                      onClick={() => setRoutineForm({ ...routineForm, selected_days: '5,6' })}
                      className="hover:underline font-medium"
                    >
                      Weekends
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-between gap-1.5">
                  {DAYS_MAP.map((d) => {
                    const selected = routineForm.selected_days.split(',').map((s) => s.trim()).includes(d.id);
                    return (
                      <button
                        key={d.id}
                        type="button"
                        onClick={() => toggleDay(d.id)}
                        className={`flex-1 py-2 rounded-xl text-xs font-semibold border transition-all ${
                          selected
                            ? 'bg-[#72C9BE] text-slate-900 border-[#72C9BE]'
                            : 'bg-slate-50 border-slate-200 text-slate-600 hover:text-slate-900'
                        }`}
                      >
                        {d.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Optional Reminder */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Optional Reminder
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-2">
                  {[
                    { id: 'none', label: 'None' },
                    { id: 'morning', label: 'Morning' },
                    { id: 'afternoon', label: 'Afternoon' },
                    { id: 'evening', label: 'Evening' },
                  ].map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setRoutineForm({ ...routineForm, reminder_preset: p.id })}
                      className={`py-1.5 px-2 rounded-xl text-xs border text-center transition-all ${
                        routineForm.reminder_preset === p.id
                          ? 'bg-[#CFEDE7] border-[#72C9BE] text-[#1A4B43] font-semibold'
                          : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setRoutineForm({ ...routineForm, reminder_preset: 'custom' })}
                    className={`py-1.5 px-3 rounded-xl text-xs border transition-all ${
                      routineForm.reminder_preset === 'custom'
                        ? 'bg-[#CFEDE7] border-[#72C9BE] text-[#1A4B43] font-semibold'
                        : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                    }`}
                  >
                    Custom Time
                  </button>

                  {routineForm.reminder_preset === 'custom' && (
                    <input
                      type="time"
                      value={routineForm.reminder_time || '08:00'}
                      onChange={(e) => setRoutineForm({ ...routineForm, reminder_time: e.target.value })}
                      className="bg-white border border-[#E7EAF0] rounded-xl px-2.5 py-1 text-xs text-slate-800 focus:outline-none focus:border-[#72C9BE]"
                    />
                  )}
                </div>
              </div>

              {/* Optional Note */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Optional Note</label>
                <textarea
                  rows={2}
                  placeholder="e.g. Keep water bottle in locker, stretch for 5 minutes..."
                  value={routineForm.note}
                  onChange={(e) => setRoutineForm({ ...routineForm, note: e.target.value })}
                  className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3 py-2 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-[#72C9BE] resize-none"
                />
              </div>

              {/* Active / Paused State Toggle */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200">
                <div>
                  <span className="text-xs font-semibold text-slate-700">Routine State</span>
                  <p className="text-[11px] text-slate-400">
                    {routineForm.is_paused ? 'Currently Paused (will not appear in Today)' : 'Active (scheduled normally)'}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setRoutineForm({ ...routineForm, is_paused: !routineForm.is_paused })}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                    routineForm.is_paused
                      ? 'bg-amber-100 text-amber-800 border border-amber-300'
                      : 'bg-[#CFEDE7] text-[#1A4B43] border border-[#72C9BE]/50'
                  }`}
                >
                  {routineForm.is_paused ? 'Paused' : 'Active'}
                </button>
              </div>

              {/* Actions */}
              <div className="flex items-center justify-end gap-2 pt-3 border-t border-[#E7EAF0]">
                <button
                  type="button"
                  onClick={() => setEditModalOpen(false)}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium rounded-xl transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 text-xs font-semibold rounded-xl transition-colors shadow-xs"
                >
                  {editingRoutineId ? 'Save Changes' : 'Create Routine'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* MANAGE MODAL (My Routines, Reminder Settings, History, Paused) */}
      {/* ======================================================== */}
      {manageModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
          <div className="bg-white border border-[#E7EAF0] rounded-2xl w-full max-w-2xl max-h-[88vh] flex flex-col shadow-float animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-5 border-b border-[#E7EAF0] flex-shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-[#CFEDE7] text-[#1A4B43]">
                  <Sliders className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-slate-800">Manage Routine & Wellbeing</h3>
                  <p className="text-xs text-slate-400">Configure routines, reminders, quiet hours, and history</p>
                </div>
              </div>
              <button
                onClick={() => setManageModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Manage Tabs */}
            <div className="flex border-b border-[#E7EAF0] bg-slate-50/50 px-5 gap-4 overflow-x-auto flex-shrink-0">
              {[
                { id: 'my-routines', label: 'My Routines', icon: HeartPulse },
                { id: 'settings', label: 'Reminder Settings', icon: Bell },
                { id: 'history', label: 'History', icon: History },
                { id: 'paused', label: 'Paused Routines', icon: PauseCircle },
              ].map((tab) => {
                const Icon = tab.icon;
                const active = manageTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setManageTab(tab.id)}
                    className={`flex items-center gap-2 py-3 border-b-2 text-xs font-semibold whitespace-nowrap transition-colors ${
                      active
                        ? 'border-[#72C9BE] text-[#1A4B43]'
                        : 'border-transparent text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Tab Content Container */}
            <div className="p-5 overflow-y-auto space-y-4 flex-1">
              {/* TAB 1: MY ROUTINES */}
              {manageTab === 'my-routines' && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-500">All created routines ({allRoutines.length})</span>
                    <button
                      onClick={() => {
                        setManageModalOpen(false);
                        openAddModal();
                      }}
                      className="text-xs text-[#1A4B43] hover:underline inline-flex items-center gap-1 font-semibold"
                    >
                      <Plus className="w-3 h-3" /> Add New
                    </button>
                  </div>

                  {allRoutines.length === 0 ? (
                    <div className="p-6 text-center bg-slate-50 rounded-xl border border-[#E7EAF0]">
                      <p className="text-xs text-slate-400">No routines created yet.</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {allRoutines.map((routine) => {
                        const days = (routine.selected_days || '').split(',').map((s) => s.trim());
                        const isPaused = Boolean(routine.is_paused);
                        return (
                          <div
                            key={routine.id}
                            className={`flex items-center justify-between gap-3 p-3.5 rounded-xl border transition-all ${
                              isPaused
                                ? 'bg-slate-50 border-slate-200 opacity-75'
                                : 'bg-white border-[#E7EAF0] shadow-xs'
                            }`}
                          >
                            <div className="min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-sm font-semibold text-slate-800 truncate">{routine.name}</span>
                                {isPaused ? (
                                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                                    Paused
                                  </span>
                                ) : (
                                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#CFEDE7] text-[#1A4B43]">
                                    Active
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-2 text-xs text-slate-500 mt-1">
                                <span className="capitalize">{routine.category}</span>
                                <span>•</span>
                                <span>
                                  {days.length === 7
                                    ? 'Daily'
                                    : days.map((d) => DAYS_MAP.find((m) => m.id === d)?.full).join(', ')}
                                </span>
                                {routine.reminder_time && (
                                  <>
                                    <span>•</span>
                                    <span className="text-[#1A4B43] flex items-center gap-0.5 font-medium">
                                      <Clock className="w-3 h-3" />
                                      {routine.reminder_time}
                                    </span>
                                  </>
                                )}
                              </div>
                            </div>

                            <div className="flex items-center gap-1.5 flex-shrink-0">
                              <button
                                onClick={() => handleTogglePause(routine.id)}
                                className={`p-2 rounded-lg text-xs font-medium border transition-colors ${
                                  isPaused
                                    ? 'bg-[#CFEDE7] text-[#1A4B43] border-[#72C9BE] hover:bg-[#bce6dc]'
                                    : 'bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200'
                                }`}
                                title={isPaused ? 'Resume Routine' : 'Pause Routine'}
                              >
                                {isPaused ? <PlayCircle className="w-4 h-4" /> : <PauseCircle className="w-4 h-4" />}
                              </button>

                              <button
                                onClick={() => openEditModal(routine)}
                                className="p-2 rounded-lg bg-slate-100 text-slate-600 hover:text-slate-900 border border-slate-200 hover:bg-slate-200 transition-colors"
                                title="Edit routine"
                              >
                                <Edit3 className="w-4 h-4" />
                              </button>

                              <button
                                onClick={() => handleDeleteRoutine(routine.id, routine.name)}
                                className="p-2 rounded-lg bg-rose-50 text-rose-600 hover:bg-rose-100 border border-rose-200 transition-colors"
                                title="Delete routine"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: REMINDER SETTINGS */}
              {manageTab === 'settings' && (
                <form onSubmit={handleSaveSettings} className="space-y-4">
                  {settingsSavedMessage && (
                    <div className="p-3 bg-[#CFEDE7] border border-[#72C9BE] rounded-xl flex items-center gap-2 text-[#1A4B43] text-xs font-medium animate-in fade-in">
                      <Sparkles className="w-4 h-4" />
                      <span>Reminder settings saved successfully!</span>
                    </div>
                  )}

                  {/* Non-punitive banner */}
                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-start gap-2.5 text-xs text-slate-600">
                    <Info className="w-4 h-4 text-[#72C9BE] flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-slate-800">Thoughtful Notification Promise</p>
                      <p className="text-slate-500 mt-0.5">
                        MedPilot will never repeatedly nag you for missed routines. Missed routines are simply marked missed with zero guilt or punitive warnings.
                      </p>
                    </div>
                  </div>

                  {/* Master Reminders Switch */}
                  <div className="flex items-center justify-between p-3.5 bg-white border border-[#E7EAF0] rounded-xl shadow-xs">
                    <div>
                      <span className="text-xs font-semibold text-slate-800">Enable Routine Reminders</span>
                      <p className="text-[11px] text-slate-400">Receive gentle in-app nudges for scheduled routines</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSettings({ ...settings, reminders_enabled: !settings.reminders_enabled })}
                      className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors ${
                        settings.reminders_enabled ? 'bg-[#72C9BE] justify-end' : 'bg-slate-200 justify-start'
                      }`}
                    >
                      <div className="bg-white w-4 h-4 rounded-full shadow-md transform" />
                    </button>
                  </div>

                  {/* Pause Reminders Today */}
                  <div className="flex items-center justify-between p-3.5 bg-white border border-[#E7EAF0] rounded-xl shadow-xs">
                    <div>
                      <span className="text-xs font-semibold text-slate-800">Pause Reminders Today</span>
                      <p className="text-[11px] text-slate-400">Take a peaceful day off without any notifications</p>
                    </div>
                    <button
                      type="button"
                      onClick={() =>
                        setSettings({ ...settings, pause_reminders_today: !settings.pause_reminders_today })
                      }
                      className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors ${
                        settings.pause_reminders_today ? 'bg-[#72C9BE] justify-end' : 'bg-slate-200 justify-start'
                      }`}
                    >
                      <div className="bg-white w-4 h-4 rounded-full shadow-md transform" />
                    </button>
                  </div>

                  {/* Quiet Hours */}
                  <div className="p-3.5 bg-white border border-[#E7EAF0] rounded-xl shadow-xs space-y-2.5">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-xs font-semibold text-slate-800">Quiet Hours</span>
                        <p className="text-[11px] text-slate-400">Mute all reminders during rest or night hours</p>
                      </div>
                      <button
                        type="button"
                        onClick={() =>
                          setSettings({ ...settings, quiet_hours_enabled: !settings.quiet_hours_enabled })
                        }
                        className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors ${
                          settings.quiet_hours_enabled ? 'bg-[#72C9BE] justify-end' : 'bg-slate-200 justify-start'
                        }`}
                      >
                        <div className="bg-white w-4 h-4 rounded-full shadow-md transform" />
                      </button>
                    </div>

                    {settings.quiet_hours_enabled && (
                      <div className="flex items-center gap-3 pt-2 border-t border-[#E7EAF0]">
                        <div className="flex-1">
                          <label className="text-[10px] text-slate-500 font-medium">From</label>
                          <input
                            type="time"
                            value={settings.quiet_hours_start}
                            onChange={(e) => setSettings({ ...settings, quiet_hours_start: e.target.value })}
                            className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1 text-xs text-slate-800 focus:bg-white focus:border-[#72C9BE]"
                          />
                        </div>
                        <div className="flex-1">
                          <label className="text-[10px] text-slate-500 font-medium">To</label>
                          <input
                            type="time"
                            value={settings.quiet_hours_end}
                            onChange={(e) => setSettings({ ...settings, quiet_hours_end: e.target.value })}
                            className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1 text-xs text-slate-800 focus:bg-white focus:border-[#72C9BE]"
                          />
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Timetable Integration & Batching */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between p-3.5 bg-white border border-[#E7EAF0] rounded-xl shadow-xs">
                      <div>
                        <span className="text-xs font-semibold text-slate-800">
                          Use Timetable to Avoid Class Interruptions
                        </span>
                        <p className="text-[11px] text-slate-400">
                          Automatically suppress reminders when you have a scheduled MBBS class
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() =>
                          setSettings({ ...settings, avoid_during_classes: !settings.avoid_during_classes })
                        }
                        className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors ${
                          settings.avoid_during_classes ? 'bg-[#72C9BE] justify-end' : 'bg-slate-200 justify-start'
                        }`}
                      >
                        <div className="bg-white w-4 h-4 rounded-full shadow-md transform" />
                      </button>
                    </div>

                    <div className="flex items-center justify-between p-3.5 bg-white border border-[#E7EAF0] rounded-xl shadow-xs">
                      <div>
                        <span className="text-xs font-semibold text-slate-800">Combine Nearby Reminders</span>
                        <p className="text-[11px] text-slate-400">
                          Group routines within 30 minutes into a single convenient digest
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSettings({ ...settings, combine_nearby: !settings.combine_nearby })}
                        className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors ${
                          settings.combine_nearby ? 'bg-[#72C9BE] justify-end' : 'bg-slate-200 justify-start'
                        }`}
                      >
                        <div className="bg-white w-4 h-4 rounded-full shadow-md transform" />
                      </button>
                    </div>
                  </div>

                  {/* Default Timing Slots */}
                  <div className="p-3.5 bg-white border border-[#E7EAF0] rounded-xl shadow-xs space-y-2">
                    <span className="text-xs font-semibold text-slate-800">Default Slot Times</span>
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <label className="text-[10px] text-slate-500 font-medium">Morning</label>
                        <input
                          type="time"
                          value={settings.morning_time}
                          onChange={(e) => setSettings({ ...settings, morning_time: e.target.value })}
                          className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2 py-1 text-xs text-slate-800 focus:bg-white focus:border-[#72C9BE]"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-500 font-medium">Afternoon</label>
                        <input
                          type="time"
                          value={settings.afternoon_time}
                          onChange={(e) => setSettings({ ...settings, afternoon_time: e.target.value })}
                          className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2 py-1 text-xs text-slate-800 focus:bg-white focus:border-[#72C9BE]"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-500 font-medium">Evening</label>
                        <input
                          type="time"
                          value={settings.evening_time}
                          onChange={(e) => setSettings({ ...settings, evening_time: e.target.value })}
                          className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2 py-1 text-xs text-slate-800 focus:bg-white focus:border-[#72C9BE]"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="flex justify-end pt-2">
                    <button
                      type="submit"
                      className="px-4 py-2 bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 text-xs font-semibold rounded-xl transition-colors shadow-xs"
                    >
                      Save Settings
                    </button>
                  </div>
                </form>
              )}

              {/* TAB 3: HISTORY */}
              {manageTab === 'history' && (
                <div className="space-y-3">
                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-600 flex items-center gap-2">
                    <History className="w-4 h-4 text-[#72C9BE] flex-shrink-0" />
                    <span>
                      Past 14 days history. Missed routines are simply marked missed without guilt or streak warnings.
                    </span>
                  </div>

                  {historyLogs.length === 0 ? (
                    <div className="p-8 text-center bg-slate-50 rounded-xl border border-slate-200">
                      <p className="text-xs text-slate-400">No history logs recorded yet.</p>
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      {historyLogs.map((log) => (
                        <div
                          key={log.id}
                          className="flex items-center justify-between p-3 rounded-xl bg-white border border-[#E7EAF0] shadow-xs text-xs"
                        >
                          <div>
                            <span className="font-semibold text-slate-800">{log.habit_name}</span>
                            <span className="text-[11px] text-slate-400 ml-2">
                              {new Date(log.date).toLocaleDateString(undefined, {
                                month: 'short',
                                day: 'numeric',
                                weekday: 'short'
                              })}
                            </span>
                          </div>

                          <div className="flex items-center gap-1.5">
                            {log.notes && (
                              <span className="text-[10px] text-slate-600 bg-slate-100 px-2 py-0.5 rounded-md border border-slate-200/80 font-medium">
                                {log.notes}
                              </span>
                            )}
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                                log.status === 'completed'
                                  ? 'bg-[#CFEDE7] text-[#1A4B43]'
                                  : log.status === 'partial'
                                  ? 'bg-[#B7D4F4]/40 text-[#1E3A8A]'
                                  : log.status === 'skipped'
                                  ? 'bg-[#F2F5F8] text-[#6E7785] border border-[#E7EAF0]'
                                  : 'bg-slate-100 text-slate-400'
                              }`}
                            >
                              {log.status === 'completed'
                                ? '✓ Done'
                                : log.status === 'partial'
                                ? '◐ Partly'
                                : log.status === 'skipped'
                                ? '– Skipped'
                                : 'Missed'}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 4: PAUSED / ARCHIVED ROUTINES */}
              {manageTab === 'paused' && (
                <div className="space-y-3">
                  <p className="text-xs text-slate-500">
                    Paused routines do not appear in your daily list or send reminders. You can resume them anytime.
                  </p>

                  {allRoutines.filter((r) => r.is_paused).length === 0 ? (
                    <div className="p-8 text-center bg-slate-50 rounded-xl border border-slate-200">
                      <PauseCircle className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                      <p className="text-xs text-slate-400">You don't have any paused routines right now.</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {allRoutines
                        .filter((r) => r.is_paused)
                        .map((routine) => (
                          <div
                            key={routine.id}
                            className="flex items-center justify-between p-3 rounded-xl bg-white border border-[#E7EAF0] shadow-xs"
                          >
                            <div>
                              <span className="text-sm font-semibold text-slate-700">{routine.name}</span>
                              <span className="text-xs text-slate-400 ml-2 capitalize">({routine.category})</span>
                            </div>

                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => handleTogglePause(routine.id)}
                                className="flex items-center gap-1 px-3 py-1 bg-[#CFEDE7] hover:bg-[#bce6dc] text-[#1A4B43] rounded-lg text-xs font-semibold transition-colors"
                              >
                                <PlayCircle className="w-3.5 h-3.5" />
                                <span>Resume</span>
                              </button>

                              <button
                                onClick={() => handleDeleteRoutine(routine.id, routine.name)}
                                className="p-1.5 text-rose-500 hover:bg-rose-50 rounded-lg transition-colors"
                                title="Delete routine"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
