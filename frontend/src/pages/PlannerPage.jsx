import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BookOpen,
  Plus,
  Sparkles,
  Clock,
  Play,
  Check,
  Trash2,
  Edit2,
  X,
  Timer,
  HeartPulse,
  Calendar,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
  RefreshCw,
  CheckCircle2,
  Info,
  Minus,
  Zap,
  ChevronDown,
  RotateCcw,
  Sliders,
  MoreHorizontal
} from 'lucide-react';
import { apiRequest } from '../api/client';

export default function PlannerPage() {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [currentSemesterSubjects, setCurrentSemesterSubjects] = useState([]);
  const [otherSubjects, setOtherSubjects] = useState([]);
  const [showAllSubjects, setShowAllSubjects] = useState(false);
  const [exams, setExams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('today'); // 'today', 'upcoming', 'completed'

  // Toast / Status Message State (replaces browser alerts)
  const [toast, setToast] = useState(null); // { message: string, type: 'success' | 'info' | 'error' }

  const showToast = (message, type = 'success', duration = 4500) => {
    setToast({ message, type });
    if (duration) {
      setTimeout(() => {
        setToast((curr) => (curr?.message === message ? null : curr));
      }, duration);
    }
  };

  // Workload Recommendation & Rescheduling State
  const [recommendation, setRecommendation] = useState(null);
  const [rescheduling, setRescheduling] = useState(false);
  const [rescheduleNotice, setRescheduleNotice] = useState('');

  // Modals
  const [addTaskModal, setAddTaskModal] = useState(false);
  const [aiPlanModal, setAiPlanModal] = useState(false);
  const [selectedTaskDetail, setSelectedTaskDetail] = useState(null);
  const [completingTask, setCompletingTask] = useState(null);
  const [completionFeedback, setCompletionFeedback] = useState(null);

  // Need More Time Interactive Workflow States
  const [nmtStep, setNmtStep] = useState(null); // null, 'continue_now', 'no_space'
  const [continueEndTime, setContinueEndTime] = useState('');
  const [continueDurationMinutes, setContinueDurationMinutes] = useState(30);
  const [showSpecificEndTime, setShowSpecificEndTime] = useState(false);
  const [addToPlanMinutes, setAddToPlanMinutes] = useState(45);
  const [showMoveTaskPicker, setShowMoveTaskPicker] = useState(false);
  const [selectedMoveTaskId, setSelectedMoveTaskId] = useState('');
  const [continueConflict, setContinueConflict] = useState(null);
  const [noSpaceData, setNoSpaceData] = useState(null);
  const [replanLoading, setReplanLoading] = useState(false);

  // Exam Sync Status States
  const [examSyncNeeded, setExamSyncNeeded] = useState(false);
  const [changedExams, setChangedExams] = useState([]);
  const [syncingExams, setSyncingExams] = useState(false);

  // Task Action States (⋯ menu, Edit, Move/Reschedule, Delete)
  const [openMenuTaskId, setOpenMenuTaskId] = useState(null);
  const [editingTask, setEditingTask] = useState(null);
  const [editForm, setEditForm] = useState({
    title: '',
    subject_id: '',
    estimated_minutes: 45,
    priority: 'medium',
    description: ''
  });
  const [reschedulingTask, setReschedulingTask] = useState(null);
  const [rescheduleDate, setRescheduleDate] = useState('');
  const [deletingTask, setDeletingTask] = useState(null);

  // Missed class topics & controls
  const [missedClasses, setMissedClasses] = useState([]);
  const [missedClassesOpen, setMissedClassesOpen] = useState(true);
  const [snoozeModalTopic, setSnoozeModalTopic] = useState(null);
  const [snoozePreset, setSnoozePreset] = useState('tomorrow');
  const [customSnoozeDate, setCustomSnoozeDate] = useState('');
  const [skipModalTopic, setSkipModalTopic] = useState(null);
  const [selectedSkipReason, setSelectedSkipReason] = useState('skip_plan_only');
  const [showDevDiagnostics, setShowDevDiagnostics] = useState(false);

  // Persistent Focus Session State (survives page navigation via localStorage)
  const [focusSession, setFocusSession] = useState(null); // { task, plannedMinutes, accumulatedSeconds, lastStartedAt, isRunning }
  const [timerTick, setTimerTick] = useState(0);

  // Task form
  const [taskForm, setTaskForm] = useState({
    title: '',
    subject_id: '',
    exam_id: '',
    priority: 'medium',
    estimated_minutes: 45,
    scheduled_date: new Date().toISOString().split('T')[0],
    scheduled_time: '18:00'
  });

  // Structured AI Plan form
  const [aiPlanForm, setAiPlanForm] = useState({
    plan_days: 2,
    study_hours: 1,
    study_minutes: 0,
    subject_mode: 'all',
    subject_ids: [],
    planning_style: 'balanced',
    until_next_exam: false,
    quick_review_mode: false
  });
  const [aiGenerating, setAiGenerating] = useState(false);

  const loadPlannerData = async () => {
    try {
      setLoading(true);
      const [taskList, plannerSubjData, examList, recData, missedList, examSyncData] = await Promise.all([
        apiRequest('/planner/tasks'),
        apiRequest('/planner/subjects').catch(async () => {
          const raw = await apiRequest('/subjects/');
          return {
            current_semester_subjects: raw || [],
            other_subjects: [],
            all_subjects: raw || []
          };
        }),
        apiRequest('/exams/'),
        apiRequest('/planner/recommendation/today').catch(() => null),
        apiRequest('/planner/missed-topics').catch(() => []),
        apiRequest('/planner/exam-sync-status').catch(() => null)
      ]);
      setTasks(taskList || []);
      setMissedClasses(missedList || []);
      if (examSyncData && examSyncData.exam_sync_needed) {
        setExamSyncNeeded(true);
        setChangedExams(examSyncData.changed_exams || []);
      } else {
        setExamSyncNeeded(false);
      }

      const allSubjs = plannerSubjData?.all_subjects || [];
      const currentSubjs =
        plannerSubjData?.current_semester_subjects && plannerSubjData.current_semester_subjects.length > 0
          ? plannerSubjData.current_semester_subjects
          : allSubjs;
      const others = plannerSubjData?.other_subjects || [];

      setSubjects(allSubjs);
      setCurrentSemesterSubjects(currentSubjs);
      setOtherSubjects(others);
      setExams(examList || []);
      setRecommendation(recData);

      const defaultSubjId = currentSubjs[0]?.id || allSubjs[0]?.id;
      if (defaultSubjId && !taskForm.subject_id) {
        setTaskForm((prev) => ({ ...prev, subject_id: defaultSubjId }));
      }
      if (currentSubjs.length > 0) {
        setAiPlanForm((prev) => ({
          ...prev,
          subject_ids: prev.subject_ids.length > 0 ? prev.subject_ids : currentSubjs.map((s) => s.id)
        }));
      }
    } catch (err) {
      console.error('Error loading planner:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSyncExams = async () => {
    try {
      setSyncingExams(true);
      await apiRequest('/planner/sync-exams', { method: 'POST' });
      setExamSyncNeeded(false);
      showToast('Study plan updated with latest exam details ✓', 'success');
      await loadPlannerData();
    } catch (err) {
      showToast(`Failed to update plan: ${err.message}`, 'error');
    } finally {
      setSyncingExams(false);
    }
  };

  useEffect(() => {
    loadPlannerData();
  }, []);

  // Restore active focus session from localStorage on mount (survives page navigation)
  useEffect(() => {
    try {
      const raw = localStorage.getItem('medpilot_active_study_session');
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && parsed.task) {
          setFocusSession(parsed);
        }
      }
    } catch (err) {
      console.error('Failed to load saved study session:', err);
    }
  }, []);

  // Compute exact elapsed seconds from wall clock without drift
  const getElapsedSeconds = (session) => {
    if (!session) return 0;
    const accum = session.accumulatedSeconds || 0;
    if (!session.isRunning || !session.lastStartedAt) return accum;
    const added = Math.max(0, Math.floor((Date.now() - session.lastStartedAt) / 1000));
    return accum + added;
  };

  // Timer interval triggers re-render every second when running
  useEffect(() => {
    let interval = null;
    if (focusSession && focusSession.isRunning) {
      interval = setInterval(() => {
        setTimerTick((t) => t + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [focusSession?.isRunning]);

  const handleStartTask = (task) => {
    const mins = task.estimated_minutes || 45;
    const sessionObj = {
      task,
      plannedMinutes: mins,
      accumulatedSeconds: 0,
      lastStartedAt: Date.now(),
      isRunning: true
    };
    setFocusSession(sessionObj);
    try {
      localStorage.setItem('medpilot_active_study_session', JSON.stringify(sessionObj));
    } catch (e) {
      console.error(e);
    }
  };

  const handleCancelSession = () => {
    try {
      localStorage.removeItem('medpilot_active_study_session');
    } catch (e) {}
    setFocusSession(null);
    showToast('Study session cancelled', 'info');
  };

  const handlePauseResume = () => {
    setFocusSession((prev) => {
      if (!prev) return null;
      const now = Date.now();
      let updated;
      if (prev.isRunning) {
        const added = prev.lastStartedAt ? Math.max(0, Math.floor((now - prev.lastStartedAt) / 1000)) : 0;
        updated = {
          ...prev,
          accumulatedSeconds: (prev.accumulatedSeconds || 0) + added,
          lastStartedAt: null,
          isRunning: false
        };
      } else {
        updated = {
          ...prev,
          lastStartedAt: now,
          isRunning: true
        };
      }
      try {
        localStorage.setItem('medpilot_active_study_session', JSON.stringify(updated));
      } catch (e) {}
      return updated;
    });
  };


  const handleFinishFocusSession = () => {
    if (!focusSession) return;
    const task = focusSession.task;
    const elapsedSecs = getElapsedSeconds(focusSession);
    const spentMinutes = Math.max(1, Math.round(elapsedSecs / 60));
    const plannedMinutes = focusSession.plannedMinutes || task.estimated_minutes || 45;
    const savedFeedback = focusSession.persistedFeedback || null;

    try {
      localStorage.removeItem('medpilot_active_study_session');
    } catch (e) {}

    setFocusSession(null);

    setCompletingTask({
      ...task,
      plannedMinutes,
      actualMinutes: spentMinutes
    });
    setCompletionFeedback(savedFeedback);
  };

  const handleRescheduleOptional = async () => {
    if (!window.confirm("Move today's unfinished medium and low priority tasks to tomorrow? High-priority tasks will stay scheduled for today.")) return;
    try {
      setRescheduling(true);
      const res = await apiRequest('/planner/tasks/reschedule-optional', {
        method: 'POST',
        body: JSON.stringify({})
      });
      setRescheduleNotice(res.message);
      setTimeout(() => setRescheduleNotice(''), 4500);
      showToast(res.message || 'Rescheduled optional tasks to tomorrow', 'success');
      loadPlannerData();
    } catch (err) {
      showToast(`Error rescheduling tasks: ${err.message}`, 'error');
    } finally {
      setRescheduling(false);
    }
  };

  const handleCreateTask = async (e) => {
    e.preventDefault();
    if (!taskForm.title.trim()) return;
    try {
      await apiRequest('/planner/tasks', {
        method: 'POST',
        body: JSON.stringify({
          ...taskForm,
          title: taskForm.title.trim(),
          scheduled_time: taskForm.scheduled_time ? `${taskForm.scheduled_time}:00` : null
        })
      });
      setAddTaskModal(false);
      setTaskForm((prev) => ({ ...prev, title: '' }));
      showToast('Study task created successfully!', 'success');
      loadPlannerData();
    } catch (err) {
      if (err.message && err.message.includes('Daily study budget exceeded')) {
        const confirmExceed = window.confirm(`${err.message}\n\nDo you want to override your daily study limit for this task?`);
        if (confirmExceed) {
          try {
            await apiRequest('/planner/tasks', {
              method: 'POST',
              body: JSON.stringify({
                ...taskForm,
                title: taskForm.title.trim(),
                scheduled_time: taskForm.scheduled_time ? `${taskForm.scheduled_time}:00` : null,
                confirm_budget_override: true
              })
            });
            setAddTaskModal(false);
            setTaskForm((prev) => ({ ...prev, title: '' }));
            showToast('Study task created with limit override!', 'success');
            loadPlannerData();
            return;
          } catch (e2) {
            showToast(`Error: ${e2.message}`, 'error');
            return;
          }
        }
      }
      showToast(`Error creating task: ${err.message}`, 'error');
    }
  };

  const handleToggleTask = async (taskId, currentStatus, taskObj = null) => {
    if (!currentStatus) {
      // Completing task: prompt for optional feedback
      const task = taskObj || tasks.find((t) => t.id === taskId);
      if (task) {
        setCompletingTask({
          ...task,
          actualMinutes: task.estimated_minutes || 30
        });
        setCompletionFeedback(null);
        return;
      }
    }
    try {
      await apiRequest(`/planner/tasks/${taskId}`, {
        method: 'PUT',
        body: JSON.stringify({ is_completed: !currentStatus })
      });
      loadPlannerData();
    } catch (err) {
      console.error(err);
      showToast(`Failed to update task: ${err.message}`, 'error');
    }
  };

  const handleSubmitTaskFeedback = async (skipFeedback = false) => {
    if (!completingTask) return;

    // If feedback is need_more_time and user pressed Save & Complete, trigger Add to My Plan
    if (!skipFeedback && completionFeedback === 'need_more_time') {
      await handleAddToPlan('auto');
      return;
    }

    try {
      const actualMins = parseInt(completingTask.actualMinutes, 10) || completingTask.plannedMinutes || completingTask.estimated_minutes || 30;
      const feedbackVal = skipFeedback ? null : (completionFeedback || null);

      await apiRequest(`/planner/tasks/${completingTask.id}/feedback`, {
        method: 'POST',
        body: JSON.stringify({
          feedback: feedbackVal,
          actual_minutes: actualMins
        })
      });

      const plannedMins = completingTask.plannedMinutes || completingTask.estimated_minutes || 45;
      setCompletingTask(null);
      setCompletionFeedback(null);
      setNmtStep(null);
      await loadPlannerData();

      const msg = `Study completed ✓ (Planned: ${plannedMins} min, Actual: ${actualMins} min)`;
      showToast(msg, 'success');
    } catch (err) {
      showToast(`Error completing task: ${err.message}`, 'error');
    }
  };

  const formatDurationDisplay = (mins) => {
    const m = parseInt(mins, 10) || 0;
    if (m < 60) return `${m} min`;
    const h = Math.floor(m / 60);
    const rem = m % 60;
    return rem === 0 ? `${h} hr` : `${h} hr ${rem} min`;
  };

  const getFormattedStopTime = (additionalMinutes) => {
    const target = new Date(Date.now() + (additionalMinutes || 30) * 60000);
    return target.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  };

  const checkContinueConflictForMinutes = (additionalMinutes) => {
    const now = new Date();
    const nowMinutes = now.getHours() * 60 + now.getMinutes();
    const targetMinutes = nowMinutes + (additionalMinutes || 30);

    const todayStr = now.toISOString().split('T')[0];
    const todayTasks = tasks.filter((t) =>
      t.scheduled_date === todayStr &&
      !t.is_completed &&
      t.id !== completingTask?.id &&
      t.scheduled_time
    );

    for (const t of todayTasks) {
      const [th, tm] = t.scheduled_time.split(':').map(Number);
      const taskStartMin = th * 60 + tm;
      if (taskStartMin >= nowMinutes && taskStartMin < targetMinutes) {
        return t;
      }
    }
    return null;
  };

  const getContinueMinutes = (endTimeStr) => {
    if (!endTimeStr) return 30;
    const [h, m] = endTimeStr.split(':').map(Number);
    const now = new Date();
    const target = new Date();
    target.setHours(h, m, 0, 0);
    if (target <= now) {
      target.setDate(target.getDate() + 1);
    }
    const diffMins = Math.max(5, Math.round((target - now) / 60000));
    return diffMins;
  };

  const updateContinueDuration = (mins) => {
    const clamped = Math.max(5, Math.min(240, mins));
    setContinueDurationMinutes(clamped);
    const target = new Date(Date.now() + clamped * 60000);
    const hh = String(target.getHours()).padStart(2, '0');
    const mm = String(target.getMinutes()).padStart(2, '0');
    setContinueEndTime(`${hh}:${mm}`);
    setContinueConflict(checkContinueConflictForMinutes(clamped));
  };

  const handleSpecificTimeChange = (timeStr) => {
    setContinueEndTime(timeStr);
    const diffMins = getContinueMinutes(timeStr);
    setContinueDurationMinutes(diffMins);
    setContinueConflict(checkContinueConflictForMinutes(diffMins));
  };

  const checkContinueConflict = (endTimeStr) => {
    if (!endTimeStr) return null;
    const [h, m] = endTimeStr.split(':').map(Number);
    const targetMinutes = h * 60 + m;
    const now = new Date();
    const nowMinutes = now.getHours() * 60 + now.getMinutes();

    const todayStr = new Date().toISOString().split('T')[0];
    const todayTasks = tasks.filter((t) =>
      t.scheduled_date === todayStr &&
      !t.is_completed &&
      t.id !== completingTask?.id &&
      t.scheduled_time
    );

    for (const t of todayTasks) {
      const [th, tm] = t.scheduled_time.split(':').map(Number);
      const taskStartMin = th * 60 + tm;
      if (taskStartMin >= nowMinutes && taskStartMin < targetMinutes) {
        return t;
      }
    }
    return null;
  };

  const handleConfirmContinueNow = () => {
    if (!completingTask) return;
    const accumSecs = (completingTask.actualMinutes || 30) * 60;
    const sessionObj = {
      task: completingTask,
      plannedMinutes: completingTask.plannedMinutes || completingTask.estimated_minutes || 45,
      accumulatedSeconds: accumSecs,
      lastStartedAt: Date.now(),
      isRunning: true,
      persistedFeedback: 'need_more_time'
    };
    setFocusSession(sessionObj);
    try {
      localStorage.setItem('medpilot_active_study_session', JSON.stringify(sessionObj));
    } catch (e) {
      console.error(e);
    }
    setCompletingTask(null);
    setCompletionFeedback(null);
    setNmtStep(null);
    setContinueConflict(null);
    showToast(`Continuing session for ${completingTask.title} (+${continueDurationMinutes}m target)`, 'info');
  };

  const handleMoveConflictingTask = async () => {
    if (!continueConflict) return;
    try {
      await apiRequest(`/planner/tasks/${continueConflict.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          scheduled_time: continueEndTime ? `${continueEndTime}:00` : null
        })
      });
      showToast(`Moved ${continueConflict.title} to ${continueEndTime}`, 'success');
      setContinueConflict(null);
      loadPlannerData();
    } catch (e) {
      showToast(`Error moving task: ${e.message}`, 'error');
    }
  };

  const handleShortenConflictingTask = async () => {
    if (!continueConflict) return;
    try {
      const curDur = continueConflict.estimated_minutes || 45;
      const newDur = Math.max(15, curDur - 15);
      await apiRequest(`/planner/tasks/${continueConflict.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          estimated_minutes: newDur
        })
      });
      showToast(`Shortened ${continueConflict.title} to ${newDur} min`, 'success');
      setContinueConflict(null);
      loadPlannerData();
    } catch (e) {
      showToast(`Error shortening task: ${e.message}`, 'error');
    }
  };

  const handleAddToPlan = async (strategy = 'auto', extraOpts = {}) => {
    if (!completingTask) return;
    try {
      setReplanLoading(true);
      const actualMins = parseInt(completingTask.actualMinutes, 10) || completingTask.plannedMinutes || completingTask.estimated_minutes || 30;
      const payload = {
        extra_minutes: extraOpts.extra_minutes || addToPlanMinutes || 45,
        actual_minutes: actualMins,
        strategy,
        ...extraOpts
      };
      const res = await apiRequest(`/planner/tasks/${completingTask.id}/replan-need-more-time`, {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      if (res.success) {
        setCompletingTask(null);
        setCompletionFeedback(null);
        setNmtStep(null);
        setNoSpaceData(null);
        setSelectedMoveTaskId('');
        setShowMoveTaskPicker(false);
        await loadPlannerData();
        showToast(res.explanation || 'Rebalanced schedule successfully!', 'success', 6000);
      } else if (res.requires_user_action) {
        setNoSpaceData(res);
        setNmtStep('no_space');
        setShowMoveTaskPicker(false);
        if (res.tomorrow_tasks && res.tomorrow_tasks.length > 0) {
          setSelectedMoveTaskId(res.tomorrow_tasks[0].id);
        }
      }
    } catch (err) {
      showToast(`Error re-planning: ${err.message}`, 'error');
    } finally {
      setReplanLoading(false);
    }
  };

  const handleHandleLater = async () => {
    await handleAddToPlan('handle_later');
  };

  // Close ⋯ dropdown on click outside
  useEffect(() => {
    const handleClickOutside = () => setOpenMenuTaskId(null);
    if (openMenuTaskId) {
      window.addEventListener('click', handleClickOutside);
    }
    return () => window.removeEventListener('click', handleClickOutside);
  }, [openMenuTaskId]);

  const handleOpenEditModal = (task, e) => {
    e?.stopPropagation();
    setOpenMenuTaskId(null);
    setEditingTask(task);
    setEditForm({
      title: task.title || '',
      subject_id: task.subject_id || (subjects[0]?.id || ''),
      estimated_minutes: task.estimated_minutes || 45,
      priority: task.priority || 'medium',
      description: task.description || ''
    });
  };

  const handleSaveEditTask = async (e) => {
    e.preventDefault();
    if (!editingTask) return;
    const payload = {
      title: editForm.title.trim(),
      subject_id: editForm.subject_id || null,
      estimated_minutes: parseInt(editForm.estimated_minutes, 10) || 45,
      priority: editForm.priority,
      description: editForm.description.trim()
    };
    try {
      const updated = await apiRequest(`/planner/tasks/${editingTask.id}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
      });
      // Update UI immediately
      setTasks((prev) =>
        prev.map((t) => (t.id === editingTask.id ? { ...t, ...updated } : t))
      );
      if (selectedTaskDetail?.id === editingTask.id) {
        setSelectedTaskDetail((prev) => (prev ? { ...prev, ...updated } : null));
      }
      setEditingTask(null);
      showToast('Task updated successfully!', 'success');
      loadPlannerData();
    } catch (err) {
      if (err.message && err.message.includes('Daily study budget exceeded')) {
        const confirmExceed = window.confirm(`${err.message}\n\nDo you want to override your daily study limit for this change?`);
        if (confirmExceed) {
          try {
            const updated = await apiRequest(`/planner/tasks/${editingTask.id}`, {
              method: 'PUT',
              body: JSON.stringify({ ...payload, confirm_budget_override: true })
            });
            setTasks((prev) =>
              prev.map((t) => (t.id === editingTask.id ? { ...t, ...updated } : t))
            );
            if (selectedTaskDetail?.id === editingTask.id) {
              setSelectedTaskDetail((prev) => (prev ? { ...prev, ...updated } : null));
            }
            setEditingTask(null);
            showToast('Task updated with limit override!', 'success');
            loadPlannerData();
            return;
          } catch (e2) {
            showToast(`Error: ${e2.message}`, 'error');
            return;
          }
        }
      }
      showToast(`Error updating task: ${err.message}`, 'error');
    }
  };

  const handleOpenRescheduleModal = (task, e) => {
    e?.stopPropagation();
    setOpenMenuTaskId(null);
    setReschedulingTask(task);
    const tomorrow = new Date(Date.now() + 86400000).toISOString().split('T')[0];
    setRescheduleDate(task.scheduled_date || tomorrow);
  };

  const handleSaveRescheduleTask = async (newDate) => {
    const targetDate = newDate || rescheduleDate;
    if (!reschedulingTask || !targetDate) return;
    try {
      const updated = await apiRequest(`/planner/tasks/${reschedulingTask.id}`, {
        method: 'PUT',
        body: JSON.stringify({ scheduled_date: targetDate })
      });
      // Update UI immediately (same task ID, updated scheduled_date)
      setTasks((prev) =>
        prev.map((t) =>
          t.id === reschedulingTask.id ? { ...t, ...updated, scheduled_date: targetDate } : t
        )
      );
      if (selectedTaskDetail?.id === reschedulingTask.id) {
        setSelectedTaskDetail((prev) =>
          prev ? { ...prev, ...updated, scheduled_date: targetDate } : null
        );
      }
      const label = formatDateLabel ? formatDateLabel(targetDate) : targetDate;
      setReschedulingTask(null);
      showToast(`Task rescheduled to ${label}`, 'success');
      loadPlannerData();
    } catch (err) {
      if (err.message && err.message.includes('Daily study budget exceeded')) {
        const confirmExceed = window.confirm(`${err.message}\n\nDo you want to override your daily study limit to reschedule this task?`);
        if (confirmExceed) {
          try {
            const updated = await apiRequest(`/planner/tasks/${reschedulingTask.id}`, {
              method: 'PUT',
              body: JSON.stringify({ scheduled_date: targetDate, confirm_budget_override: true })
            });
            setTasks((prev) =>
              prev.map((t) =>
                t.id === reschedulingTask.id ? { ...t, ...updated, scheduled_date: targetDate } : t
              )
            );
            if (selectedTaskDetail?.id === reschedulingTask.id) {
              setSelectedTaskDetail((prev) =>
                prev ? { ...prev, ...updated, scheduled_date: targetDate } : null
              );
            }
            const label = formatDateLabel ? formatDateLabel(targetDate) : targetDate;
            setReschedulingTask(null);
            showToast(`Task rescheduled to ${label} with limit override`, 'success');
            loadPlannerData();
            return;
          } catch (e2) {
            showToast(`Error: ${e2.message}`, 'error');
            return;
          }
        }
      }
      showToast(`Error rescheduling task: ${err.message}`, 'error');
    }
  };

  const handleOpenDeleteConfirm = (task, e) => {
    e?.stopPropagation();
    setOpenMenuTaskId(null);
    setDeletingTask(task);
  };

  const handleConfirmDelete = async () => {
    if (!deletingTask) return;
    const taskId = deletingTask.id;
    try {
      await apiRequest(`/planner/tasks/${taskId}`, { method: 'DELETE' });
      // Remove immediately from UI
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
      if (selectedTaskDetail?.id === taskId) {
        setSelectedTaskDetail(null);
      }
      setDeletingTask(null);
      showToast('Task removed from planner', 'success');
      loadPlannerData();
    } catch (err) {
      showToast(`Error deleting task: ${err.message}`, 'error');
    }
  };

  const handleDeleteTask = async (taskId) => {
    const taskToDelete = tasks.find((t) => t.id === taskId) || { id: taskId, title: 'this task' };
    handleOpenDeleteConfirm(taskToDelete);
  };

  const handleUpdateTopicStatus = async (topicId, studyStatus, snoozeUntil = null, skipReason = null) => {
    try {
      await apiRequest(`/planner/topics/${topicId}/status`, {
        method: 'PUT',
        body: JSON.stringify({
          study_status: studyStatus,
          snooze_until: snoozeUntil,
          skip_reason: skipReason
        })
      });
      setSnoozeModalTopic(null);
      setSkipModalTopic(null);
      const msg =
        studyStatus === 'later'
          ? `Topic snoozed until ${snoozeUntil}`
          : studyStatus === 'skip'
          ? 'Topic excluded from automated study plans'
          : 'Topic marked active for study plan';
      showToast(msg, 'success');
      loadPlannerData();
    } catch (err) {
      showToast(`Failed to update topic: ${err.message}`, 'error');
    }
  };

  const handleRestoreTopic = async (topicId) => {
    try {
      await apiRequest(`/planner/topics/${topicId}/restore`, {
        method: 'POST'
      });
      showToast('Topic restored to active study catch-up', 'success');
      loadPlannerData();
    } catch (err) {
      showToast(`Failed to restore topic: ${err.message}`, 'error');
    }
  };

  const formatDateLabel = (dateStr) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr.includes('T') ? dateStr : `${dateStr}T00:00:00`);
      return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
    } catch {
      return dateStr;
    }
  };

  const formatMissedDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr.includes('T') ? dateStr : `${dateStr}T00:00:00`);
      const day = d.getDate();
      const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec'];
      return `${day} ${monthNames[d.getMonth()]}`;
    } catch {
      return dateStr;
    }
  };

  const getCalculatedSnoozeDate = () => {
    const d = new Date();
    if (snoozePreset === 'tomorrow') {
      d.setDate(d.getDate() + 1);
      return d.toISOString().split('T')[0];
    }
    if (snoozePreset === '3_days') {
      d.setDate(d.getDate() + 3);
      return d.toISOString().split('T')[0];
    }
    if (snoozePreset === '1_week') {
      d.setDate(d.getDate() + 7);
      return d.toISOString().split('T')[0];
    }
    return customSnoozeDate || d.toISOString().split('T')[0];
  };

  const handleGenerateAiPlan = async (e, overrideOpts = {}) => {
    if (e && e.preventDefault) e.preventDefault();
    setAiGenerating(true);
    try {
      const today = new Date();
      const planDays = overrideOpts.plan_days ?? aiPlanForm.plan_days ?? 2;
      const endDay = new Date(today);
      endDay.setDate(today.getDate() + planDays);

      const payload = {
        plan_days: planDays,
        study_hours: overrideOpts.study_hours ?? (parseInt(aiPlanForm.study_hours) || 0),
        study_minutes: overrideOpts.study_minutes ?? (parseInt(aiPlanForm.study_minutes) || 0),
        subject_mode: overrideOpts.subject_mode ?? aiPlanForm.subject_mode,
        subject_ids: (overrideOpts.subject_mode ?? aiPlanForm.subject_mode) === 'choose'
          ? (overrideOpts.subject_ids ?? aiPlanForm.subject_ids)
          : (showAllSubjects ? subjects.map((s) => s.id) : currentSemesterSubjects.map((s) => s.id)),
        planning_style: overrideOpts.planning_style ?? aiPlanForm.planning_style,
        until_next_exam: overrideOpts.until_next_exam ?? aiPlanForm.until_next_exam,
        quick_review_mode: overrideOpts.quick_review_mode ?? aiPlanForm.quick_review_mode,
        start_date: today.toISOString().split('T')[0],
        end_date: endDay.toISOString().split('T')[0]
      };

      const res = await apiRequest('/planner/generate', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      if (res.total_tasks_created > 0) {
        showToast(
          res.message || `Scheduled ${res.total_tasks_created} study tasks over the next ${planDays} days!`,
          'success'
        );
        setAiPlanModal(false);
        loadPlannerData();
      } else {
        showToast(
          res.message || "I need something to plan. Add an exam, topic, or study task first.",
          'info',
          6000
        );
      }
    } catch (err) {
      showToast(`AI Study Plan error: ${err.message}`, 'error');
    } finally {
      setAiGenerating(false);
    }
  };

  const todayStr = new Date().toISOString().split('T')[0];

  // Group tasks into Today's plan, Upcoming, and Completed
  const completedTasks = tasks.filter((t) => t.is_completed);
  const uncompletedTasks = tasks.filter((t) => !t.is_completed);
  const rawTodayTasks = uncompletedTasks.filter((t) => t.scheduled_date === todayStr);
  const upcomingTasks = uncompletedTasks.filter((t) => t.scheduled_date !== todayStr);
  const allTodayTasks = tasks.filter((t) => t.scheduled_date === todayStr);
  const isTodayAllCompleted = allTodayTasks.length > 0 && rawTodayTasks.length === 0;

  const encouragingLines = [
    "Today's plan complete ✓",
    "Strong work today. You stayed consistent.",
    "Small steps add up.",
    "Progress made. Rest well.",
    "You showed up for your plan today."
  ];
  const celebrationLine = encouragingLines[allTodayTasks.length % encouragingLines.length];

  // Adapt today's task ordering based on student wellbeing input
  const todayTasks = [...rawTodayTasks].sort((a, b) => {
    if (recommendation?.mood === 'stressful') {
      const pWeight = { high: 3, medium: 2, low: 1 };
      return (pWeight[b.priority] || 2) - (pWeight[a.priority] || 2);
    }
    if (recommendation?.mood === 'tired') {
      return (a.estimated_minutes || 45) - (b.estimated_minutes || 45);
    }
    if (recommendation?.mood === 'great') {
      const pWeight = { high: 3, medium: 2, low: 1 };
      return (pWeight[b.priority] || 2) - (pWeight[a.priority] || 2);
    }
    return 0;
  });

  const currentTabTasks =
    activeTab === 'today'
      ? todayTasks
      : activeTab === 'upcoming'
      ? upcomingTasks
      : completedTasks;

  const upcomingExams = exams
    .filter((e) => e.exam_date && e.exam_date >= todayStr)
    .sort((a, b) => a.exam_date.localeCompare(b.exam_date));
  const nextExam = upcomingExams[0] || null;
  const daysUntilNextExam = nextExam
    ? Math.max(1, Math.ceil((new Date(nextExam.exam_date + 'T00:00:00') - new Date(todayStr + 'T00:00:00')) / (1000 * 60 * 60 * 24)))
    : null;

  const currentPlanDays = aiPlanForm.until_next_exam && daysUntilNextExam
    ? daysUntilNextExam
    : (parseInt(aiPlanForm.plan_days, 10) || 1);

  const dailyMinutes = (parseInt(aiPlanForm.study_hours, 10) || 0) * 60 + (parseInt(aiPlanForm.study_minutes, 10) || 0);
  const totalAvailableMinutes = currentPlanDays * dailyMinutes;

  const activeSubjectCount = aiPlanForm.subject_mode === 'choose'
    ? (aiPlanForm.subject_ids.length > 0 ? aiPlanForm.subject_ids.length : 1)
    : (showAllSubjects
        ? (subjects.length > 0 ? subjects.length : 1)
        : (currentSemesterSubjects.length > 0 ? currentSemesterSubjects.length : (subjects.length > 0 ? subjects.length : 1)));

  const candidateTopicsCount = Math.max(
    activeSubjectCount,
    (exams?.reduce((acc, e) => acc + (e.important_topics?.length || 1), 0) || 0) +
    (missedClasses?.reduce((acc, c) => acc + (c.topics?.length || 1), 0) || 0)
  );
  const neededMinutes = candidateTopicsCount * 35;
  const availableHours = totalAvailableMinutes / 60;
  const availableHoursText = totalAvailableMinutes >= 60
    ? `${availableHours % 1 === 0 ? availableHours : availableHours.toFixed(1)} hours`
    : `${totalAvailableMinutes} minutes`;
  const neededHours = neededMinutes / 60;
  const neededHoursText = `${neededHours % 1 === 0 ? neededHours : neededHours.toFixed(1)} hours`;
  const isTimeTight = candidateTopicsCount >= 2 && totalAvailableMinutes > 0 && totalAvailableMinutes < neededMinutes * 0.70;

  const formatTimer = (totalSeconds) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins < 10 ? '0' : ''}${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-16">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#E7EAF0] pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#26313F] flex items-center gap-2.5">
            <span className="p-2 rounded-xl bg-[#B7D4F4]/40 text-[#1E3A8A]">
              <BookOpen className="w-5 h-5 stroke-[2.2]" />
            </span>
            <span>Study Planner</span>
          </h1>
          <p className="text-xs text-[#6E7785] mt-1">
            Refined, lightweight study goals tailored to your medical curriculum.
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={() => setAiPlanModal(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white hover:bg-[#F2F5F8] text-[#26313F] border border-[#E7EAF0] text-xs font-semibold shadow-soft transition-all cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5 text-[#72C9BE]" />
            <span>Generate Plan</span>
          </button>

          <button
            onClick={() => setAddTaskModal(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#72C9BE] hover:bg-[#5db8ad] text-[#13443e] text-xs font-semibold shadow-sm transition-all cursor-pointer active:scale-98"
          >
            <Plus className="w-4 h-4 stroke-[2.5]" />
            <span>+ Add Task</span>
          </button>
        </div>
      </div>

      {/* Workload Recommendation Banner */}
      {recommendation && (
        <div className="bg-white border border-[#E7EAF0] rounded-2xl p-5 sm:p-6 shadow-card space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E7EAF0] pb-3.5">
            <div className="flex items-center gap-2.5 flex-wrap">
              {/* Mood pill */}
              {recommendation.mood === 'great' && (
                <span className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1 rounded-full bg-[#CFEDE7] text-[#1A4B43]">
                  <span>😄</span> Great Feeling
                </span>
              )}
              {recommendation.mood === 'good' && (
                <span className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1 rounded-full bg-[#B7D4F4]/50 text-[#1E3A8A]">
                  <span>🙂</span> Good Momentum
                </span>
              )}
              {recommendation.mood === 'okay' && (
                <span className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1 rounded-full bg-[#F2F5F8] text-[#26313F] border border-[#E7EAF0]">
                  <span>😐</span> Balanced Pace
                </span>
              )}
              {recommendation.mood === 'tired' && (
                <span className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1 rounded-full bg-[#F3DFAB]/50 text-[#6B4E17]">
                  <span>😴</span> Low Energy
                </span>
              )}
              {recommendation.mood === 'stressful' && (
                <span className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1 rounded-full bg-[#EABFC5]/50 text-[#69242E]">
                  <span>😣</span> High Stress
                </span>
              )}
              {!recommendation.mood && (
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full bg-[#F2F5F8] text-[#6E7785]">
                  Standard Pace
                </span>
              )}

              {/* Workload mode chip */}
              <span className="text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-lg bg-slate-100 text-slate-700">
                {recommendation.workload_mode === 'high-focus' && 'High-Focus Plan'}
                {recommendation.workload_mode === 'normal' && 'Normal Workload'}
                {recommendation.workload_mode === 'paced' && 'Shorter Study Blocks'}
                {recommendation.workload_mode === 'light-revision' && 'Light Revision & Notes'}
                {recommendation.workload_mode === 'essential-only' && 'Essential Tasks Only'}
              </span>

              {/* Suggested block length */}
              <span className="text-xs font-semibold text-slate-500 flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-[#72C9BE]" />
                <span>{recommendation.suggested_block_minutes}m target blocks</span>
              </span>
            </div>

            {/* Quick link if check-in is pending */}
            {recommendation.checkin_status === 'pending' && (
              <a
                href="/habits"
                className="text-xs font-semibold text-[#1A4B43] hover:underline flex items-center gap-1"
              >
                <span>Check in for today in Routine & Wellbeing</span>
                <ArrowRight className="w-3 h-3" />
              </a>
            )}
          </div>

          {/* Headline */}
          <div>
            <h3 className="text-sm font-bold text-slate-800 tracking-tight">
              {recommendation.headline}
            </h3>
          </div>

          {/* Urgent Exam Alert if approaching */}
          {recommendation.urgent_exam_alert && (
            <div className="p-3 rounded-xl bg-[#F3DFAB]/40 border border-[#F3DFAB] flex items-center gap-2.5 text-xs text-[#6B4E17] font-medium">
              <AlertCircle className="w-4 h-4 flex-shrink-0 text-[#6B4E17]" />
              <span>{recommendation.urgent_exam_alert}</span>
            </div>
          )}

          {/* Guidance Points */}
          <div className="space-y-1.5">
            {recommendation.guidance.map((point, idx) => (
              <div key={idx} className="flex items-start gap-2 text-xs text-slate-600 leading-relaxed">
                <span className="w-1.5 h-1.5 rounded-full bg-[#72C9BE] mt-1.5 flex-shrink-0" />
                <span>{point}</span>
              </div>
            ))}
          </div>

          {/* Reschedule optional tasks action (for stressful/tired) */}
          {(recommendation.mood === 'stressful' || recommendation.mood === 'tired') && recommendation.reschedule_candidates_count > 0 && (
            <div className="pt-2 border-t border-[#E7EAF0] flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#F7F8FC] p-3 rounded-xl">
              <div className="text-xs text-slate-600">
                <span className="font-semibold text-slate-800">Lighten tonight's load:</span>{' '}
                <span>You have {recommendation.reschedule_candidates_count} optional / non-urgent task(s) scheduled for today.</span>
              </div>
              <button
                type="button"
                disabled={rescheduling}
                onClick={handleRescheduleOptional}
                className="text-xs font-semibold px-3.5 py-1.5 rounded-xl bg-white hover:bg-slate-50 text-slate-800 border border-[#E7EAF0] shadow-xs transition-all cursor-pointer whitespace-nowrap self-start sm:self-auto"
              >
                {rescheduling ? 'Moving...' : 'Reschedule optional to tomorrow'}
              </button>
            </div>
          )}

          {/* Reschedule feedback notice */}
          {rescheduleNotice && (
            <div className="p-2.5 rounded-xl bg-[#CADFCB]/40 text-[#1C4323] text-xs font-semibold flex items-center gap-2">
              <Check className="w-4 h-4 stroke-[3]" />
              <span>{rescheduleNotice}</span>
            </div>
          )}

          {/* Educational Pacing Disclaimer */}
          <div className="pt-1 flex items-center gap-1.5 text-[11px] text-slate-400">
            <ShieldCheck className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            <span>{recommendation.disclaimer}</span>
          </div>
        </div>
      )}

      {/* Missed Class Topics & Catch-up Backlog */}
      {missedClasses && missedClasses.length > 0 && (
        <div className="bg-white rounded-2xl border border-[#E7EAF0] shadow-soft overflow-hidden">
          <div className="p-4 flex items-center justify-between gap-3 border-b border-[#E7EAF0]/60 bg-[#FAFBFD]">
            <div className="flex items-center gap-3">
              <span className="p-2 rounded-xl bg-[#FEF3C7]/70 text-[#92400E]">
                <Calendar className="w-4 h-4 stroke-[2.2]" />
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-[#26313F]">Missed Class Topics</h3>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#FEF3C7] text-[#92400E] border border-[#FDE68A]">
                    {missedClasses.reduce((acc, c) => acc + (c.topics?.length || 0), 0)} Topics Recorded
                  </span>
                </div>
                <p className="text-xs text-[#6E7785] mt-0.5">
                  Catch-up topics from classes you missed. Control which ones are added to your plan.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setMissedClassesOpen(!missedClassesOpen)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-[#4F5969] bg-white border border-[#E7EAF0] hover:bg-[#F2F5F8] transition-colors cursor-pointer shadow-2xs"
            >
              <span>{missedClassesOpen ? 'Hide' : 'Review Topics'}</span>
              <ChevronDown className={`w-3.5 h-3.5 transition-transform ${missedClassesOpen ? 'rotate-180' : ''}`} />
            </button>
          </div>

          {missedClassesOpen && (
            <div className="p-4 space-y-4">
              {missedClasses.map((item) => {
                const totalTopics = item.topics?.length || 0;
                const subjName = item.subject?.name || item.subject_name || 'Subject';
                const subjColor = item.subject?.color || item.subject_color || '#72C9BE';
                const formattedDate = formatMissedDate(item.date || item.class_date);

                return (
                  <div key={item.occurrence_id} className="p-4 rounded-2xl bg-[#F8FAFC] border border-[#E2E8F0]/80 space-y-3 shadow-2xs">
                    <div className="flex items-center justify-between gap-2 flex-wrap border-b border-[#E2E8F0]/60 pb-2.5">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-white border border-[#E2E8F0] shadow-2xs">
                          <span
                            className="w-2.5 h-2.5 rounded-full shrink-0"
                            style={{ backgroundColor: subjColor }}
                          />
                          <span className="text-xs font-bold text-[#1E293B]">
                            {subjName}
                          </span>
                        </div>
                        <span className="text-xs font-medium text-[#64748B]">
                          Missed on {formattedDate}
                        </span>
                      </div>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-[#FEE2E2] text-[#991B1B] border border-[#FECACA]">
                        Absent
                      </span>
                    </div>

                    {totalTopics === 0 ? (
                      <p className="text-xs text-[#94A3B8] italic py-1">
                        No lecture topics recorded for this missed class yet. (You can add topics via Timetable).
                      </p>
                    ) : (
                      <div className="space-y-2.5">
                        {item.topics.map((topic) => {
                          const status = topic.study_status || 'study';
                          return (
                            <div
                              key={topic.id}
                              className="p-3.5 rounded-xl bg-white border border-[#E2E8F0] flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs"
                            >
                              <div className="min-w-0 space-y-1">
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  <span className="text-xs font-semibold text-[#64748B]">Topic:</span>
                                  <span className="text-xs font-bold text-[#1E293B] break-words">
                                    {topic.title || topic.name}
                                  </span>
                                </div>
                                {topic.description && (
                                  <p className="text-[11px] text-[#6E7785] line-clamp-2">
                                    {topic.description}
                                  </p>
                                )}
                                <div>
                                  {status === 'study' && (
                                    <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-md bg-[#CFEDE7]/60 text-[#13443e] border border-[#72C9BE]/30">
                                      <span className="w-1.5 h-1.5 rounded-full bg-[#72C9BE]" />
                                      Included in Study Plan
                                    </span>
                                  )}
                                  {status === 'later' && (
                                    <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-md bg-[#FEF3C7] text-[#92400E] border border-[#FDE68A]">
                                      <span className="w-1.5 h-1.5 rounded-full bg-[#F59E0B]" />
                                      Postponed until {formatMissedDate(topic.snooze_until) || formatDateLabel(topic.snooze_until)}
                                    </span>
                                  )}
                                  {status === 'skip' && (
                                    <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-md bg-[#F1F5F9] text-[#64748B] border border-[#CBD5E1]">
                                      <span className="w-1.5 h-1.5 rounded-full bg-[#94A3B8]" />
                                      Skipped from Plan {topic.skip_reason === 'already_know' ? '(Already know this)' : topic.skip_reason === 'dont_suggest' ? '(Do not suggest)' : ''}
                                    </span>
                                  )}
                                </div>
                              </div>

                              <div className="flex items-center gap-1.5 shrink-0 self-end sm:self-center pt-1 sm:pt-0">
                                <button
                                  type="button"
                                  onClick={() => handleUpdateTopicStatus(topic.id, 'study')}
                                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                                    status === 'study'
                                      ? 'bg-[#CFEDE7] text-[#13443e] border border-[#72C9BE]/50 shadow-2xs'
                                      : 'bg-[#F8FAFC] text-[#334155] border border-[#E2E8F0] hover:bg-[#CFEDE7]/50 hover:text-[#13443e]'
                                  }`}
                                  title="Include topic in study planning"
                                >
                                  Study
                                </button>

                                <button
                                  type="button"
                                  onClick={() =>
                                    setSnoozeModalTopic({
                                      ...topic,
                                      subjectName: subjName,
                                      occurrenceDate: item.date || item.class_date
                                    })
                                  }
                                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                                    status === 'later'
                                      ? 'bg-[#FEF3C7] text-[#92400E] border border-[#FDE68A] shadow-2xs'
                                      : 'bg-[#F8FAFC] text-[#334155] border border-[#E2E8F0] hover:bg-[#FEF3C7]/60 hover:text-[#92400E]'
                                  }`}
                                  title="Snooze topic until tomorrow / 3 days / 1 week / custom date"
                                >
                                  Later
                                </button>

                                {status === 'skip' ? (
                                  <button
                                    type="button"
                                    onClick={() => handleRestoreTopic(topic.id)}
                                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-[#EFF6FF] border border-[#BFDBFE] text-xs font-bold text-[#1D4ED8] hover:bg-[#DBEAFE] transition-colors cursor-pointer"
                                    title="Restore skipped topic to planning"
                                  >
                                    <RotateCcw className="w-3.5 h-3.5" />
                                    <span>Restore</span>
                                  </button>
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setSkipModalTopic({
                                        ...topic,
                                        subjectName: subjName,
                                        occurrenceDate: item.date || item.class_date
                                      })
                                    }
                                    className="px-3 py-1.5 rounded-xl text-xs font-bold bg-[#F8FAFC] text-[#64748B] border border-[#E2E8F0] hover:bg-[#FEE2E2] hover:text-[#991B1B] hover:border-[#FCA5A5] transition-colors cursor-pointer"
                                    title="Exclude topic from automatic planning"
                                  >
                                    Skip
                                  </button>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Exam Details Changed Banner */}
      {examSyncNeeded && (
        <div className="p-4 rounded-2xl bg-[#E8F6F4] border border-[#72C9BE]/50 text-[#13443e] flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs animate-in fade-in duration-150">
          <div className="flex items-start sm:items-center gap-2.5">
            <div className="p-1.5 rounded-xl bg-[#72C9BE] text-[#13443e] shrink-0 mt-0.5 sm:mt-0">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-[#13443e]">
                Your exam details changed. Update your remaining study plan?
              </h4>
              <p className="text-[11px] text-[#1A4B43] mt-0.5">
                Only unfinished and future study tasks will be updated to match the latest exam syllabus and dates.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
            <button
              type="button"
              disabled={syncingExams}
              onClick={handleSyncExams}
              className="px-3 py-1.5 rounded-xl bg-[#72C9BE] hover:bg-[#5db8ad] text-[#13443e] text-xs font-bold transition-all shadow-xs cursor-pointer disabled:opacity-50"
            >
              {syncingExams ? 'Updating...' : 'Update Plan'}
            </button>
            <button
              type="button"
              onClick={() => setExamSyncNeeded(false)}
              className="px-3 py-1.5 rounded-xl bg-white hover:bg-[#F2F5F8] text-[#6E7785] text-xs font-semibold border border-[#E7EAF0] transition-colors cursor-pointer"
            >
              Not Now
            </button>
          </div>
        </div>
      )}

      {/* Tabs: Today's plan, Upcoming, Completed */}
      <div className="flex items-center gap-2 border-b border-[#E7EAF0] pb-2">
        {[
          { id: 'today', label: "Today's plan", count: todayTasks.length },
          { id: 'upcoming', label: 'Upcoming', count: upcomingTasks.length },
          { id: 'completed', label: 'Completed', count: completedTasks.length },
        ].map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all ${
                isActive
                  ? 'bg-[#CFEDE7] text-[#1A4B43]'
                  : 'text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8]'
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                  isActive ? 'bg-white text-[#1A4B43]' : 'bg-[#E7EAF0] text-[#6E7785]'
                }`}
              >
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Lightweight Tasks List */}
      <div className="space-y-2.5">
        {loading ? (
          <div className="p-8 text-center bg-white rounded-2xl border border-[#E7EAF0] shadow-soft">
            <div className="w-6 h-6 border-2 border-[#72C9BE] border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <p className="text-xs text-[#6E7785]">Loading study tasks...</p>
          </div>
        ) : currentTabTasks.length === 0 ? (
          activeTab === 'today' && isTodayAllCompleted ? (
            <div className="p-8 text-center bg-white rounded-3xl border border-[#72C9BE]/50 shadow-soft space-y-4 animate-in fade-in zoom-in-95 duration-200">
              <div className="w-14 h-14 rounded-3xl bg-[#CFEDE7] text-[#13443e] flex items-center justify-center mx-auto shadow-sm">
                <CheckCircle2 className="w-7 h-7 stroke-[2.5]" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-bold text-[#13443e]">
                  {celebrationLine}
                </h3>
                <p className="text-xs text-[#4B5563] max-w-sm mx-auto leading-relaxed">
                  All {allTodayTasks.length} planned {allTodayTasks.length === 1 ? 'task' : 'tasks'} completed today ({allTodayTasks.reduce((acc, t) => acc + (t.actual_minutes || t.estimated_minutes || 0), 0)} min focused).
                </p>
              </div>
              <div className="flex items-center justify-center gap-2 pt-1 flex-wrap">
                <button
                  type="button"
                  onClick={() => setActiveTab('completed')}
                  className="px-4 py-2 rounded-xl bg-[#CFEDE7] hover:bg-[#b5e7dc] text-[#13443e] text-xs font-bold transition-all cursor-pointer shadow-xs"
                >
                  View Completed Tasks
                </button>
                <button
                  type="button"
                  onClick={() => setAiPlanModal(true)}
                  className="px-4 py-2 rounded-xl bg-white hover:bg-[#F2F5F8] text-[#26313F] border border-[#E7EAF0] text-xs font-semibold transition-all cursor-pointer shadow-2xs"
                >
                  Plan Next Days
                </button>
              </div>
            </div>
          ) : (
          <div className="p-10 text-center bg-white rounded-2xl border border-[#E7EAF0] shadow-soft space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-[#CFEDE7]/40 text-[#1A4B43] flex items-center justify-center mx-auto mb-1">
              <BookOpen className="w-6 h-6 text-[#1A4B43]" />
            </div>
            <h3 className="text-sm font-semibold text-[#26313F]">
              {activeTab === 'today'
                ? (exams.length === 0 && tasks.length === 0
                    ? "I need something to plan. Add an exam, topic, or study task first."
                    : "No study tasks scheduled for today")
                : activeTab === 'upcoming'
                ? "No upcoming study tasks"
                : "No completed tasks yet"}
            </h3>
            <p className="text-xs text-[#6E7785] max-w-sm mx-auto leading-relaxed">
              {activeTab === 'today'
                ? (exams.length === 0 && tasks.length === 0
                    ? "MedPilot builds grounded 7-day revision schedules from your upcoming exams, recorded lecture topics, and missed classes."
                    : "Add your first focused revision goal or generate an AI plan for the week.")
                : activeTab === 'upcoming'
                ? "Plan your next study milestones ahead of time or generate a 7-day schedule."
                : "Completed study sessions will appear here with logged focus time."}
            </p>
            <div className="flex items-center justify-center gap-2 pt-2 flex-wrap">
              <button
                onClick={() => setAddTaskModal(true)}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#72C9BE] hover:bg-[#5db8ad] text-[#13443e] text-xs font-semibold shadow-sm transition-all cursor-pointer active:scale-98"
              >
                <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
                <span>+ Add Study Task</span>
              </button>
              <button
                onClick={() => navigate('/exams')}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white hover:bg-[#F2F5F8] text-[#26313F] border border-[#E7EAF0] text-xs font-semibold transition-all cursor-pointer"
              >
                <BookOpen className="w-3.5 h-3.5 text-[#6E7785]" />
                <span>+ Add Exam</span>
              </button>
              <button
                onClick={() => setAiPlanModal(true)}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#B7D4F4]/30 hover:bg-[#B7D4F4]/50 text-[#1E3A8A] border border-[#B7D4F4]/60 text-xs font-semibold transition-all cursor-pointer"
              >
                <Sparkles className="w-3.5 h-3.5 text-[#2563EB]" />
                <span>Generate AI Plan</span>
              </button>
            </div>
          </div>
        )
      ) : (
        <div className="grid gap-2">
            {currentTabTasks.map((task) => {
              const isCompleted = task.is_completed;
              return (
                <div
                  key={task.id}
                  onClick={() => setSelectedTaskDetail(task)}
                  className={`p-4 rounded-2xl border transition-all bg-white shadow-soft flex items-center justify-between gap-3 cursor-pointer group hover:border-[#72C9BE]/50 ${
                    isCompleted ? 'opacity-70' : ''
                  } ${
                    focusSession?.task?.id === task.id ? 'border-[#72C9BE] ring-2 ring-[#72C9BE]/30 bg-[#CFEDE7]/10' : ''
                  }`}
                >
                  <div className="flex items-center gap-3.5 min-w-0">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleToggleTask(task.id, isCompleted, task);
                      }}
                      className={`w-5 h-5 rounded-lg border flex items-center justify-center transition-colors shrink-0 ${
                        isCompleted
                          ? 'bg-[#72C9BE] border-[#72C9BE] text-[#13443e]'
                          : 'border-[#D9DDE5] hover:border-[#72C9BE] bg-[#F7F8FC]'
                      }`}
                    >
                      {isCompleted && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                    </button>

                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        {task.subject && (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-[#F2F5F8] text-[#26313F]">
                            {task.subject.name}
                          </span>
                        )}

                        {/* Missed Class Badge */}
                        {task.missed_class_date && (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-[#FEF3C7] text-[#92400E] border border-[#FDE68A]">
                            Missed Class • {formatDateLabel(task.missed_class_date)}
                          </span>
                        )}

                        {/* Reason Badge */}
                        {task.reason && (
                          <span className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-[#EFF6FF] text-[#1D4ED8] border border-[#BFDBFE]/60 whitespace-pre-line text-left">
                            {task.reason}
                          </span>
                        )}

                        {/* Historical Feedback Badge */}
                        {task.feedback && (
                          <span className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-[#FEF3C7] text-[#92400E] border border-[#FDE68A]">
                            {task.feedback === 'hard' && '😓 Marked Hard'}
                            {task.feedback === 'need_more_time' && '⏳ Needed More Time'}
                            {task.feedback === 'easy' && '😄 Marked Easy'}
                            {task.feedback === 'okay' && '🙂 Marked Okay'}
                          </span>
                        )}

                        {/* Wellbeing-specific task badges */}
                        {activeTab === 'today' && !isCompleted && recommendation?.mood === 'stressful' && (
                          task.priority === 'high' ? (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-[#EABFC5]/40 text-[#69242E] border border-[#EABFC5]/60">
                              Essential
                            </span>
                          ) : (
                            <span className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-slate-100 text-slate-500">
                              Optional
                            </span>
                          )
                        )}

                        {activeTab === 'today' && !isCompleted && recommendation?.mood === 'tired' && (task.estimated_minutes || 45) <= 30 && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-[#F3DFAB]/40 text-[#6B4E17] border border-[#F3DFAB]/60">
                            Light Revision
                          </span>
                        )}

                        {activeTab === 'today' && !isCompleted && recommendation?.mood === 'great' && task.priority === 'high' && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-[#CFEDE7] text-[#1A4B43] border border-[#72C9BE]/30">
                            High Priority
                          </span>
                        )}

                        <h4
                          className={`text-sm font-semibold truncate ${
                            isCompleted ? 'line-through text-[#8E97A6]' : 'text-[#26313F]'
                          }`}
                        >
                          {task.title}
                        </h4>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-[#6E7785] mt-0.5 flex-wrap">
                        <span className="flex items-center gap-1 font-mono">
                          <Clock className="w-3 h-3 text-[#72C9BE]" />
                          {task.estimated_minutes || 45} min
                        </span>
                        {task.description && (
                          <>
                            <span>•</span>
                            <span className="text-[#4B5563] italic truncate max-w-sm">{task.description}</span>
                          </>
                        )}
                        {task.exam && !task.description?.toLowerCase().includes('exam') && (
                          <>
                            <span>•</span>
                            <span className="text-[#3C2D69] truncate">for {task.exam.name}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Clean Right Actions: [Start] and [⋯] Menu */}
                  <div className="flex items-center gap-2 shrink-0">
                    {!isCompleted ? (
                      focusSession?.task?.id === task.id ? (
                        <div className="flex items-center gap-1.5 sm:gap-2" onClick={(e) => e.stopPropagation()}>
                          {focusSession.isRunning ? (
                            <>
                              <span className="font-mono font-bold text-xs text-[#13443e] bg-[#CFEDE7]/70 px-2.5 py-1.5 rounded-xl border border-[#72C9BE]/50 tracking-wider shadow-2xs">
                                {formatTimer(getElapsedSeconds(focusSession))} elapsed
                              </span>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handlePauseResume();
                                }}
                                className="px-2.5 sm:px-3 py-1.5 rounded-xl bg-[#F2F5F8] hover:bg-[#E7EAF0] text-[#26313F] text-xs font-bold transition-all cursor-pointer shadow-2xs"
                              >
                                Pause
                              </button>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleFinishFocusSession();
                                }}
                                className="px-2.5 sm:px-3 py-1.5 rounded-xl bg-[#72C9BE] hover:bg-[#5db8ad] text-[#13443e] text-xs font-bold transition-all shadow-sm cursor-pointer"
                              >
                                Finish
                              </button>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleCancelSession();
                                }}
                                className="px-2 sm:px-2.5 py-1.5 rounded-xl bg-white hover:bg-rose-50 text-[#991B1B] hover:text-rose-700 text-xs font-semibold border border-[#E7EAF0] hover:border-rose-200 transition-all cursor-pointer"
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <>
                              <span className="font-mono font-bold text-xs text-[#92400E] bg-[#FEF3C7]/90 px-2.5 py-1.5 rounded-xl border border-[#FDE68A] tracking-wider shadow-2xs flex items-center gap-1">
                                <span>{formatTimer(getElapsedSeconds(focusSession))}</span>
                                <span className="font-medium text-[10px] text-[#B45309]">paused</span>
                              </span>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handlePauseResume();
                                }}
                                className="px-2.5 sm:px-3 py-1.5 rounded-xl bg-[#CFEDE7] hover:bg-[#b5e7dc] text-[#13443e] text-xs font-bold transition-all cursor-pointer shadow-2xs"
                              >
                                Resume
                              </button>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleFinishFocusSession();
                                }}
                                className="px-2.5 sm:px-3 py-1.5 rounded-xl bg-[#72C9BE] hover:bg-[#5db8ad] text-[#13443e] text-xs font-bold transition-all shadow-sm cursor-pointer"
                              >
                                Finish
                              </button>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleCancelSession();
                                }}
                                className="px-2 sm:px-2.5 py-1.5 rounded-xl bg-white hover:bg-rose-50 text-[#991B1B] hover:text-rose-700 text-xs font-semibold border border-[#E7EAF0] hover:border-rose-200 transition-all cursor-pointer"
                              >
                                Cancel
                              </button>
                            </>
                          )}
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleStartTask(task);
                          }}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-[#CFEDE7] hover:bg-[#b5e7dc] text-[#1A4B43] text-xs font-semibold transition-all cursor-pointer shadow-2xs"
                        >
                          <Play className="w-3 h-3 text-[#3D8C82] fill-current" />
                          <span>Start</span>
                        </button>
                      )
                    ) : (
                      <span className="text-xs text-[#1A4B43] font-medium px-2 py-0.5 rounded-md bg-[#CFEDE7]/40">
                        Finished
                      </span>
                    )}

                    {/* Secondary ⋯ Action Button */}
                    <div className="relative">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenMenuTaskId(openMenuTaskId === task.id ? null : task.id);
                        }}
                        className="p-1.5 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] border border-transparent hover:border-[#E7EAF0] transition-colors cursor-pointer"
                        title="More options"
                        aria-label="More task options"
                      >
                        <MoreHorizontal className="w-4 h-4" />
                      </button>

                      {/* ⋯ Dropdown Menu */}
                      {openMenuTaskId === task.id && (
                        <div
                          onClick={(e) => e.stopPropagation()}
                          className="absolute right-0 top-full mt-1.5 z-40 w-44 bg-white border border-[#E7EAF0] rounded-2xl p-1.5 shadow-float animate-in fade-in zoom-in-95 duration-100 text-xs"
                        >
                          <button
                            type="button"
                            onClick={(e) => handleOpenEditModal(task, e)}
                            className="w-full text-left px-3 py-2 rounded-xl text-[#26313F] hover:bg-[#F8FAFC] flex items-center gap-2 font-medium transition-colors cursor-pointer"
                          >
                            <Edit2 className="w-3.5 h-3.5 text-[#72C9BE]" />
                            <span>Edit</span>
                          </button>

                          <button
                            type="button"
                            onClick={(e) => handleOpenRescheduleModal(task, e)}
                            className="w-full text-left px-3 py-2 rounded-xl text-[#26313F] hover:bg-[#F8FAFC] flex items-center gap-2 font-medium transition-colors cursor-pointer"
                          >
                            <Calendar className="w-3.5 h-3.5 text-[#2563EB]" />
                            <span>Move / Reschedule</span>
                          </button>

                          <div className="my-1 border-t border-[#E7EAF0]/70" />

                          <button
                            type="button"
                            onClick={(e) => handleOpenDeleteConfirm(task, e)}
                            className="w-full text-left px-3 py-2 rounded-xl text-[#B91C1C] hover:bg-[#FEF2F2] flex items-center gap-2 font-medium transition-colors cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5 text-[#DC2626]" />
                            <span>Delete</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>



      {/* ======================================================== */}
      {/* ADVANCED TASK DETAIL / EDIT MODAL */}
      {/* ======================================================== */}
      {selectedTaskDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#26313F]/30 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white border border-[#E7EAF0] rounded-3xl max-w-md w-full p-6 space-y-4 shadow-float">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <h3 className="text-base font-bold text-[#26313F]">Task Details</h3>
              <button
                onClick={() => setSelectedTaskDetail(null)}
                className="p-1 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <span className="text-[#8E97A6] font-medium block">Title</span>
                <p className="text-sm font-semibold text-[#26313F] mt-0.5">{selectedTaskDetail.title}</p>
              </div>

              <div className="grid grid-cols-2 gap-3 pt-2">
                <div>
                  <span className="text-[#8E97A6] font-medium block">Subject</span>
                  <p className="text-[#26313F] font-medium mt-0.5">{selectedTaskDetail.subject?.name || 'General'}</p>
                </div>
                <div>
                  <span className="text-[#8E97A6] font-medium block">Estimated Duration</span>
                  <p className="text-[#26313F] font-medium mt-0.5">{selectedTaskDetail.estimated_minutes || 45} minutes</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className="text-[#8E97A6] font-medium block">Scheduled Date</span>
                  <p className="text-[#26313F] font-medium mt-0.5">{selectedTaskDetail.scheduled_date || 'Today'}</p>
                </div>
                <div>
                  <span className="text-[#8E97A6] font-medium block">Priority</span>
                  <span className="inline-block uppercase text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#F2F5F8] text-[#26313F] mt-0.5">
                    {selectedTaskDetail.priority || 'medium'}
                  </span>
                </div>
              </div>

              {selectedTaskDetail.missed_class_date && (
                <div className="pt-2 border-t border-[#E7EAF0]/60">
                  <span className="text-[#8E97A6] font-medium block">Missed Class Catch-up</span>
                  <div className="mt-1 p-2 rounded-xl bg-[#FEF3C7]/40 border border-[#FDE68A] text-[#92400E] text-xs flex items-center gap-2">
                    <Calendar className="w-3.5 h-3.5 text-[#D97706] shrink-0" />
                    <span>Taught on {formatDateLabel(selectedTaskDetail.missed_class_date)} while absent</span>
                  </div>
                </div>
              )}

              {selectedTaskDetail.reason && (
                <div className="pt-1 border-t border-[#E7EAF0]/60">
                  <span className="text-[#8E97A6] font-medium block">Intelligent Planning Rationale</span>
                  <div className="mt-1 space-y-1">
                    {selectedTaskDetail.reason.split('\n').map((line, idx) => (
                      <p key={idx} className="text-[#26313F] font-medium text-xs bg-[#F8FAFC] p-2 rounded-xl border border-[#E2E8F0]/70">
                        {line}
                      </p>
                    ))}
                  </div>
                </div>
              )}

              {selectedTaskDetail.description && selectedTaskDetail.description !== selectedTaskDetail.reason && (
                <div className="pt-1 border-t border-[#E7EAF0]/60">
                  <span className="text-[#8E97A6] font-medium block">Description</span>
                  <p className="text-[#26313F] font-medium mt-0.5 italic">{selectedTaskDetail.description}</p>
                </div>
              )}

              {/* Planning Transparency & Diagnostics Toggle */}
              <div className="pt-2 border-t border-[#E7EAF0]/60">
                <button
                  type="button"
                  onClick={() => setShowDevDiagnostics(!showDevDiagnostics)}
                  className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-[#6E7785] hover:text-[#26313F] transition-colors cursor-pointer"
                >
                  <Sliders className="w-3 h-3 text-[#72C9BE]" />
                  <span>{showDevDiagnostics ? 'Hide Planning Diagnostics' : 'Show Planning Diagnostics'}</span>
                </button>

                {showDevDiagnostics && (
                  <div className="mt-2 p-3 bg-[#F8FAFC] rounded-2xl border border-[#E2E8F0] space-y-2 text-[11px] font-mono animate-in fade-in duration-100">
                    <div className="flex justify-between items-center">
                      <span className="text-[#64748B]">Planning Score:</span>
                      <span className="font-bold text-[#0F172A] px-1.5 py-0.5 rounded bg-white border border-[#CBD5E1]">
                        {selectedTaskDetail.planning_score != null ? Number(selectedTaskDetail.planning_score).toFixed(2) : 'N/A'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[#64748B]">Priority Level:</span>
                      <span className="uppercase text-[#0F172A] font-sans font-semibold">{selectedTaskDetail.priority || 'medium'}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[#64748B]">Subject:</span>
                      <span className="text-[#0F172A] font-sans font-medium">{selectedTaskDetail.subject?.name || 'General'}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[#64748B]">Allocated Block:</span>
                      <span className="text-[#0F172A] font-bold">{selectedTaskDetail.estimated_minutes || 45} mins</span>
                    </div>
                    {selectedTaskDetail.missed_class_date && (
                      <div className="flex justify-between items-center">
                        <span className="text-[#64748B]">Absence Date:</span>
                        <span className="text-[#0F172A]">{selectedTaskDetail.missed_class_date}</span>
                      </div>
                    )}
                    <p className="text-[10px] text-[#94A3B8] font-sans pt-1.5 border-t border-[#E2E8F0] leading-snug">
                      Weights reflect exam proximity, topic difficulty, missed lecture priority, and prior student study feedback.
                    </p>
                  </div>
                )}
              </div>

              {selectedTaskDetail.is_completed && (
                <div className="grid grid-cols-2 gap-3 pt-2 border-t border-[#E7EAF0]/60">
                  <div>
                    <span className="text-[#8E97A6] font-medium block">Actual Time Spent</span>
                    <p className="text-[#26313F] font-medium mt-0.5">
                      {selectedTaskDetail.actual_minutes ? `${selectedTaskDetail.actual_minutes} min` : `${selectedTaskDetail.estimated_minutes || 45} min`}
                    </p>
                  </div>
                  <div>
                    <span className="text-[#8E97A6] font-medium block">Student Feedback</span>
                    <p className="text-[#26313F] font-medium mt-0.5 capitalize">
                      {selectedTaskDetail.feedback || 'Completed'}
                    </p>
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-[#E7EAF0]">
              <button
                type="button"
                onClick={() => {
                  const t = selectedTaskDetail;
                  handleOpenDeleteConfirm(t);
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs text-[#69242E] hover:bg-[#EABFC5]/20 rounded-xl transition-colors cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Delete</span>
              </button>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    const t = selectedTaskDetail;
                    setSelectedTaskDetail(null);
                    handleOpenEditModal(t);
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs text-[#1A4B43] bg-[#CFEDE7] hover:bg-[#b5e7dc] rounded-xl font-semibold transition-colors cursor-pointer"
                >
                  <Edit2 className="w-3.5 h-3.5" />
                  <span>Edit</span>
                </button>

                <button
                  type="button"
                  onClick={() => setSelectedTaskDetail(null)}
                  className="px-4 py-2 bg-[#F2F5F8] hover:bg-[#E7EAF0] text-[#26313F] text-xs font-semibold rounded-xl cursor-pointer"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* EDIT STUDY TASK MODAL */}
      {/* ======================================================== */}
      {editingTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#26313F]/30 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white border border-[#E7EAF0] rounded-3xl max-w-md w-full p-6 space-y-4 shadow-float">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <h3 className="text-base font-bold text-[#26313F] flex items-center gap-2">
                <Edit2 className="w-4 h-4 text-[#72C9BE]" />
                <span>Edit Study Task</span>
              </h3>
              <button
                onClick={() => setEditingTask(null)}
                className="p-1 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveEditTask} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-[#26313F] font-semibold mb-1">Task Title / Topic</label>
                <input
                  type="text"
                  required
                  value={editForm.title}
                  onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                  placeholder="e.g. Revise Inguinal Canal Anatomy"
                  className="w-full bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl px-3 py-2.5 text-[#26313F] focus:bg-white focus:border-[#72C9BE] focus:outline-none text-sm font-medium"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[#26313F] font-semibold mb-1">Subject</label>
                  <select
                    value={editForm.subject_id}
                    onChange={(e) => setEditForm({ ...editForm, subject_id: e.target.value })}
                    className="w-full bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl px-3 py-2 text-[#26313F] focus:bg-white focus:border-[#72C9BE] focus:outline-none"
                  >
                    <optgroup label="Current Semester">
                      {currentSemesterSubjects.map((s) => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                      ))}
                    </optgroup>
                    {otherSubjects.length > 0 && (
                      <optgroup label="Other Subjects">
                        {otherSubjects.map((s) => (
                          <option key={s.id} value={s.id}>{s.name}</option>
                        ))}
                      </optgroup>
                    )}
                  </select>
                </div>

                <div>
                  <label className="block text-[#26313F] font-semibold mb-1">Duration (minutes)</label>
                  <input
                    type="number"
                    min="10"
                    max="240"
                    value={editForm.estimated_minutes}
                    onChange={(e) => setEditForm({ ...editForm, estimated_minutes: parseInt(e.target.value, 10) || 30 })}
                    className="w-full bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl px-3 py-2 text-[#26313F] focus:bg-white focus:border-[#72C9BE] focus:outline-none font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[#26313F] font-semibold mb-1">Priority</label>
                  <select
                    value={editForm.priority}
                    onChange={(e) => setEditForm({ ...editForm, priority: e.target.value })}
                    className="w-full bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl px-3 py-2 text-[#26313F] focus:bg-white focus:border-[#72C9BE] focus:outline-none"
                  >
                    <option value="high">High Priority</option>
                    <option value="medium">Medium Priority</option>
                    <option value="low">Low Priority</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[#26313F] font-semibold mb-1">Quick Durations</label>
                  <div className="flex gap-1">
                    {[30, 45, 60].map((mins) => (
                      <button
                        key={mins}
                        type="button"
                        onClick={() => setEditForm({ ...editForm, estimated_minutes: mins })}
                        className={`flex-1 py-1.5 text-[11px] font-semibold rounded-lg border transition-all cursor-pointer ${
                          editForm.estimated_minutes === mins
                            ? 'bg-[#CFEDE7] text-[#1A4B43] border-[#72C9BE]'
                            : 'bg-[#F7F8FC] border-[#E7EAF0] text-[#6E7785] hover:border-slate-300'
                        }`}
                      >
                        {mins}m
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-[#26313F] font-semibold mb-1">Notes / Description</label>
                <textarea
                  rows="2"
                  value={editForm.description}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  placeholder="Optional notes, page numbers, or clinical focus..."
                  className="w-full bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl px-3 py-2 text-[#26313F] focus:bg-white focus:border-[#72C9BE] focus:outline-none resize-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-[#E7EAF0]">
                <button
                  type="button"
                  onClick={() => setEditingTask(null)}
                  className="px-4 py-2 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] font-medium transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-[#72C9BE] hover:bg-[#5bb8ac] text-[#13443e] font-semibold shadow-xs transition-colors cursor-pointer"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* MOVE / RESCHEDULE TASK MODAL */}
      {/* ======================================================== */}
      {reschedulingTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#26313F]/30 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white border border-[#E7EAF0] rounded-3xl max-w-sm w-full p-6 space-y-4 shadow-float">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <h3 className="text-base font-bold text-[#26313F] flex items-center gap-2">
                <Calendar className="w-4 h-4 text-[#2563EB]" />
                <span>Move / Reschedule Task</span>
              </h3>
              <button
                onClick={() => setReschedulingTask(null)}
                className="p-1 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3 bg-[#F8FAFC] border border-[#E7EAF0] rounded-2xl">
                <span className="text-[10px] uppercase font-bold text-[#6E7785] tracking-wider block">
                  Task to reschedule
                </span>
                <p className="font-semibold text-[#26313F] text-sm mt-0.5">{reschedulingTask.title}</p>
                <p className="text-[11px] text-[#6E7785] mt-0.5">
                  Currently scheduled: <span className="font-medium text-[#26313F]">{reschedulingTask.scheduled_date || 'Today'}</span>
                </p>
              </div>

              <div>
                <label className="block text-[#26313F] font-semibold mb-1.5">Select New Date</label>
                <input
                  type="date"
                  value={rescheduleDate}
                  onChange={(e) => setRescheduleDate(e.target.value)}
                  className="w-full bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl px-3 py-2 text-[#26313F] focus:bg-white focus:border-[#72C9BE] focus:outline-none font-medium text-xs"
                />
              </div>

              <div>
                <span className="text-[11px] font-semibold text-[#6E7785] block mb-1.5">Quick Presets:</span>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { label: 'Tomorrow', days: 1 },
                    { label: 'In 2 Days', days: 2 },
                    { label: 'In 3 Days', days: 3 },
                    { label: 'In 1 Week', days: 7 }
                  ].map((preset) => {
                    const d = new Date(Date.now() + preset.days * 86400000).toISOString().split('T')[0];
                    const isSelected = rescheduleDate === d;
                    return (
                      <button
                        key={preset.label}
                        type="button"
                        onClick={() => setRescheduleDate(d)}
                        className={`p-2 rounded-xl border text-xs font-semibold text-center transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-[#CFEDE7] text-[#1A4B43] border-[#72C9BE] shadow-2xs'
                            : 'bg-[#F7F8FC] border-[#E7EAF0] text-[#6E7785] hover:border-slate-300'
                        }`}
                      >
                        {preset.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <p className="text-[11px] text-[#8E97A6] leading-relaxed pt-1">
                Moving this task keeps its study priority, progress history, and original details without creating duplicates.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-[#E7EAF0]">
              <button
                type="button"
                onClick={() => setReschedulingTask(null)}
                className="px-4 py-2 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] font-medium transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleSaveRescheduleTask(rescheduleDate)}
                className="px-4 py-2 rounded-xl bg-[#2563EB] hover:bg-[#1d4ed8] text-white font-semibold transition-colors shadow-xs cursor-pointer"
              >
                Move Task
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* SUBTLE DELETE TASK CONFIRMATION MODAL */}
      {/* ======================================================== */}
      {deletingTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#26313F]/30 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white border border-[#E7EAF0] rounded-3xl max-w-sm w-full p-6 space-y-4 shadow-float">
            <div className="flex items-start gap-3">
              <div className="p-2.5 rounded-2xl bg-rose-50 border border-rose-100 text-rose-600 shrink-0">
                <Trash2 className="w-5 h-5" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-bold text-[#26313F]">Delete Study Task?</h3>
                <p className="text-xs text-[#6E7785] leading-relaxed">
                  Are you sure you want to remove <span className="font-semibold text-[#26313F]">"{deletingTask.title}"</span>? This will remove only this task from your study schedule.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-[#E7EAF0]">
              <button
                type="button"
                onClick={() => setDeletingTask(null)}
                className="px-4 py-2 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] text-xs font-semibold transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                className="px-4 py-2 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-bold transition-all shadow-2xs cursor-pointer"
              >
                Delete Task
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* COMPLETION FEEDBACK MODAL (OPTIONAL) */}
      {/* ======================================================== */}
      {completingTask && (
        <div className="fixed inset-0 z-50 bg-[#26313F]/40 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-3xl border border-[#E7EAF0] p-6 max-w-sm w-full shadow-float space-y-4">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <h3 className="text-base font-bold text-[#26313F] flex items-center gap-1.5">
                <span>Study completed</span>
                <span className="text-[#10B981] font-bold">✓</span>
              </h3>
              <button
                type="button"
                onClick={() => setCompletingTask(null)}
                className="p-1 rounded-xl text-[#8E97A6] hover:text-[#26313F] hover:bg-[#F2F5F8] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-[#CFEDE7]/60 text-[#13443e] border border-[#72C9BE]/30">
                {completingTask.subject?.name || 'Curriculum Study'}
              </span>
              <p className="text-xs font-bold text-[#1E293B] truncate pt-0.5">{completingTask.title}</p>
            </div>

            {/* Planned vs Actual Duration Display */}
            <div className="grid grid-cols-2 gap-2.5 py-1">
              <div className="p-3 rounded-2xl bg-[#F8FAFC] border border-[#E2E8F0] text-center">
                <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider block">Planned</span>
                <span className="text-base font-extrabold text-[#1E293B] font-mono mt-0.5 block">
                  {formatDurationDisplay(completingTask.plannedMinutes || completingTask.estimated_minutes || 45)}
                </span>
              </div>
              <div className="p-3 rounded-2xl bg-[#CFEDE7]/40 border border-[#72C9BE]/40 text-center">
                <span className="text-[10px] font-bold text-[#13443e] uppercase tracking-wider block">Actual</span>
                <span className="text-base font-extrabold text-[#13443e] font-mono mt-0.5 block">
                  {formatDurationDisplay(completingTask.actualMinutes || 30)}
                </span>
              </div>
            </div>

            {/* Optional question: How did it feel? */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-[#26313F]">How did it feel?</span>
                <span className="text-[10px] text-[#8E97A6] font-medium">(Optional)</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { id: 'easy', label: 'Easy', emoji: '😄', desc: 'Revision may require less time' },
                  { id: 'okay', label: 'Okay', emoji: '🙂', desc: 'Current estimate was reasonable' },
                  { id: 'hard', label: 'Hard', emoji: '😓', desc: 'Future plans allocate more time' },
                  { id: 'need_more_time', label: 'Need more time', emoji: '⏳', desc: 'Schedules follow-up session' },
                ].map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setCompletionFeedback(completionFeedback === opt.id ? null : opt.id)}
                    className={`p-2.5 rounded-2xl border text-left transition-all cursor-pointer ${
                      completionFeedback === opt.id
                        ? 'bg-[#CFEDE7]/70 border-[#72C9BE] text-[#13443e] ring-2 ring-[#72C9BE]/30 shadow-2xs'
                        : 'bg-[#F8FAFC] border-[#E2E8F0] text-[#26313F] hover:border-[#CBD5E1]'
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs">{opt.emoji}</span>
                      <span className="text-xs font-bold text-[#1E293B]">{opt.label}</span>
                    </div>
                    <span className="text-[10px] text-[#6E7785] block mt-0.5 leading-tight">{opt.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            {completionFeedback === 'need_more_time' && (
              <div className="space-y-2.5 pt-2 border-t border-[#E7EAF0] animate-in fade-in duration-200">
                <div className="p-2.5 rounded-2xl bg-[#FEF3C7]/70 border border-[#FDE68A]">
                  <p className="text-xs font-bold text-[#92400E]">
                    This topic needs a little more time. What would you like to do?
                  </p>
                </div>

                <div className="space-y-2">
                  {/* Choice 1: Continue Now */}
                  <button
                    type="button"
                    onClick={() => {
                      setNmtStep('continue_now');
                      updateContinueDuration(30);
                      setShowSpecificEndTime(false);
                    }}
                    className="w-full p-2.5 rounded-2xl border border-[#72C9BE] bg-[#CFEDE7]/40 hover:bg-[#CFEDE7]/70 text-left transition-all cursor-pointer flex items-start gap-2.5 shadow-2xs"
                  >
                    <span className="p-1.5 rounded-xl bg-[#72C9BE] text-[#13443e] font-bold text-xs shrink-0 mt-0.5">⚡</span>
                    <div>
                      <span className="text-xs font-bold text-[#13443e] block">1. Continue Now</span>
                      <span className="text-[11px] text-[#1A4B43] leading-snug block mt-0.5">
                        Keep studying right now with the active timer.
                      </span>
                    </div>
                  </button>

                  {/* Choice 2: Add to My Plan */}
                  <div className="p-2.5 rounded-2xl border border-[#CBD5E1] bg-[#F8FAFC] space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-start gap-2.5">
                        <span className="p-1.5 rounded-xl bg-[#E2E8F0] text-[#334155] font-bold text-xs shrink-0 mt-0.5">📅</span>
                        <div>
                          <span className="text-xs font-bold text-[#1E293B] block">2. Add to My Plan</span>
                          <span className="text-[11px] text-[#64748B] leading-snug block mt-0.5">
                            Re-plan upcoming days within your daily limit.
                          </span>
                        </div>
                      </div>
                      <button
                        type="button"
                        disabled={replanLoading}
                        onClick={() => handleAddToPlan('auto', { extra_minutes: addToPlanMinutes })}
                        className="px-3 py-1.5 bg-[#72C9BE] hover:bg-[#5bb8ac] text-[#13443e] font-bold text-xs rounded-xl transition-all shrink-0 cursor-pointer shadow-2xs"
                      >
                        Add ({addToPlanMinutes}m)
                      </button>
                    </div>

                    <div className="flex items-center gap-1.5 pt-1 border-t border-[#E2E8F0]/60">
                      <span className="text-[10px] font-bold text-[#64748B] px-1">Follow-up:</span>
                      {[20, 30, 45, 60].map((mins) => (
                        <button
                          key={mins}
                          type="button"
                          onClick={() => setAddToPlanMinutes(mins)}
                          className={`py-0.5 px-2 rounded-lg text-[11px] font-bold transition-all cursor-pointer ${
                            addToPlanMinutes === mins
                              ? 'bg-[#72C9BE] text-[#13443e]'
                              : 'bg-white border border-[#E2E8F0] text-[#64748B] hover:bg-[#F1F5F9]'
                          }`}
                        >
                          {mins}m
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Choice 3: I'll Handle It Later */}
                  <button
                    type="button"
                    disabled={replanLoading}
                    onClick={handleHandleLater}
                    className="w-full p-2.5 rounded-2xl border border-[#E2E8F0] bg-white hover:bg-[#F8FAFC] text-left transition-all cursor-pointer flex items-start gap-2.5 shadow-2xs"
                  >
                    <span className="p-1.5 rounded-xl bg-[#F1F5F9] text-[#64748B] font-bold text-xs shrink-0 mt-0.5">📝</span>
                    <div>
                      <span className="text-xs font-bold text-[#475569] block">3. I'll Handle It Later</span>
                      <span className="text-[11px] text-[#64748B] leading-snug block mt-0.5">
                        Save progress & feedback without adding extra tasks.
                      </span>
                    </div>
                  </button>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between pt-3 border-t border-[#E7EAF0] gap-2">
              <button
                type="button"
                onClick={() => handleSubmitTaskFeedback(true)}
                className="px-3.5 py-2 text-xs font-semibold text-[#6E7785] hover:bg-[#F2F5F8] rounded-xl transition-colors cursor-pointer"
              >
                Skip Feedback
              </button>
              <button
                type="button"
                onClick={() => handleSubmitTaskFeedback(false)}
                className="px-4 py-2 bg-[#72C9BE] hover:bg-[#5bb8ac] text-[#13443e] font-bold text-xs rounded-xl transition-all shadow-sm cursor-pointer"
              >
                Save & Complete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* CONTINUE NOW MODAL (DURATION-FIRST INTERFACE) */}
      {/* ======================================================== */}
      {nmtStep === 'continue_now' && completingTask && (
        <div className="fixed inset-0 z-50 bg-[#26313F]/40 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-3xl border border-[#E7EAF0] p-6 max-w-sm w-full shadow-float space-y-4">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <h3 className="text-base font-bold text-[#26313F] flex items-center gap-2">
                <span className="p-1 rounded-lg bg-[#CFEDE7] text-[#1A4B43]">⚡</span>
                <span>Continue Studying</span>
              </h3>
              <button
                type="button"
                onClick={() => { setNmtStep(null); setContinueConflict(null); }}
                className="p-1 rounded-xl text-[#8E97A6] hover:text-[#26313F] hover:bg-[#F2F5F8] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-[#CFEDE7]/60 text-[#13443e] border border-[#72C9BE]/30">
                {completingTask.subject?.name || 'Curriculum Study'}
              </span>
              <p className="text-xs font-bold text-[#1E293B] truncate pt-0.5">{completingTask.title}</p>
            </div>

            {/* Duration-First Interface */}
            <div className="space-y-3 pt-1">
              <label className="text-xs font-bold text-[#26313F] block">
                How much longer do you want to study?
              </label>

              {/* Quick Chips: [ +15 min ] [ +30 min ] [ +45 min ] [ +1 hr ] */}
              <div className="grid grid-cols-4 gap-1.5">
                {[
                  { label: '+15 min', mins: 15 },
                  { label: '+30 min', mins: 30 },
                  { label: '+45 min', mins: 45 },
                  { label: '+1 hr', mins: 60 }
                ].map((chip) => {
                  const isSelected = continueDurationMinutes === chip.mins;
                  return (
                    <button
                      key={chip.mins}
                      type="button"
                      onClick={() => updateContinueDuration(chip.mins)}
                      className={`py-2 px-1 rounded-xl border text-xs font-bold transition-all cursor-pointer text-center ${
                        isSelected
                          ? 'border-[#72C9BE] bg-[#CFEDE7] text-[#13443e] shadow-2xs'
                          : 'border-[#E2E8F0] bg-[#F8FAFC] hover:bg-[#F1F5F9] text-[#475569]'
                      }`}
                    >
                      {chip.label}
                    </button>
                  );
                })}
              </div>

              {/* Custom Stepper: [-] 25 min [+] */}
              <div className="flex items-center justify-between p-2 rounded-2xl bg-[#F8FAFC] border border-[#E2E8F0]">
                <span className="text-xs font-semibold text-[#64748B] pl-1">Custom:</span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => updateContinueDuration(continueDurationMinutes - 5)}
                    disabled={continueDurationMinutes <= 5}
                    className="w-8 h-8 rounded-xl border border-[#E2E8F0] bg-white hover:bg-[#F1F5F9] text-sm font-bold text-[#334155] disabled:opacity-40 transition-all flex items-center justify-center cursor-pointer shadow-2xs"
                  >
                    -
                  </button>
                  <span className="text-xs font-bold text-[#1E293B] min-w-[58px] text-center font-mono">
                    {continueDurationMinutes} min
                  </span>
                  <button
                    type="button"
                    onClick={() => updateContinueDuration(continueDurationMinutes + 5)}
                    disabled={continueDurationMinutes >= 240}
                    className="w-8 h-8 rounded-xl border border-[#E2E8F0] bg-white hover:bg-[#F1F5F9] text-sm font-bold text-[#334155] disabled:opacity-40 transition-all flex items-center justify-center cursor-pointer shadow-2xs"
                  >
                    +
                  </button>
                </div>
              </div>

              {/* Dynamic calculation readout */}
              <div className="flex items-center justify-between text-xs font-medium text-[#1A4B43] bg-[#CFEDE7]/50 px-3 py-2 rounded-xl border border-[#72C9BE]/30">
                <span>About {continueDurationMinutes} more minutes</span>
                <span className="text-[11px] font-bold text-[#13443e]">
                  until ~{getFormattedStopTime(continueDurationMinutes)}
                </span>
              </div>

              {/* Secondary option: "Study until a specific time" */}
              <div className="pt-1">
                <button
                  type="button"
                  onClick={() => setShowSpecificEndTime(!showSpecificEndTime)}
                  className="text-[11px] font-semibold text-[#64748B] hover:text-[#26313F] transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  <span>{showSpecificEndTime ? '▾' : '▸'} Study until a specific time</span>
                </button>

                {showSpecificEndTime && (
                  <div className="mt-2 p-2.5 rounded-2xl bg-[#F8FAFC] border border-[#E2E8F0] space-y-1 animate-in fade-in duration-150">
                    <label className="text-[10px] font-bold uppercase tracking-wider text-[#64748B] block">
                      Target End Time
                    </label>
                    <input
                      type="time"
                      value={continueEndTime}
                      onChange={(e) => handleSpecificTimeChange(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-xl border border-[#E2E8F0] bg-white text-xs font-mono font-bold text-[#1E293B] focus:border-[#72C9BE] focus:ring-1 focus:ring-[#72C9BE] outline-none"
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Conflict Warning & Resolution Actions */}
            {continueConflict && (
              <div className="p-3 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 space-y-2">
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <p className="text-xs leading-snug">
                    Continuing for {continueDurationMinutes} min overlaps with planned task (<strong>{continueConflict.title}</strong>).
                  </p>
                </div>
                <div className="flex flex-col gap-1.5 pt-1">
                  <button
                    type="button"
                    onClick={handleMoveConflictingTask}
                    className="w-full py-1.5 px-2.5 rounded-xl bg-white hover:bg-amber-100/60 border border-amber-300 text-amber-800 text-[11px] font-bold transition-all text-left flex items-center justify-between cursor-pointer"
                  >
                    <span>Move conflicting task</span>
                    <span className="text-[10px] text-amber-700">after target stop &rarr;</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleShortenConflictingTask}
                    className="w-full py-1.5 px-2.5 rounded-xl bg-white hover:bg-amber-100/60 border border-amber-300 text-amber-800 text-[11px] font-bold transition-all text-left flex items-center justify-between cursor-pointer"
                  >
                    <span>Shorten conflicting task</span>
                    <span className="text-[10px] text-amber-700">-15m &rarr;</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const [ch, cm] = (continueConflict.scheduled_time || '18:00').split(':').map(Number);
                      const safeTime = `${String(ch).padStart(2, '0')}:${String(cm).padStart(2, '0')}`;
                      handleSpecificTimeChange(safeTime);
                    }}
                    className="w-full py-1.5 px-2.5 rounded-xl bg-white hover:bg-amber-100/60 border border-amber-300 text-amber-800 text-[11px] font-bold transition-all text-left flex items-center justify-between cursor-pointer"
                  >
                    <span>Adjust stop time</span>
                    <span className="text-[10px] text-amber-700">stop before conflict</span>
                  </button>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between pt-3 border-t border-[#E7EAF0] gap-2">
              <button
                type="button"
                onClick={() => { setNmtStep(null); setContinueConflict(null); }}
                className="px-3.5 py-2 text-xs font-semibold text-[#6E7785] hover:bg-[#F2F5F8] rounded-xl transition-colors cursor-pointer"
              >
                Back
              </button>
              <button
                type="button"
                onClick={handleConfirmContinueNow}
                className="px-4 py-2 bg-[#72C9BE] hover:bg-[#5bb8ac] text-[#13443e] font-bold text-xs rounded-xl transition-all shadow-sm cursor-pointer"
              >
                Continue Session
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* NO SPACE MODAL (SCHEDULE FULL - 4 USER CHOICES) */}
      {/* ======================================================== */}
      {nmtStep === 'no_space' && noSpaceData && (
        <div className="fixed inset-0 z-50 bg-[#26313F]/40 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-3xl border border-[#E7EAF0] p-6 max-w-md w-full shadow-float space-y-4">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <h3 className="text-base font-bold text-[#26313F] flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-amber-500 shrink-0" />
                <span>Schedule Full</span>
              </h3>
              <button
                type="button"
                onClick={() => { setNmtStep(null); setNoSpaceData(null); setShowMoveTaskPicker(false); }}
                className="p-1 rounded-xl text-[#8E97A6] hover:text-[#26313F] hover:bg-[#F2F5F8] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 space-y-1">
              <p className="text-xs font-bold">{noSpaceData.message || 'All upcoming days are already at your daily study limit.'}</p>
              <p className="text-[11px] text-amber-700">
                Daily limit: {noSpaceData.daily_limit_minutes || 120} min/day. Choose how you would like to accommodate your {addToPlanMinutes} min follow-up:
              </p>
            </div>

            <div className="space-y-2 pt-1">
              {/* Choice 1: Spread beyond current plan */}
              <button
                type="button"
                disabled={replanLoading}
                onClick={() => handleAddToPlan('spread_later', { extra_minutes: addToPlanMinutes })}
                className="w-full p-3 rounded-2xl border border-[#E2E8F0] bg-[#F8FAFC] hover:bg-[#F1F5F9] text-left transition-all cursor-pointer flex items-center justify-between shadow-2xs"
              >
                <div>
                  <span className="text-xs font-bold text-[#1E293B] block">1. Spread beyond current plan</span>
                  <span className="text-[11px] text-[#64748B] block mt-0.5">
                    Add study days after your current plan end date while keeping your daily limit.
                  </span>
                </div>
                <ArrowRight className="w-4 h-4 text-[#72C9BE] shrink-0 ml-2" />
              </button>

              {/* Choice 2: Move a lower-priority task (pick which non-urgent task to postpone) */}
              <div className="p-3 rounded-2xl border border-[#E2E8F0] bg-[#F8FAFC] space-y-2">
                <div
                  onClick={() => setShowMoveTaskPicker(!showMoveTaskPicker)}
                  className="flex items-center justify-between cursor-pointer"
                >
                  <div>
                    <span className="text-xs font-bold text-[#1E293B] block">2. Move a lower-priority task</span>
                    <span className="text-[11px] text-[#64748B] block mt-0.5">
                      Pick a non-urgent task to postpone so tomorrow stays within limit.
                    </span>
                  </div>
                  <span className="text-xs font-bold text-[#72C9BE] shrink-0 ml-2">
                    {showMoveTaskPicker ? 'Hide ▲' : 'Select ▼'}
                  </span>
                </div>

                {showMoveTaskPicker && (
                  <div className="pt-2 border-t border-[#E2E8F0] space-y-2 animate-in fade-in duration-150">
                    {noSpaceData.tomorrow_tasks && noSpaceData.tomorrow_tasks.length > 0 ? (
                      <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                        {noSpaceData.tomorrow_tasks.map((mt) => {
                          const isSelected = selectedMoveTaskId === mt.id;
                          return (
                            <div
                              key={mt.id}
                              onClick={() => setSelectedMoveTaskId(mt.id)}
                              className={`p-2 rounded-xl border text-xs cursor-pointer transition-all flex items-center justify-between ${
                                isSelected
                                  ? 'border-[#72C9BE] bg-[#CFEDE7]/50 text-[#13443e] font-semibold ring-1 ring-[#72C9BE]'
                                  : 'border-[#E2E8F0] bg-white text-[#334155] hover:border-[#CBD5E1]'
                              }`}
                            >
                              <div className="truncate pr-2">
                                <span className="block truncate font-bold text-[11px]">{mt.title}</span>
                                <span className="text-[10px] text-[#64748B]">
                                  {mt.subject_name} • {mt.estimated_minutes} min • {mt.priority} priority
                                </span>
                              </div>
                              <span className="text-[10px] font-bold text-[#72C9BE] shrink-0">
                                {isSelected ? '✓ Selected' : 'Select'}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="text-[11px] text-[#64748B] italic">No non-urgent tasks found to postpone.</p>
                    )}

                    <button
                      type="button"
                      disabled={!selectedMoveTaskId || replanLoading}
                      onClick={() =>
                        handleAddToPlan('move_lower_priority', {
                          move_task_id: selectedMoveTaskId,
                          extra_minutes: addToPlanMinutes
                        })
                      }
                      className="w-full py-2 px-3 bg-[#72C9BE] hover:bg-[#5bb8ac] text-[#13443e] font-bold text-xs rounded-xl transition-all disabled:opacity-40 cursor-pointer shadow-2xs"
                    >
                      Postpone Selected Task & Schedule Follow-up
                    </button>
                  </div>
                )}
              </div>

              {/* Choice 3: Increase daily time for one day */}
              <button
                type="button"
                disabled={replanLoading}
                onClick={() =>
                  handleAddToPlan('increase_study_time', {
                    increase_daily_limit: true,
                    extra_minutes: addToPlanMinutes
                  })
                }
                className="w-full p-3 rounded-2xl border border-[#72C9BE]/50 bg-[#CFEDE7]/40 hover:bg-[#CFEDE7]/70 text-left transition-all cursor-pointer flex items-center justify-between shadow-2xs"
              >
                <div>
                  <span className="text-xs font-bold text-[#13443e] block">3. Increase daily time for one day</span>
                  <span className="text-[11px] text-[#1A4B43] block mt-0.5">
                    Allow an extra {addToPlanMinutes} min over your daily limit for tomorrow only.
                  </span>
                </div>
                <ArrowRight className="w-4 h-4 text-[#72C9BE] shrink-0 ml-2" />
              </button>

              {/* Choice 4: I'll handle it later */}
              <button
                type="button"
                disabled={replanLoading}
                onClick={handleHandleLater}
                className="w-full p-3 rounded-2xl border border-[#E2E8F0] bg-white hover:bg-[#F8FAFC] text-left transition-all cursor-pointer flex items-center justify-between shadow-2xs"
              >
                <div>
                  <span className="text-xs font-bold text-[#475569] block">4. I'll handle it later</span>
                  <span className="text-[11px] text-[#64748B] block mt-0.5">
                    Save "Need more time" progress without adding extra tasks to your schedule.
                  </span>
                </div>
                <ArrowRight className="w-4 h-4 text-[#64748B] shrink-0 ml-2" />
              </button>
            </div>

            <div className="pt-2 border-t border-[#E7EAF0] flex justify-end">
              <button
                type="button"
                onClick={() => { setNmtStep(null); setNoSpaceData(null); setShowMoveTaskPicker(false); }}
                className="px-4 py-1.5 text-xs font-semibold text-[#6E7785] hover:bg-[#F2F5F8] rounded-xl transition-colors cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* ADD TASK MODAL */}
      {/* ======================================================== */}
      {addTaskModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#26313F]/30 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white border border-[#E7EAF0] rounded-3xl max-w-md w-full p-6 space-y-4 shadow-float">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <h3 className="text-base font-bold text-[#26313F] flex items-center gap-2">
                <Plus className="w-4 h-4 text-[#72C9BE]" />
                <span>Add Study Task</span>
              </h3>
              <button
                onClick={() => setAddTaskModal(false)}
                className="p-1 rounded-xl text-[#6E7785] hover:text-[#26313F]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateTask} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-[#26313F] font-semibold mb-1">Task Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g., Revise Upper Limb brachial plexus"
                  value={taskForm.title}
                  onChange={(e) => setTaskForm({ ...taskForm, title: e.target.value })}
                  className="w-full bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl px-3 py-2 text-[#26313F] focus:border-[#72C9BE] focus:outline-none text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[#26313F] font-semibold mb-1">Subject</label>
                  <select
                    value={taskForm.subject_id}
                    onChange={(e) => setTaskForm({ ...taskForm, subject_id: e.target.value })}
                    className="w-full bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl px-3 py-2 text-[#26313F] focus:border-[#72C9BE] focus:outline-none"
                  >
                    <optgroup label="Current Semester">
                      {currentSemesterSubjects.map((s) => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                      ))}
                    </optgroup>
                    {otherSubjects.length > 0 && (
                      <optgroup label="Other Subjects">
                        {otherSubjects.map((s) => (
                          <option key={s.id} value={s.id}>{s.name}</option>
                        ))}
                      </optgroup>
                    )}
                  </select>
                </div>
                <div>
                  <label className="block text-[#26313F] font-semibold mb-1">Duration (mins)</label>
                  <input
                    type="number"
                    min={10}
                    max={240}
                    value={taskForm.estimated_minutes}
                    onChange={(e) => setTaskForm({ ...taskForm, estimated_minutes: parseInt(e.target.value) })}
                    className="w-full bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl px-3 py-2 text-[#26313F] focus:border-[#72C9BE] focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[#26313F] font-semibold mb-1">Scheduled Date</label>
                <input
                  type="date"
                  value={taskForm.scheduled_date}
                  onChange={(e) => setTaskForm({ ...taskForm, scheduled_date: e.target.value })}
                  className="w-full bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl px-3 py-2 text-[#26313F] focus:border-[#72C9BE] focus:outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-[#E7EAF0]">
                <button
                  type="button"
                  onClick={() => setAddTaskModal(false)}
                  className="px-4 py-2 rounded-xl text-[#6E7785] hover:text-[#26313F]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2.5 rounded-xl bg-[#72C9BE] hover:bg-[#5db8ad] text-[#13443e] font-semibold shadow-sm"
                >
                  Create Task
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* AI STUDY PLAN MODAL */}
      {/* ======================================================== */}
      {aiPlanModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#26313F]/30 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white border border-[#E7EAF0] rounded-3xl max-w-lg w-full p-6 space-y-4 shadow-float max-h-[92vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <div>
                <h3 className="text-base font-bold text-[#26313F] flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-[#72C9BE]" />
                  <span>Generate Study Plan</span>
                </h3>
                <p className="text-[11px] text-[#6E7785] mt-0.5">
                  Structured schedule tailored to your daily availability and curriculum.
                </p>
              </div>
              <button
                onClick={() => setAiPlanModal(false)}
                className="p-1.5 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F7F8FC] transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleGenerateAiPlan} className="space-y-4 text-xs">
              {/* Number of Study Days */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-bold text-[#26313F]">Number of Study Days</label>
                  <span className="text-[11px] font-medium text-[#6E7785]">
                    {aiPlanForm.until_next_exam && daysUntilNextExam
                      ? `Locked to exam (${daysUntilNextExam} ${daysUntilNextExam === 1 ? 'day' : 'days'})`
                      : `${aiPlanForm.plan_days} ${aiPlanForm.plan_days === 1 ? 'day' : 'days'}`}
                  </span>
                </div>
                <div className="flex items-center gap-3 flex-wrap">
                  <div className="inline-flex items-center bg-[#F7F8FC] border border-[#E7EAF0] rounded-2xl p-1">
                    <button
                      type="button"
                      disabled={aiPlanForm.until_next_exam || aiPlanForm.plan_days <= 1}
                      onClick={() => setAiPlanForm((prev) => ({ ...prev, plan_days: Math.max(1, prev.plan_days - 1) }))}
                      className="w-8 h-8 rounded-xl bg-white border border-[#E7EAF0] flex items-center justify-center text-[#26313F] hover:bg-[#EFF3F8] disabled:opacity-40 disabled:hover:bg-white shadow-xs transition-colors cursor-pointer"
                      title="Decrease days"
                    >
                      <Minus className="w-3.5 h-3.5" />
                    </button>
                    <span className="w-12 text-center text-sm font-bold text-[#26313F]">
                      {aiPlanForm.until_next_exam && daysUntilNextExam ? daysUntilNextExam : aiPlanForm.plan_days}
                    </span>
                    <button
                      type="button"
                      disabled={aiPlanForm.until_next_exam || aiPlanForm.plan_days >= 30}
                      onClick={() => setAiPlanForm((prev) => ({ ...prev, plan_days: Math.min(30, prev.plan_days + 1) }))}
                      className="w-8 h-8 rounded-xl bg-white border border-[#E7EAF0] flex items-center justify-center text-[#26313F] hover:bg-[#EFF3F8] disabled:opacity-40 disabled:hover:bg-white shadow-xs transition-colors cursor-pointer"
                      title="Increase days"
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {nextExam && (
                    <label className="flex items-center gap-2 cursor-pointer text-xs text-[#26313F] font-medium bg-[#F7F8FC] border border-[#E7EAF0] px-3 py-2 rounded-2xl hover:bg-[#EFF3F8] transition-colors">
                      <input
                        type="checkbox"
                        checked={aiPlanForm.until_next_exam}
                        onChange={(e) => {
                          const checked = e.target.checked;
                          setAiPlanForm((prev) => ({
                            ...prev,
                            until_next_exam: checked,
                            plan_days: checked && daysUntilNextExam ? daysUntilNextExam : prev.plan_days
                          }));
                        }}
                        className="rounded text-[#72C9BE] focus:ring-[#72C9BE] w-3.5 h-3.5"
                      />
                      <span>Until Next Exam ({daysUntilNextExam}d &bull; {nextExam.name || 'Exam'})</span>
                    </label>
                  )}
                </div>
              </div>

              {/* Study Time Per Day */}
              <div>
                <label className="block text-xs font-bold text-[#26313F] mb-1.5">Study Time Per Day</label>
                <div className="grid grid-cols-2 gap-2.5">
                  <div className="relative">
                    <input
                      type="number"
                      min="0"
                      max="16"
                      value={aiPlanForm.study_hours}
                      onChange={(e) =>
                        setAiPlanForm((prev) => ({
                          ...prev,
                          study_hours: Math.max(0, parseInt(e.target.value, 10) || 0)
                        }))
                      }
                      className="w-full bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl px-3 py-2 text-xs font-semibold text-[#26313F] focus:border-[#72C9BE] focus:outline-none pr-14"
                      placeholder="1"
                    />
                    <span className="absolute right-3 top-2 text-[11px] font-medium text-[#6E7785] pointer-events-none">
                      Hours
                    </span>
                  </div>
                  <div className="relative">
                    <select
                      value={aiPlanForm.study_minutes}
                      onChange={(e) =>
                        setAiPlanForm((prev) => ({
                          ...prev,
                          study_minutes: parseInt(e.target.value, 10) || 0
                        }))
                      }
                      className="w-full bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl px-3 py-2 text-xs font-semibold text-[#26313F] focus:border-[#72C9BE] focus:outline-none"
                    >
                      <option value={0}>0 Minutes</option>
                      <option value={15}>15 Minutes</option>
                      <option value={30}>30 Minutes</option>
                      <option value={45}>45 Minutes</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Live Time Summary */}
              <div className="p-2.5 rounded-2xl bg-[#E8F6F4] border border-[#72C9BE]/30 flex items-center justify-between text-xs">
                <span className="text-[#13443e] font-medium flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-[#72C9BE]" />
                  <span>Total Available Study Time:</span>
                </span>
                <span className="font-bold text-[#13443e]">
                  {Math.floor(totalAvailableMinutes / 60) > 0 ? `${Math.floor(totalAvailableMinutes / 60)}h ` : ''}
                  {totalAvailableMinutes % 60 > 0 || totalAvailableMinutes === 0
                    ? `${totalAvailableMinutes % 60}m`
                    : ''}
                  <span className="text-[#6E7785] font-normal ml-1">
                    ({totalAvailableMinutes} mins over {currentPlanDays} {currentPlanDays === 1 ? 'day' : 'days'})
                  </span>
                </span>
              </div>

              {/* Subjects */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-bold text-[#26313F]">Subjects</label>
                  <span className="text-[11px] text-[#6E7785]">
                    {showAllSubjects ? `${subjects.length} total subjects` : `${currentSemesterSubjects.length} current semester`}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 mb-2">
                  {[
                    { id: 'all', label: showAllSubjects ? 'All Subjects' : 'All Current Sem' },
                    { id: 'choose', label: 'Choose Subjects' },
                    { id: 'auto', label: 'Let MedPilot Decide' }
                  ].map((opt) => (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => {
                        setAiPlanForm((prev) => ({
                          ...prev,
                          subject_mode: opt.id,
                          subject_ids:
                            opt.id === 'choose' && prev.subject_ids.length === 0
                              ? currentSemesterSubjects.map((s) => s.id)
                              : prev.subject_ids
                        }));
                      }}
                      className={`py-2 px-2 text-xs font-semibold rounded-xl border text-center transition-all cursor-pointer ${
                        aiPlanForm.subject_mode === opt.id
                          ? 'bg-[#72C9BE]/15 border-[#72C9BE] text-[#13443e] shadow-xs'
                          : 'bg-[#F7F8FC] border-[#E7EAF0] text-[#6E7785] hover:border-[#CBD5E1]'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>

                {aiPlanForm.subject_mode !== 'choose' && otherSubjects.length > 0 && (
                  <div className="text-[11px] text-[#6E7785] bg-[#F7F8FC] border border-[#E7EAF0] px-3 py-1.5 rounded-xl flex items-center justify-between mb-1">
                    <span>
                      {showAllSubjects
                        ? `Including all ${subjects.length} subjects in plan.`
                        : `Defaulting to ${currentSemesterSubjects.length} current semester subjects.`}
                    </span>
                    <button
                      type="button"
                      onClick={() => setShowAllSubjects(!showAllSubjects)}
                      className="text-[#13443e] font-semibold hover:underline cursor-pointer ml-2"
                    >
                      {showAllSubjects ? 'Current Semester Only' : `Show All Subjects (${subjects.length})`}
                    </button>
                  </div>
                )}

                {aiPlanForm.subject_mode === 'choose' && (
                  <div className="p-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-2xl space-y-2.5 mt-2 animate-in fade-in duration-100">
                    <div className="flex items-center justify-between text-[11px] text-[#6E7785]">
                      <span>
                        Current Semester Subjects ({aiPlanForm.subject_ids.filter(id => currentSemesterSubjects.some(s => s.id === id)).length}/{currentSemesterSubjects.length} selected):
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          const activePool = showAllSubjects ? subjects : currentSemesterSubjects;
                          const poolIds = activePool.map((s) => s.id);
                          const allInPoolSelected = poolIds.every((id) => aiPlanForm.subject_ids.includes(id));
                          setAiPlanForm((prev) => ({
                            ...prev,
                            subject_ids: allInPoolSelected
                              ? prev.subject_ids.filter((id) => !poolIds.includes(id))
                              : Array.from(new Set([...prev.subject_ids, ...poolIds]))
                          }));
                        }}
                        className="text-[#72C9BE] hover:underline font-medium cursor-pointer"
                      >
                        {(showAllSubjects ? subjects : currentSemesterSubjects).every((s) => aiPlanForm.subject_ids.includes(s.id))
                          ? 'Deselect All'
                          : 'Select All'}
                      </button>
                    </div>

                    {/* Primary current semester subject pills */}
                    <div className="flex flex-wrap gap-1.5">
                      {currentSemesterSubjects.map((s) => {
                        const isSelected = aiPlanForm.subject_ids.includes(s.id);
                        return (
                          <button
                            key={s.id}
                            type="button"
                            onClick={() => {
                              setAiPlanForm((prev) => ({
                                ...prev,
                                subject_ids: isSelected
                                  ? prev.subject_ids.filter((id) => id !== s.id)
                                  : [...prev.subject_ids, s.id]
                              }));
                            }}
                            className={`px-2.5 py-1 rounded-lg text-xs font-medium border flex items-center gap-1.5 transition-all cursor-pointer ${
                              isSelected
                                ? 'bg-white border-[#72C9BE] text-[#13443e] shadow-xs'
                                : 'bg-white/50 border-[#E7EAF0] text-[#8C95A3] hover:border-[#CBD5E1]'
                            }`}
                          >
                            <span
                              className="w-2 h-2 rounded-full"
                              style={{ backgroundColor: s.color || s.color_code || '#72C9BE' }}
                            />
                            <span>{s.name}</span>
                            {isSelected && <Check className="w-3 h-3 text-[#72C9BE]" />}
                          </button>
                        );
                      })}
                    </div>

                    {/* Secondary option: Other Subjects toggle */}
                    {otherSubjects.length > 0 && (
                      <div className="pt-2 border-t border-[#E7EAF0]/70 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] text-[#6E7785]">
                            {showAllSubjects ? 'Other semester / elective subjects:' : `${otherSubjects.length} other subjects available`}
                          </span>
                          <button
                            type="button"
                            onClick={() => setShowAllSubjects(!showAllSubjects)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl text-[11px] font-semibold text-[#4F5969] bg-white border border-[#E7EAF0] hover:bg-[#F2F5F8] transition-colors cursor-pointer shadow-2xs"
                          >
                            <span>{showAllSubjects ? 'Hide Other Subjects' : `+ Other Subjects (${otherSubjects.length})`}</span>
                            <ChevronDown className={`w-3 h-3 transition-transform ${showAllSubjects ? 'rotate-180' : ''}`} />
                          </button>
                        </div>

                        {showAllSubjects && (
                          <div className="flex flex-wrap gap-1.5 pt-1 animate-in fade-in duration-100">
                            {otherSubjects.map((s) => {
                              const isSelected = aiPlanForm.subject_ids.includes(s.id);
                              return (
                                <button
                                  key={s.id}
                                  type="button"
                                  onClick={() => {
                                    setAiPlanForm((prev) => ({
                                      ...prev,
                                      subject_ids: isSelected
                                        ? prev.subject_ids.filter((id) => id !== s.id)
                                        : [...prev.subject_ids, s.id]
                                    }));
                                  }}
                                  className={`px-2.5 py-1 rounded-lg text-xs font-medium border flex items-center gap-1.5 transition-all cursor-pointer ${
                                    isSelected
                                      ? 'bg-white border-[#72C9BE] text-[#13443e] shadow-xs'
                                      : 'bg-white/50 border-[#E7EAF0] text-[#8C95A3] hover:border-[#CBD5E1]'
                                  }`}
                                >
                                  <span
                                    className="w-2 h-2 rounded-full"
                                    style={{ backgroundColor: s.color || s.color_code || '#72C9BE' }}
                                  />
                                  <span>{s.name}</span>
                                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#EFF1F5] text-[#6E7785] font-normal">Other</span>
                                  {isSelected && <Check className="w-3 h-3 text-[#72C9BE]" />}
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Planning Style */}
              <div>
                <label className="block text-xs font-bold text-[#26313F] mb-1.5">Planning Style</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setAiPlanForm((prev) => ({ ...prev, planning_style: 'balanced' }))}
                    className={`p-3 text-left rounded-2xl border transition-all cursor-pointer ${
                      aiPlanForm.planning_style === 'balanced'
                        ? 'bg-[#72C9BE]/10 border-[#72C9BE] text-[#13443e] shadow-xs'
                        : 'bg-[#F7F8FC] border-[#E7EAF0] text-[#6E7785] hover:border-[#CBD5E1]'
                    }`}
                  >
                    <div className="font-bold text-xs flex items-center gap-1.5 mb-1">
                      <span>Balanced</span>
                      {aiPlanForm.planning_style === 'balanced' && <Check className="w-3.5 h-3.5 text-[#72C9BE]" />}
                    </div>
                    <p className="text-[11px] leading-snug opacity-80">
                      Distribute study time fairly across all selected subjects.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setAiPlanForm((prev) => ({ ...prev, planning_style: 'priority' }))}
                    className={`p-3 text-left rounded-2xl border transition-all cursor-pointer ${
                      aiPlanForm.planning_style === 'priority' || aiPlanForm.planning_style === 'priority_aware'
                        ? 'bg-[#72C9BE]/10 border-[#72C9BE] text-[#13443e] shadow-xs'
                        : 'bg-[#F7F8FC] border-[#E7EAF0] text-[#6E7785] hover:border-[#CBD5E1]'
                    }`}
                  >
                    <div className="font-bold text-xs flex items-center gap-1.5 mb-1">
                      <span>Priority-aware</span>
                      {(aiPlanForm.planning_style === 'priority' || aiPlanForm.planning_style === 'priority_aware') && (
                        <Check className="w-3.5 h-3.5 text-[#72C9BE]" />
                      )}
                    </div>
                    <p className="text-[11px] leading-snug opacity-80">
                      More time for upcoming exams, missed classes & recent topics.
                    </p>
                  </button>
                </div>
              </div>

              {/* Feasibility Warning */}
              {isTimeTight && (
                <div className="p-4 rounded-2xl bg-[#FFF9EB] border border-[#FDE68A] text-[#92400E] space-y-3 animate-in fade-in duration-150">
                  <div className="flex items-start gap-2.5">
                    <AlertCircle className="w-4 h-4 text-[#D97706] shrink-0 mt-0.5" />
                    <div className="space-y-1">
                      <div className="font-bold text-xs text-[#92400E]">
                        Your available study time may not be enough to cover everything properly.
                      </div>
                      <div className="text-[11px] text-[#A16207] leading-relaxed">
                        You have {availableHoursText} available for {candidateTopicsCount} topics.
                        <br />
                        MedPilot estimates about {neededHoursText} for thorough coverage.
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 pt-1 border-t border-[#FDE68A]/60">
                    <button
                      type="button"
                      onClick={() =>
                        setAiPlanForm((prev) => ({
                          ...prev,
                          study_hours: Math.max(1, (parseInt(prev.study_hours, 10) || 0) + 1)
                        }))
                      }
                      className="px-2.5 py-1.5 rounded-xl bg-white border border-[#FDE68A] text-[#92400E] text-[11px] font-bold hover:bg-[#FEF3C7] transition-colors cursor-pointer shadow-2xs"
                    >
                      Add More Study Time (+1h)
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setAiPlanForm((prev) => ({
                          ...prev,
                          plan_days: Math.min(30, (prev.plan_days || 2) + 1)
                        }))
                      }
                      className="px-2.5 py-1.5 rounded-xl bg-white border border-[#FDE68A] text-[#92400E] text-[11px] font-bold hover:bg-[#FEF3C7] transition-colors cursor-pointer shadow-2xs"
                    >
                      Add More Days (+1d)
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setAiPlanForm((prev) => ({
                          ...prev,
                          planning_style: 'priority'
                        }))
                      }
                      className="px-2.5 py-1.5 rounded-xl bg-white border border-[#FDE68A] text-[#92400E] text-[11px] font-bold hover:bg-[#FEF3C7] transition-colors cursor-pointer shadow-2xs"
                    >
                      Prioritize Important Topics
                    </button>
                    <button
                      type="button"
                      onClick={() => handleGenerateAiPlan(null, { quick_review_mode: true })}
                      className="px-2.5 py-1.5 rounded-xl bg-[#D97706] hover:bg-[#B45309] text-white text-[11px] font-bold transition-colors flex items-center gap-1 shadow-xs cursor-pointer"
                    >
                      <Zap className="w-3 h-3" />
                      <span>Create Quick Review Plan</span>
                    </button>
                  </div>
                  <div className="text-[10px] text-[#A16207] italic flex items-center gap-1">
                    <Info className="w-3 h-3 text-[#D97706]" />
                    <span>Quick Review: This plan gives broad coverage, not deep study.</span>
                  </div>
                </div>
              )}

              {/* Modal Footer / Submit Buttons */}
              <div className="flex justify-end gap-2 pt-3 border-t border-[#E7EAF0]">
                <button
                  type="button"
                  onClick={() => setAiPlanModal(false)}
                  className="px-4 py-2 rounded-xl text-[#6E7785] hover:text-[#26313F] transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={aiGenerating || totalAvailableMinutes <= 0}
                  className="px-5 py-2.5 rounded-xl bg-[#72C9BE] hover:bg-[#5db8ad] text-[#13443e] font-semibold shadow-sm disabled:opacity-50 transition-all cursor-pointer flex items-center gap-2"
                >
                  {aiGenerating ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin text-[#13443e]" />
                      <span>Scheduling Tasks...</span>
                    </>
                  ) : (
                    <span>Create Plan</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* SNOOZE / LATER MODAL */}
      {/* ======================================================== */}
      {snoozeModalTopic && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#26313F]/30 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white border border-[#E7EAF0] rounded-3xl max-w-sm w-full p-6 space-y-4 shadow-float">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <div>
                <h3 className="text-base font-bold text-[#26313F]">Postpone Topic</h3>
                <p className="text-[11px] text-[#6E7785] mt-0.5">
                  Choose when to reschedule catch-up study for this topic.
                </p>
              </div>
              <button
                onClick={() => setSnoozeModalTopic(null)}
                className="p-1.5 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 bg-[#F8FAFC] rounded-2xl border border-[#E2E8F0]">
              <span className="text-[10px] uppercase font-bold text-[#64748B] block tracking-wider">
                {snoozeModalTopic.subjectName || snoozeModalTopic.subject?.name || 'Subject'}
              </span>
              <p className="text-xs font-bold text-[#1E293B] mt-0.5">
                Topic: {snoozeModalTopic.title || snoozeModalTopic.name}
              </p>
              {snoozeModalTopic.occurrenceDate && (
                <p className="text-[11px] text-[#94A3B8] mt-0.5">
                  Missed on {formatMissedDate(snoozeModalTopic.occurrenceDate)}
                </p>
              )}
            </div>

            <div className="space-y-2 text-xs">
              <label className="block font-semibold text-[#26313F]">Postpone Until:</label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { id: 'tomorrow', label: 'Tomorrow' },
                  { id: '3_days', label: 'In 3 Days' },
                  { id: '1_week', label: 'In 1 Week' },
                  { id: 'custom', label: 'Custom Date' }
                ].map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => setSnoozePreset(preset.id)}
                    className={`p-2.5 rounded-xl border text-xs font-semibold text-center transition-all cursor-pointer ${
                      snoozePreset === preset.id
                        ? 'bg-[#72C9BE]/15 border-[#72C9BE] text-[#13443e] shadow-2xs'
                        : 'bg-white border-[#E7EAF0] text-[#64748B] hover:border-[#CBD5E1]'
                    }`}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>

              {snoozePreset === 'custom' && (
                <div className="pt-2 animate-in fade-in duration-100">
                  <label className="block text-[11px] font-medium text-[#64748B] mb-1">Pick a Target Date:</label>
                  <input
                    type="date"
                    min={new Date(Date.now() + 86400000).toISOString().split('T')[0]}
                    value={customSnoozeDate}
                    onChange={(e) => setCustomSnoozeDate(e.target.value)}
                    className="w-full bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl px-3 py-2 text-[#26313F] text-xs focus:border-[#72C9BE] focus:outline-none"
                  />
                </div>
              )}
            </div>

            <div className="p-2.5 rounded-xl bg-[#EFF6FF] border border-[#BFDBFE]/60 text-[11px] text-[#1E40AF]">
              Target Snooze Date: <strong>{formatDateLabel(getCalculatedSnoozeDate())}</strong>. MedPilot will not schedule this topic before that date.
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-[#E7EAF0]">
              <button
                type="button"
                onClick={() => setSnoozeModalTopic(null)}
                className="px-3.5 py-2 text-xs font-semibold text-[#6E7785] hover:bg-[#F2F5F8] rounded-xl transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() =>
                  handleUpdateTopicStatus(snoozeModalTopic.id, 'later', getCalculatedSnoozeDate(), null)
                }
                className="px-4 py-2 bg-[#72C9BE] hover:bg-[#5db8ad] text-[#13443e] text-xs font-bold rounded-xl transition-all shadow-sm cursor-pointer"
              >
                Save Postpone
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* SKIP TOPIC MODAL */}
      {/* ======================================================== */}
      {skipModalTopic && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#26313F]/30 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white border border-[#E7EAF0] rounded-3xl max-w-sm w-full p-6 space-y-4 shadow-float">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <div>
                <h3 className="text-base font-bold text-[#26313F]">Skip Topic</h3>
                <p className="text-[11px] text-[#6E7785] mt-0.5">
                  Exclude this topic from automated study scheduling.
                </p>
              </div>
              <button
                onClick={() => setSkipModalTopic(null)}
                className="p-1.5 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 bg-[#F8FAFC] rounded-2xl border border-[#E2E8F0]">
              <span className="text-[10px] uppercase font-bold text-[#64748B] block tracking-wider">
                {skipModalTopic.subjectName || skipModalTopic.subject?.name || 'Subject'}
              </span>
              <p className="text-xs font-bold text-[#1E293B] mt-0.5">
                Topic: {skipModalTopic.title || skipModalTopic.name}
              </p>
              {skipModalTopic.occurrenceDate && (
                <p className="text-[11px] text-[#94A3B8] mt-0.5">
                  Missed on {formatMissedDate(skipModalTopic.occurrenceDate)}
                </p>
              )}
            </div>

            <div className="space-y-2 text-xs">
              <label className="block font-semibold text-[#26313F]">Reason for Skipping:</label>
              <div className="space-y-2">
                {[
                  {
                    id: 'skip_plan_only',
                    label: 'Skip this plan only',
                    desc: 'Omit for now; will be eligible again in future study plans.'
                  },
                  {
                    id: 'already_know',
                    label: 'I already know this topic',
                    desc: 'Mark as already studied or mastered.'
                  },
                  {
                    id: 'dont_suggest',
                    label: "Don't suggest automatically",
                    desc: 'Keep in class records without recommending study tasks.'
                  }
                ].map((reason) => (
                  <button
                    key={reason.id}
                    type="button"
                    onClick={() => setSelectedSkipReason(reason.id)}
                    className={`w-full p-3 text-left rounded-2xl border transition-all cursor-pointer ${
                      selectedSkipReason === reason.id
                        ? 'bg-[#72C9BE]/10 border-[#72C9BE] text-[#13443e] shadow-2xs'
                        : 'bg-[#F8FAFC] border-[#E2E8F0] text-[#64748B] hover:border-[#CBD5E1]'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-[#1E293B]">{reason.label}</span>
                      {selectedSkipReason === reason.id && <Check className="w-3.5 h-3.5 text-[#72C9BE]" />}
                    </div>
                    <p className="text-[11px] text-[#64748B] mt-0.5 leading-snug">{reason.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            <p className="text-[11px] text-[#94A3B8] leading-relaxed">
              &bull; This topic will remain in your class history and can be restored at any time.
            </p>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-[#E7EAF0]">
              <button
                type="button"
                onClick={() => setSkipModalTopic(null)}
                className="px-3.5 py-2 text-xs font-semibold text-[#6E7785] hover:bg-[#F2F5F8] rounded-xl transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() =>
                  handleUpdateTopicStatus(skipModalTopic.id, 'skip', null, selectedSkipReason)
                }
                className="px-4 py-2 bg-[#FEE2E2] hover:bg-[#FCA5A5] text-[#991B1B] text-xs font-bold rounded-xl transition-all shadow-sm cursor-pointer"
              >
                Confirm Skip
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Pastel Toast Notification (replaces browser alerts) */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 max-w-md w-[calc(100vw-3rem)] animate-in fade-in slide-in-from-bottom-2 duration-200">
          <div
            className={`p-4 rounded-2xl border shadow-float flex items-start gap-3 ${
              toast.type === 'error'
                ? 'bg-[#FDF2F4] border-[#EABFC5] text-[#69242E]'
                : toast.type === 'info'
                ? 'bg-[#F0F7FD] border-[#B7D4F4] text-[#1E3A8A]'
                : 'bg-[#F0FAF7] border-[#CFEDE7] text-[#1A4B43]'
            }`}
          >
            <div className="shrink-0 mt-0.5">
              {toast.type === 'error' ? (
                <AlertCircle className="w-4 h-4 text-[#C93B52]" />
              ) : toast.type === 'info' ? (
                <Info className="w-4 h-4 text-[#2563EB]" />
              ) : (
                <CheckCircle2 className="w-4 h-4 text-[#0D9488]" />
              )}
            </div>
            <div className="flex-1 text-xs font-medium leading-relaxed">
              {toast.message}
            </div>
            <button
              onClick={() => setToast(null)}
              className="shrink-0 p-1 rounded-lg hover:bg-black/5 transition-colors opacity-70 hover:opacity-100 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
