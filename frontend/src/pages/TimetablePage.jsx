import React, { useState, useEffect } from 'react';
import {
  Calendar,
  Clock,
  Plus,
  MoreVertical,
  Edit2,
  Trash2,
  ChevronLeft,
  ChevronRight,
  BookOpen,
  MapPin,
  UserCheck,
  FileUp,
  RotateCcw,
  Check,
  X,
  CalendarCheck
} from 'lucide-react';
import { apiRequest } from '../api/client';
import ClassCheckInModal from '../components/ClassCheckInModal';
import TimetableImportModal from '../components/TimetableImportModal';
import TimetableReviewModal from '../components/TimetableReviewModal';
import SubjectManagementModal from '../components/SubjectManagementModal';

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

export default function TimetablePage() {
  const [currentWeekStart, setCurrentWeekStart] = useState(() => {
    const now = new Date();
    const day = now.getDay();
    const diff = now.getDate() - day + (day === 0 ? -6 : 1); // Monday
    const monday = new Date(now.setDate(diff));
    return monday.toISOString().split('T')[0];
  });

  const [subjects, setSubjects] = useState([]);
  const [occurrences, setOccurrences] = useState([]);
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);

  // Active dropdown menu by occurrence ID
  const [activeMenuId, setActiveMenuId] = useState(null);

  // Modals
  const [checkInModalOcc, setCheckInModalOcc] = useState(null);
  const [addClassModal, setAddClassModal] = useState(false);
  const [editModalOcc, setEditModalOcc] = useState(null);
  const [topicModalOcc, setTopicModalOcc] = useState(null);
  const [newTopicTitle, setNewTopicTitle] = useState('');
  const [editingTopicId, setEditingTopicId] = useState(null);
  const [editingTopicTitle, setEditingTopicTitle] = useState('');
  const [importModal, setImportModal] = useState(false);
  const [reviewModal, setReviewModal] = useState(false);
  const [importPreviewData, setImportPreviewData] = useState(null);
  const [timetableSettings, setTimetableSettings] = useState({ timetable_start_date: null });
  const [startDateModal, setStartDateModal] = useState(false);
  const [selectedStartDate, setSelectedStartDate] = useState('');
  const [savingSettings, setSavingSettings] = useState(false);

  // Add Class Form State
  const [addForm, setAddForm] = useState({
    type: 'recurring', // 'recurring' or 'extra'
    subject_id: '',
    day_of_week: 0,
    date: new Date().toISOString().split('T')[0],
    effective_from: new Date().toISOString().split('T')[0],
    start_time: '09:00',
    end_time: '10:00',
    faculty: '',
    room: '',
    topics: ''
  });

  // Edit Class Form
  const [editForm, setEditForm] = useState({
    scope: 'this_only', // 'this_only' or 'future'
    subject_id: '',
    date: '',
    start_time: '09:00',
    end_time: '10:00',
    faculty: '',
    room: '',
    notes: ''
  });

  // Subject Management Modal State
  const [subjectModalConfig, setSubjectModalConfig] = useState({
    isOpen: false,
    subjectId: null,
    viewMode: 'list',
    context: null,
    slotIndex: null
  });

  const openEditSubject = (subjectId, context = null, slotIndex = null) => {
    setSubjectModalConfig({
      isOpen: true,
      subjectId,
      viewMode: 'edit',
      context,
      slotIndex
    });
  };

  const openAddSubject = (context = null, slotIndex = null) => {
    setSubjectModalConfig({
      isOpen: true,
      subjectId: null,
      viewMode: 'add',
      context,
      slotIndex
    });
  };

  const handleSubjectsChanged = async (savedSubj) => {
    await loadData();
    if (savedSubj && savedSubj.id) {
      if (subjectModalConfig.context === 'add') {
        setAddForm((prev) => ({ ...prev, subject_id: savedSubj.id }));
      } else if (subjectModalConfig.context === 'edit') {
        setEditForm((prev) => ({ ...prev, subject_id: savedSubj.id }));
      }
    }
  };

  // Close menus on outside click
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (!e.target.closest('[data-dropdown-menu]')) {
        setActiveMenuId(null);
      }
    };
    document.addEventListener('click', handleOutsideClick);
    return () => document.removeEventListener('click', handleOutsideClick);
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const subjs = await apiRequest('/subjects/');
      setSubjects(subjs || []);

      if (subjs && subjs.length > 0 && !addForm.subject_id) {
        setAddForm(prev => ({ ...prev, subject_id: subjs[0].id }));
      }

      // Calculate week end date
      const startD = new Date(currentWeekStart);
      const endD = new Date(startD);
      endD.setDate(startD.getDate() + 6);
      const endStr = endD.toISOString().split('T')[0];

      const [occData, ruleData, settingsData] = await Promise.all([
        apiRequest(`/timetable/occurrences?start_date=${currentWeekStart}&end_date=${endStr}`),
        apiRequest('/timetable/rules'),
        apiRequest('/timetable/settings').catch(() => null)
      ]);

      setOccurrences(occData || []);
      setRules(ruleData || []);
      if (settingsData) {
        setTimetableSettings(settingsData);
      }
      return occData || [];
    } catch (err) {
      console.error('Error loading timetable data:', err);
      return [];
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [currentWeekStart]);

  const changeWeek = (offsetDays) => {
    const d = new Date(currentWeekStart);
    d.setDate(d.getDate() + offsetDays);
    setCurrentWeekStart(d.toISOString().split('T')[0]);
  };

  const resetToCurrentWeek = () => {
    const now = new Date();
    const day = now.getDay();
    const diff = now.getDate() - day + (day === 0 ? -6 : 1);
    const monday = new Date(now.setDate(diff));
    setCurrentWeekStart(monday.toISOString().split('T')[0]);
  };

  // Toggle cancellation (reversible)
  const handleToggleCancel = async (occ) => {
    setActiveMenuId(null);
    try {
      await apiRequest(`/timetable/occurrences/${occ.id}/toggle-cancel`, {
        method: 'POST'
      });
      loadData();
    } catch (err) {
      alert(`Failed to change class status: ${err.message}`);
    }
  };

  // Open Add Class Modal
  const openAddClassModal = (initialDay = null, initialDate = null) => {
    const todayDayIndex = (new Date().getDay() + 6) % 7;
    const targetDay = initialDay !== null ? initialDay : todayDayIndex;

    let targetDate = initialDate;
    if (!targetDate) {
      const d = new Date(currentWeekStart);
      d.setDate(d.getDate() + targetDay);
      targetDate = d.toISOString().split('T')[0];
    }

    const todayStr = new Date().toISOString().split('T')[0];

    setAddForm({
      type: 'recurring',
      subject_id: subjects[0]?.id || '',
      day_of_week: targetDay,
      date: targetDate,
      effective_from: todayStr,
      start_time: '09:00',
      end_time: '10:00',
      faculty: '',
      room: '',
      topics: ''
    });
    setAddClassModal(true);
  };

  // Save Schedule Start Date Settings
  const handleSaveStartDate = async (e) => {
    e.preventDefault();
    setSavingSettings(true);
    try {
      const updated = await apiRequest('/timetable/settings', {
        method: 'PATCH',
        body: JSON.stringify({ timetable_start_date: selectedStartDate || null })
      });
      setTimetableSettings(updated);
      setStartDateModal(false);
      await loadData();
    } catch (err) {
      alert(`Failed to update schedule start date: ${err.message}`);
    } finally {
      setSavingSettings(false);
    }
  };

  // Add Class Submit
  const handleAddClassSubmit = async (e) => {
    e.preventDefault();
    if (!addForm.subject_id) {
      alert('Please select a subject.');
      return;
    }
    try {
      if (addForm.type === 'recurring') {
        await apiRequest('/timetable/rules', {
          method: 'POST',
          body: JSON.stringify({
            subject_id: addForm.subject_id,
            day_of_week: parseInt(addForm.day_of_week, 10),
            start_time: addForm.start_time.length === 5 ? `${addForm.start_time}:00` : addForm.start_time,
            end_time: addForm.end_time.length === 5 ? `${addForm.end_time}:00` : addForm.end_time,
            faculty: addForm.faculty || '',
            room: addForm.room || '',
            effective_from: addForm.effective_from || new Date().toISOString().split('T')[0]
          })
        });
      } else {
        await apiRequest('/timetable/occurrences', {
          method: 'POST',
          body: JSON.stringify({
            subject_id: addForm.subject_id,
            date: addForm.date,
            start_time: addForm.start_time.length === 5 ? `${addForm.start_time}:00` : addForm.start_time,
            end_time: addForm.end_time.length === 5 ? `${addForm.end_time}:00` : addForm.end_time,
            faculty: addForm.faculty || '',
            room: addForm.room || '',
            topics: addForm.topics ? addForm.topics.split(',').map(t => t.trim()).filter(Boolean) : []
          })
        });
      }
      setAddClassModal(false);
      loadData();
    } catch (err) {
      alert(`Error creating class: ${err.message}`);
    }
  };

  // Open Edit Modal
  const openEditModal = (occ) => {
    setActiveMenuId(null);
    setEditModalOcc(occ);
    setEditForm({
      scope: 'this_only',
      subject_id: occ.subject_id || '',
      date: occ.date || '',
      start_time: occ.start_time ? occ.start_time.slice(0, 5) : '09:00',
      end_time: occ.end_time ? occ.end_time.slice(0, 5) : '10:00',
      faculty: occ.faculty || '',
      room: occ.room || '',
      status: occ.status || 'scheduled',
      notes: occ.notes || ''
    });
  };

  // Submit Edit Form
  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editModalOcc) return;

    try {
      const formatTime = (t) => {
        if (!t) return '09:00:00';
        const parts = t.split(':');
        const hh = (parts[0] || '09').padStart(2, '0');
        const mm = (parts[1] || '00').padStart(2, '0');
        const ss = (parts[2] || '00').padStart(2, '0');
        return `${hh}:${mm}:${ss}`;
      };

      const startTime = formatTime(editForm.start_time);
      const endTime = formatTime(editForm.end_time);

      if (editForm.scope === 'future' && editModalOcc.rule_id) {
        await apiRequest(`/timetable/rules/${editModalOcc.rule_id}`, {
          method: 'PUT',
          body: JSON.stringify({
            subject_id: editForm.subject_id,
            start_time: startTime,
            end_time: endTime,
            faculty: editForm.faculty,
            room: editForm.room,
            start_from_date: editForm.date || editModalOcc.date,
            update_future_occurrences: true
          })
        });
      } else {
        await apiRequest(`/timetable/occurrences/${editModalOcc.id}`, {
          method: 'PUT',
          body: JSON.stringify({
            subject_id: editForm.subject_id,
            date: editForm.date,
            start_time: startTime,
            end_time: endTime,
            faculty: editForm.faculty,
            room: editForm.room,
            status: editForm.status || editModalOcc.status || 'scheduled',
            notes: editForm.notes
          })
        });
      }
      setEditModalOcc(null);
      await loadData();
    } catch (err) {
      const errorMsg = err?.message || (typeof err === 'object' ? JSON.stringify(err) : String(err));
      alert(`Failed to update class: ${errorMsg}`);
    }
  };

  // Delete Occurrence or Rule completely
  const handleDeleteClass = async (occ) => {
    setActiveMenuId(null);
    const isRecurring = Boolean(occ.rule_id);
    const confirmMsg = isRecurring
      ? 'Delete this recurring weekly class from your timetable?'
      : 'Delete this class from your timetable?';

    if (!window.confirm(confirmMsg)) return;

    try {
      if (isRecurring) {
        await apiRequest(`/timetable/rules/${occ.rule_id}`, { method: 'DELETE' });
      } else {
        await apiRequest(`/timetable/occurrences/${occ.id}`, { method: 'DELETE' });
      }
      loadData();
    } catch (err) {
      alert(`Failed to delete class: ${err.message}`);
    }
  };

  // Add Topic
  const handleAddTopic = async (e) => {
    e.preventDefault();
    if (!newTopicTitle.trim() || !topicModalOcc) return;
    try {
      await apiRequest(`/timetable/occurrences/${topicModalOcc.id}/topics`, {
        method: 'POST',
        body: JSON.stringify({ title: newTopicTitle.trim() })
      });
      setNewTopicTitle('');
      const freshOccs = await loadData();
      if (freshOccs && freshOccs.length > 0) {
        const freshOcc = freshOccs.find((o) => o.id === topicModalOcc.id);
        if (freshOcc) setTopicModalOcc(freshOcc);
      }
    } catch (err) {
      alert(err.message);
    }
  };

  // Update Topic
  const handleUpdateTopic = async (topicId) => {
    if (!editingTopicTitle.trim()) return;
    try {
      await apiRequest(`/timetable/topics/${topicId}`, {
        method: 'PUT',
        body: JSON.stringify({ title: editingTopicTitle.trim() })
      });
      setEditingTopicId(null);
      setEditingTopicTitle('');
      const freshOccs = await loadData();
      if (freshOccs && freshOccs.length > 0) {
        const freshOcc = freshOccs.find((o) => o.id === topicModalOcc.id);
        if (freshOcc) setTopicModalOcc(freshOcc);
      }
    } catch (err) {
      alert(err.message);
    }
  };

  // Delete Topic
  const handleDeleteTopic = async (topicId) => {
    try {
      await apiRequest(`/timetable/topics/${topicId}`, { method: 'DELETE' });
      const freshOccs = await loadData();
      if (freshOccs && freshOccs.length > 0) {
        const freshOcc = freshOccs.find((o) => o.id === topicModalOcc.id);
        if (freshOcc) setTopicModalOcc(freshOcc);
      }
    } catch (err) {
      alert(err.message);
    }
  };

  // Group occurrences by day
  const occurrencesByDate = {};
  occurrences.forEach((occ) => {
    if (!occurrencesByDate[occ.date]) occurrencesByDate[occ.date] = [];
    occurrencesByDate[occ.date].push(occ);
  });

  const todayStr = new Date().toISOString().split('T')[0];
  const nowTime = new Date().toTimeString().slice(0, 5);

  // Helper for lifecycle status
  const getClassLifecycle = (occ) => {
    if (occ.status === 'cancelled' || occ.attendance?.status === 'cancelled') {
      return { label: 'Cancelled', style: 'bg-[#E7EAF0] text-[#4B5563]', isCancelled: true };
    }
    const att = occ.attendance?.status;
    if (att === 'present') {
      return { label: 'Present', style: 'bg-[#CFEDE7] text-[#1A4B43]' };
    }
    if (att === 'absent') {
      return { label: 'Absent', style: 'bg-[#EABFC5]/40 text-[#69242E]' };
    }

    const isToday = occ.date === todayStr;
    const isPast = occ.date < todayStr;
    const startTime = occ.start_time.slice(0, 5);
    const endTime = occ.end_time.slice(0, 5);

    if (isPast || (isToday && endTime <= nowTime)) {
      return { label: 'Waiting Check-in', style: 'bg-[#F3DFAB]/60 text-[#6B4E17]', isPending: true };
    }
    if (isToday && startTime <= nowTime && nowTime < endTime) {
      return { label: 'In Progress', style: 'bg-[#CFEDE7] text-[#1A4B43]', isInProgress: true };
    }
    return { label: 'Upcoming', style: 'bg-[#B7D4F4]/30 text-[#1E3A8A]' };
  };

  return (
    <div className="space-y-6 pb-16">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#E7EAF0] pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#26313F] flex items-center gap-2.5">
            <span className="p-2 rounded-xl bg-[#CFEDE7] text-[#1A4B43]">
              <Calendar className="w-5 h-5 stroke-[2.2]" />
            </span>
            <span>Timetable</span>
          </h1>
          <p className="text-xs text-[#6E7785] mt-1">
            Your weekly schedule. Concluded classes prompt attendance automatically.
          </p>
        </div>

        {/* Primary Actions */}
        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={() => {
              setSelectedStartDate(timetableSettings.timetable_start_date || new Date().toISOString().split('T')[0]);
              setStartDateModal(true);
            }}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white hover:bg-[#F2F5F8] text-[#26313F] border border-[#E7EAF0] text-xs font-medium transition-all shadow-soft cursor-pointer"
            title="Configure Schedule Start Date"
          >
            <Calendar className="w-3.5 h-3.5 text-[#3D8C82]" />
            <span>
              {timetableSettings.timetable_start_date
                ? `Starts: ${timetableSettings.timetable_start_date}`
                : 'Schedule Starts: Today'}
            </span>
          </button>

          <button
            onClick={() => setSubjectModalConfig({ isOpen: true, subjectId: null, viewMode: 'list', context: null })}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white hover:bg-[#F2F5F8] text-[#26313F] border border-[#E7EAF0] text-xs font-medium transition-all shadow-soft cursor-pointer"
          >
            <BookOpen className="w-3.5 h-3.5 text-[#6E7785]" />
            <span>Subjects</span>
          </button>

          <button
            onClick={() => setImportModal(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white hover:bg-[#F2F5F8] text-[#26313F] border border-[#E7EAF0] text-xs font-semibold transition-all shadow-soft cursor-pointer"
          >
            <FileUp className="w-3.5 h-3.5 text-[#3D8C82]" />
            <span>Import Timetable</span>
          </button>

          <button
            onClick={() => openAddClassModal()}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#72C9BE] hover:bg-[#5db8ad] text-[#13443e] text-xs font-semibold shadow-sm transition-all cursor-pointer active:scale-98"
          >
            <Plus className="w-4 h-4 stroke-[2.5]" />
            <span>+ Add Class</span>
          </button>
        </div>
      </div>

      {/* Week Navigator */}
      <div className="flex items-center justify-between bg-white border border-[#E7EAF0] p-2.5 sm:p-3 rounded-2xl shadow-soft">
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => changeWeek(-7)}
            className="p-2 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] transition-colors"
            title="Previous Week"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <button
            onClick={resetToCurrentWeek}
            className="px-3 py-1.5 rounded-xl text-xs font-semibold text-[#1A4B43] bg-[#CFEDE7]/60 hover:bg-[#CFEDE7] transition-colors"
          >
            This Week
          </button>
        </div>

        <div className="text-center">
          <span className="text-xs sm:text-sm font-semibold text-[#26313F]">
            {new Date(currentWeekStart).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
            {' — '}
            {(() => {
              const d = new Date(currentWeekStart);
              d.setDate(d.getDate() + 6);
              return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
            })()}
          </span>
        </div>

        <button
          onClick={() => changeWeek(7)}
          className="p-2 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] transition-colors"
          title="Next Week"
        >
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>

      {/* 7-Day Timetable Columns */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {DAYS.map((dayName, dayIndex) => {
          const dayDate = new Date(currentWeekStart);
          dayDate.setDate(dayDate.getDate() + dayIndex);
          const dateStr = dayDate.toISOString().split('T')[0];
          const isToday = dateStr === todayStr;
          const dayOccs = occurrencesByDate[dateStr] || [];

          return (
            <div
              key={dateStr}
              className={`rounded-2xl border transition-all flex flex-col bg-white shadow-soft ${
                isToday
                  ? 'border-[#72C9BE] ring-1 ring-[#72C9BE]/30'
                  : 'border-[#E7EAF0]'
              }`}
            >
              {/* Day Column Header */}
              <div
                onClick={() => openAddClassModal(dayIndex, dateStr)}
                className={`p-3.5 border-b border-[#E7EAF0] flex items-center justify-between cursor-pointer rounded-t-2xl transition-colors ${
                  isToday ? 'bg-[#CFEDE7]/30' : 'hover:bg-[#F7F8FC]'
                }`}
                title={`Click to add class on ${dayName}`}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-[#26313F] text-sm">
                      {dayName}
                    </h3>
                    {isToday && (
                      <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-[#CFEDE7] text-[#1A4B43]">
                        Today
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-[#6E7785] mt-0.5">
                    {dayDate.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                  </p>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#F2F5F8] text-[#6E7785]">
                    {dayOccs.length}
                  </span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      openAddClassModal(dayIndex, dateStr);
                    }}
                    className="p-1 rounded-lg text-[#6E7785] hover:text-[#26313F] hover:bg-[#E7EAF0] transition-all cursor-pointer"
                    title={`Add class on ${dayName}`}
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Class Cards */}
              <div className="p-3 space-y-2.5 flex-1 flex flex-col justify-between">
                <div>
                  {dayOccs.length === 0 ? (
                    <div
                      onClick={() => openAddClassModal(dayIndex, dateStr)}
                      className="py-10 text-center text-xs text-[#8E97A6] flex flex-col items-center justify-center gap-2 cursor-pointer hover:bg-[#F7F8FC] rounded-xl transition-all border border-dashed border-transparent hover:border-[#E7EAF0]"
                    >
                      <span>No classes</span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          openAddClassModal(dayIndex, dateStr);
                        }}
                        className="inline-flex items-center gap-1 text-[11px] text-[#3D8C82] hover:underline font-semibold cursor-pointer py-1 px-2 rounded-lg bg-[#CFEDE7]/40 hover:bg-[#CFEDE7] transition-all"
                      >
                        <Plus className="w-3 h-3" />
                        <span>Add Class</span>
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {dayOccs.map((occ) => {
                        const lifecycle = getClassLifecycle(occ);
                        const isCancelled = lifecycle.isCancelled;

                        return (
                          <div
                            key={occ.id}
                            className={`p-3 rounded-xl border transition-all relative ${
                              isCancelled
                                ? 'bg-[#F7F8FC] border-[#E7EAF0] opacity-60'
                                : 'bg-white border-[#E7EAF0] hover:border-[#72C9BE]/50 shadow-soft'
                            }`}
                          >
                            {/* Card Top: Subject & Time */}
                            <div className="flex items-start justify-between gap-2">
                              <div className="space-y-0.5 flex-1 min-w-0">
                                <div className="text-[11px] font-mono font-medium text-[#6E7785] flex items-center gap-1">
                                  <Clock className="w-3 h-3 text-[#72C9BE]" />
                                  <span>{occ.start_time.slice(0, 5)} – {occ.end_time.slice(0, 5)}</span>
                                </div>
                                <h4 className="font-bold text-[#26313F] text-sm truncate block mt-0.5">
                                  {occ.subject?.name || 'Class'}
                                </h4>
                              </div>

                              {/* Subtle ⋯ Context Menu Button */}
                              <div className="relative" data-dropdown-menu>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setActiveMenuId(activeMenuId === occ.id ? null : occ.id);
                                  }}
                                  className="p-1 rounded-lg text-[#8E97A6] hover:text-[#26313F] hover:bg-[#F2F5F8] transition-colors"
                                  title="Class Options"
                                >
                                  <MoreVertical className="w-3.5 h-3.5" />
                                </button>

                                {/* Dropdown Menu Popover */}
                                {activeMenuId === occ.id && (
                                  <div
                                    className="absolute right-0 top-7 z-30 w-44 rounded-xl bg-white border border-[#E7EAF0] shadow-card py-1 text-xs text-[#26313F] animate-in fade-in zoom-in-95 duration-100"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <button
                                      onClick={() => {
                                        setActiveMenuId(null);
                                        setCheckInModalOcc(occ);
                                      }}
                                      className="w-full text-left px-3 py-1.5 hover:bg-[#F2F5F8] flex items-center gap-2 text-[#1A4B43] font-medium"
                                    >
                                      <CalendarCheck className="w-3.5 h-3.5 text-[#72C9BE]" />
                                      <span>Check In</span>
                                    </button>

                                    <button
                                      onClick={() => openEditModal(occ)}
                                      className="w-full text-left px-3 py-1.5 hover:bg-[#F2F5F8] flex items-center gap-2 text-[#26313F]"
                                    >
                                      <Edit2 className="w-3.5 h-3.5 text-[#6E7785]" />
                                      <span>Edit Class</span>
                                    </button>

                                    <button
                                      onClick={() => handleToggleCancel(occ)}
                                      className="w-full text-left px-3 py-1.5 hover:bg-[#F2F5F8] flex items-center gap-2 text-[#6E7785]"
                                    >
                                      <RotateCcw className="w-3.5 h-3.5" />
                                      <span>{isCancelled ? 'Restore' : 'Cancel Class'}</span>
                                    </button>

                                    <button
                                      onClick={() => {
                                        setActiveMenuId(null);
                                        setTopicModalOcc(occ);
                                      }}
                                      className="w-full text-left px-3 py-1.5 hover:bg-[#F2F5F8] flex items-center gap-2 text-[#26313F]"
                                    >
                                      <BookOpen className="w-3.5 h-3.5 text-[#6E7785]" />
                                      <span>Topics</span>
                                    </button>

                                    <div className="border-t border-[#E7EAF0] my-1" />

                                    <button
                                      onClick={() => handleDeleteClass(occ)}
                                      className="w-full text-left px-3 py-1.5 hover:bg-[#EABFC5]/20 text-[#69242E] flex items-center gap-2 font-medium"
                                    >
                                      <Trash2 className="w-3.5 h-3.5" />
                                      <span>Delete Class</span>
                                    </button>
                                  </div>
                                )}
                              </div>
                            </div>

                            {/* Room & Faculty Details */}
                            {(occ.room || occ.faculty) && (
                              <div className="flex flex-wrap items-center gap-2 text-[11px] text-[#6E7785] mt-1.5">
                                {occ.faculty && (
                                  <span className="truncate max-w-[140px] font-medium">{occ.faculty}</span>
                                )}
                                {occ.room && occ.faculty && <span>•</span>}
                                {occ.room && (
                                  <span className="truncate max-w-[120px]">{occ.room}</span>
                                )}
                              </div>
                            )}

                            {/* Topics Section */}
                            {occ.topics && occ.topics.length > 0 ? (
                              <div className="mt-1.5 space-y-1">
                                <div className="flex flex-wrap items-center gap-1">
                                  {occ.topics.map((t) => (
                                    <button
                                      key={t.id}
                                      type="button"
                                      onClick={() => setTopicModalOcc(occ)}
                                      title="Click to view or edit topics"
                                      className="text-[10px] px-2 py-0.5 rounded-md bg-[#CFEDE7]/50 hover:bg-[#CFEDE7] text-[#1A4B43] border border-[#72C9BE]/40 truncate max-w-full font-medium transition-colors cursor-pointer text-left"
                                    >
                                      {t.title}
                                    </button>
                                  ))}
                                  <button
                                    type="button"
                                    onClick={() => setTopicModalOcc(occ)}
                                    className="p-1 rounded-md text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] text-[10px] flex items-center gap-0.5 font-medium cursor-pointer"
                                    title="Edit topics"
                                  >
                                    <Edit2 className="w-2.5 h-2.5" />
                                  </button>
                                </div>
                              </div>
                            ) : !isCancelled && (lifecycle.label === 'Present' || lifecycle.label === 'Absent' || occ.date < todayStr || (occ.date === todayStr && occ.end_time.slice(0, 5) <= nowTime)) ? (
                              <div className="flex items-center justify-between gap-1.5 mt-1.5 pt-1">
                                <span className="inline-flex items-center gap-1 text-[10px] text-[#8E97A6] font-medium bg-[#F2F5F8] border border-dashed border-[#CBD5E1] px-2 py-0.5 rounded-full">
                                  Topic not added
                                </span>
                                <button
                                  type="button"
                                  onClick={() => setTopicModalOcc(occ)}
                                  className="inline-flex items-center gap-0.5 text-[11px] font-semibold text-[#1A4B43] hover:text-[#0f302b] hover:underline cursor-pointer"
                                >
                                  <Plus className="w-3 h-3" />
                                  <span>Add Topic</span>
                                </button>
                              </div>
                            ) : null}

                            {/* Card Bottom: Status Badge & Quick Check-in */}
                            <div className="flex items-center justify-between pt-2 mt-2 border-t border-[#F2F5F8]">
                              <span
                                className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${lifecycle.style}`}
                              >
                                {lifecycle.label}
                              </span>

                              {lifecycle.isPending && (
                                <button
                                  onClick={() => setCheckInModalOcc(occ)}
                                  className="px-2.5 py-0.5 rounded-lg bg-[#CFEDE7] hover:bg-[#b5e7dc] text-[#1A4B43] text-[11px] font-semibold transition-all flex items-center gap-1 cursor-pointer"
                                >
                                  <span>Check In</span>
                                </button>
                              )}

                              {isCancelled && (
                                <button
                                  type="button"
                                  onClick={() => handleToggleCancel(occ)}
                                  className="px-2 py-0.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-[11px] font-medium transition-all flex items-center gap-1 cursor-pointer"
                                  title="Undo cancellation"
                                >
                                  <RotateCcw className="w-3 h-3 text-[#6E7785]" />
                                  <span>Undo Cancel</span>
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Bottom quick button to add class */}
                {dayOccs.length > 0 && (
                  <button
                    type="button"
                    onClick={() => openAddClassModal(dayIndex, dateStr)}
                    className="w-full py-1.5 px-2 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] text-xs font-medium flex items-center justify-center gap-1 transition-all cursor-pointer mt-2"
                  >
                    <Plus className="w-3 h-3" />
                    <span>Add to {dayName}</span>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* MODAL 1: Add Class Modal */}
      {addClassModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-[#26313F]/30 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white border border-[#E7EAF0] rounded-3xl max-w-lg w-full max-h-[90vh] flex flex-col p-5 sm:p-6 shadow-float overflow-hidden">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-[#CFEDE7] text-[#1A4B43]">
                  <CalendarCheck className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-[#26313F]">Add Class</h3>
                  <p className="text-xs text-[#6E7785]">
                    Add a weekly recurring class or a single extra lecture
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setAddClassModal(false)}
                className="p-1.5 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto pr-1 space-y-4 text-xs mt-4">
              <form id="single-class-form" onSubmit={handleAddClassSubmit} className="space-y-4">
                <div className="grid grid-cols-2 p-1 rounded-2xl bg-[#F7F8FC] border border-[#E7EAF0] text-center font-semibold">
                  <button
                    type="button"
                    onClick={() => setAddForm({ ...addForm, type: 'recurring' })}
                    className={`py-2 rounded-xl transition-all cursor-pointer ${
                      addForm.type === 'recurring'
                        ? 'bg-white text-[#26313F] shadow-sm font-bold'
                        : 'text-[#6E7785] hover:text-[#26313F]'
                    }`}
                  >
                    Weekly Recurring
                  </button>
                  <button
                    type="button"
                    onClick={() => setAddForm({ ...addForm, type: 'extra' })}
                    className={`py-2 rounded-xl transition-all cursor-pointer ${
                      addForm.type === 'extra'
                        ? 'bg-white text-[#26313F] shadow-sm font-bold'
                        : 'text-[#6E7785] hover:text-[#26313F]'
                    }`}
                  >
                    Single / Extra Class
                  </button>
                </div>

                {/* Subject */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-[#26313F] font-semibold">Subject</label>
                    <div className="flex items-center gap-2">
                      {addForm.subject_id && (
                        <button
                          type="button"
                          onClick={() => openEditSubject(addForm.subject_id, 'add')}
                          className="text-[11px] text-[#3D8C82] hover:underline font-medium flex items-center gap-1 cursor-pointer"
                        >
                          <Edit2 className="w-3 h-3" />
                          <span>Edit Subject</span>
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => openAddSubject('add')}
                        className="text-[11px] text-[#6E7785] hover:text-[#26313F] font-medium flex items-center gap-1 cursor-pointer"
                      >
                        <Plus className="w-3 h-3" />
                        <span>+ New Subject</span>
                      </button>
                    </div>
                  </div>
                  <select
                    value={addForm.subject_id}
                    onChange={(e) => setAddForm({ ...addForm, subject_id: e.target.value })}
                    className="w-full py-2.5 px-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-[#26313F] text-sm focus:border-[#72C9BE] focus:outline-none"
                  >
                    {subjects.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} {s.code ? `(${s.code})` : ''}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Day of Week OR Date */}
                {addForm.type === 'recurring' ? (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-[#26313F] font-semibold mb-1">Day of the Week</label>
                      <select
                        value={addForm.day_of_week}
                        onChange={(e) => setAddForm({ ...addForm, day_of_week: e.target.value })}
                        className="w-full py-2.5 px-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-[#26313F] text-sm focus:border-[#72C9BE] focus:outline-none"
                      >
                        {DAYS.map((d, idx) => (
                          <option key={idx} value={idx}>Every {d}</option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-[#26313F] font-semibold mb-1 flex items-center justify-between">
                        <span>Schedule starts from</span>
                        <span className="text-[11px] font-normal text-[#6E7785]">Default: Today</span>
                      </label>
                      <input
                        type="date"
                        required
                        value={addForm.effective_from}
                        onChange={(e) => setAddForm({ ...addForm, effective_from: e.target.value })}
                        className="w-full py-2 px-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-[#26313F] text-sm focus:border-[#72C9BE] focus:outline-none"
                      />
                      <p className="text-[11px] text-[#6E7785] mt-1">
                        Recurring classes and attendance check-ins will only be tracked on or after this date.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div>
                    <label className="block text-[#26313F] font-semibold mb-1">Class Date</label>
                    <input
                      type="date"
                      required
                      value={addForm.date}
                      onChange={(e) => setAddForm({ ...addForm, date: e.target.value })}
                      className="w-full py-2 px-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-[#26313F] text-sm focus:border-[#72C9BE] focus:outline-none"
                    />
                  </div>
                )}

                {/* Time Slot */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[#26313F] font-semibold mb-1">Start Time</label>
                    <input
                      type="time"
                      required
                      value={addForm.start_time}
                      onChange={(e) => setAddForm({ ...addForm, start_time: e.target.value })}
                      className="w-full py-2 px-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-[#26313F] text-sm focus:border-[#72C9BE] focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-[#26313F] font-semibold mb-1">End Time</label>
                    <input
                      type="time"
                      required
                      value={addForm.end_time}
                      onChange={(e) => setAddForm({ ...addForm, end_time: e.target.value })}
                      className="w-full py-2 px-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-[#26313F] text-sm focus:border-[#72C9BE] focus:outline-none"
                    />
                  </div>
                </div>

                {/* Faculty & Room */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[#26313F] font-semibold mb-1">Faculty (Optional)</label>
                    <input
                      type="text"
                      value={addForm.faculty}
                      onChange={(e) => setAddForm({ ...addForm, faculty: e.target.value })}
                      placeholder="e.g. Dr. Verma"
                      className="w-full py-2 px-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-[#26313F] text-sm focus:border-[#72C9BE] focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-[#26313F] font-semibold mb-1">Room (Optional)</label>
                    <input
                      type="text"
                      value={addForm.room}
                      onChange={(e) => setAddForm({ ...addForm, room: e.target.value })}
                      placeholder="e.g. LT-2, Lab 3"
                      className="w-full py-2 px-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-[#26313F] text-sm focus:border-[#72C9BE] focus:outline-none"
                    />
                  </div>
                </div>

                {/* Topics */}
                {addForm.type === 'extra' && (
                  <div>
                    <label className="block text-[#26313F] font-semibold mb-1">Topics (comma-separated)</label>
                    <input
                      type="text"
                      value={addForm.topics}
                      onChange={(e) => setAddForm({ ...addForm, topics: e.target.value })}
                      placeholder="e.g. Cranial Nerves, Brainstem"
                      className="w-full py-2 px-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-[#26313F] text-sm focus:border-[#72C9BE] focus:outline-none"
                    />
                  </div>
                )}
              </form>
            </div>

            {/* Modal Footer */}
            <div className="flex justify-end gap-2 pt-3 border-t border-[#E7EAF0] mt-2">
              <button
                type="button"
                onClick={() => setAddClassModal(false)}
                className="px-4 py-2 rounded-xl text-[#6E7785] hover:text-[#26313F] cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                form="single-class-form"
                className="px-5 py-2.5 rounded-xl bg-[#72C9BE] hover:bg-[#5db8ad] text-[#13443e] font-semibold shadow-sm cursor-pointer"
              >
                Save Class
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: Edit Class Modal */}
      {editModalOcc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#26313F]/30 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white border border-[#E7EAF0] rounded-3xl max-w-md w-full p-6 space-y-4 shadow-float">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <h3 className="text-base font-bold text-[#26313F] flex items-center gap-2">
                <Edit2 className="w-4 h-4 text-[#72C9BE]" />
                <span>Edit Class</span>
              </h3>
              <button
                onClick={() => setEditModalOcc(null)}
                className="p-1.5 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="space-y-4 text-xs">
              {editModalOcc.rule_id && (
                <div className="p-3 rounded-2xl bg-[#F7F8FC] border border-[#E7EAF0] space-y-2">
                  <label className="block text-[#26313F] font-semibold">Update Scope</label>
                  <div className="space-y-1.5">
                    <label className="flex items-center gap-2 text-[#26313F] cursor-pointer">
                      <input
                        type="radio"
                        name="editScope"
                        checked={editForm.scope === 'this_only'}
                        onChange={() => setEditForm({ ...editForm, scope: 'this_only' })}
                        className="text-[#72C9BE] focus:ring-[#72C9BE]"
                      />
                      <span>Only this single occurrence ({editModalOcc.date})</span>
                    </label>
                    <label className="flex items-center gap-2 text-[#26313F] cursor-pointer">
                      <input
                        type="radio"
                        name="editScope"
                        checked={editForm.scope === 'future'}
                        onChange={() => setEditForm({ ...editForm, scope: 'future' })}
                        className="text-[#72C9BE] focus:ring-[#72C9BE]"
                      />
                      <span>This and all future weekly classes</span>
                    </label>
                  </div>
                </div>
              )}

              {/* Subject */}
              <div>
                <label className="block text-[#26313F] font-semibold mb-1">Subject</label>
                <select
                  value={editForm.subject_id}
                  onChange={(e) => setEditForm({ ...editForm, subject_id: e.target.value })}
                  className="w-full py-2.5 px-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-[#26313F] text-sm focus:border-[#72C9BE] focus:outline-none"
                >
                  {subjects.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} {s.code ? `(${s.code})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              {/* Time Slot */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[#26313F] font-semibold mb-1">Start Time</label>
                  <input
                    type="time"
                    required
                    value={editForm.start_time}
                    onChange={(e) => setEditForm({ ...editForm, start_time: e.target.value })}
                    className="w-full py-2 px-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-[#26313F] text-sm focus:border-[#72C9BE] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[#26313F] font-semibold mb-1">End Time</label>
                  <input
                    type="time"
                    required
                    value={editForm.end_time}
                    onChange={(e) => setEditForm({ ...editForm, end_time: e.target.value })}
                    className="w-full py-2 px-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-[#26313F] text-sm focus:border-[#72C9BE] focus:outline-none"
                  />
                </div>
              </div>

              {/* Faculty & Room */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[#26313F] font-semibold mb-1">Faculty</label>
                  <input
                    type="text"
                    value={editForm.faculty}
                    onChange={(e) => setEditForm({ ...editForm, faculty: e.target.value })}
                    placeholder="e.g. Dr. Name"
                    className="w-full py-2 px-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-[#26313F] text-sm focus:border-[#72C9BE] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[#26313F] font-semibold mb-1">Room</label>
                  <input
                    type="text"
                    value={editForm.room}
                    onChange={(e) => setEditForm({ ...editForm, room: e.target.value })}
                    placeholder="e.g. LH-1"
                    className="w-full py-2 px-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-[#26313F] text-sm focus:border-[#72C9BE] focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-[#E7EAF0]">
                <button
                  type="button"
                  onClick={() => setEditModalOcc(null)}
                  className="px-4 py-2 rounded-xl text-[#6E7785] hover:text-[#26313F]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2.5 rounded-xl bg-[#72C9BE] hover:bg-[#5db8ad] text-[#13443e] font-semibold shadow-sm"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: Manage Topics Modal */}
      {topicModalOcc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#26313F]/30 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white border border-[#E7EAF0] rounded-3xl max-w-md w-full p-6 space-y-4 shadow-float">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <div>
                <h3 className="text-base font-bold text-[#26313F] flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-[#72C9BE]" />
                  <span>Class Topics: {topicModalOcc.subject?.name}</span>
                </h3>
                <div className="flex items-center gap-2 text-[11px] text-[#6E7785] mt-0.5">
                  <span>{new Date(topicModalOcc.date + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</span>
                  <span>•</span>
                  <span>{topicModalOcc.start_time?.slice(0, 5)}–{topicModalOcc.end_time?.slice(0, 5)}</span>
                  {topicModalOcc.attendance?.status === 'present' && (
                    <span className="text-[10px] font-semibold px-2 py-0.2 rounded-full bg-[#CFEDE7] text-[#1A4B43]">
                      Present ✓
                    </span>
                  )}
                  {topicModalOcc.attendance?.status === 'absent' && (
                    <span className="text-[10px] font-semibold px-2 py-0.2 rounded-full bg-[#EABFC5]/40 text-[#69242E]">
                      Absent
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={() => {
                  setTopicModalOcc(null);
                  setEditingTopicId(null);
                  setEditingTopicTitle('');
                }}
                className="p-1 rounded-xl text-[#6E7785] hover:text-[#26313F]"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-2">
              <span className="text-xs text-[#6E7785] font-semibold uppercase tracking-wider block">
                Recorded Topics ({topicModalOcc.topics?.length || 0})
              </span>
              {(!topicModalOcc.topics || topicModalOcc.topics.length === 0) ? (
                <div className="p-3 rounded-xl bg-[#F7F8FC] border border-dashed border-[#CBD5E1] text-center">
                  <p className="text-xs text-[#8E97A6] font-medium">Topic not added yet for this class.</p>
                  <p className="text-[11px] text-[#A0AEC0] mt-0.5">Add topics below to link them to study planning and revision.</p>
                </div>
              ) : (
                <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                  {topicModalOcc.topics.map((t) => (
                    <div
                      key={t.id}
                      className="p-2.5 rounded-xl bg-[#F7F8FC] border border-[#E7EAF0] text-xs"
                    >
                      {editingTopicId === t.id ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={editingTopicTitle}
                            onChange={(e) => setEditingTopicTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                e.preventDefault();
                                handleUpdateTopic(t.id);
                              } else if (e.key === 'Escape') {
                                setEditingTopicId(null);
                              }
                            }}
                            autoFocus
                            className="flex-1 py-1 px-2.5 bg-white border border-[#72C9BE] rounded-lg text-[#26313F] text-xs focus:outline-none"
                          />
                          <button
                            type="button"
                            onClick={() => handleUpdateTopic(t.id)}
                            className="p-1.5 rounded-lg bg-[#CFEDE7] hover:bg-[#b5e7dc] text-[#1A4B43]"
                            title="Save changes"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingTopicId(null)}
                            className="p-1.5 rounded-lg bg-[#E7EAF0] hover:bg-[#d5dbe5] text-[#6E7785]"
                            title="Cancel editing"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[#26313F] font-medium truncate flex-1">{t.title}</span>
                          <div className="flex items-center gap-2 shrink-0">
                            <button
                              type="button"
                              onClick={() => {
                                setEditingTopicId(t.id);
                                setEditingTopicTitle(t.title);
                              }}
                              className="text-[#3D8C82] hover:text-[#1A4B43] hover:underline font-medium text-xs flex items-center gap-0.5 cursor-pointer"
                            >
                              <Edit2 className="w-3 h-3" />
                              <span>Edit</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteTopic(t.id)}
                              className="text-[#69242E] hover:underline font-medium text-xs cursor-pointer"
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <form onSubmit={handleAddTopic} className="space-y-2 pt-3 border-t border-[#E7EAF0]">
              <label className="block text-xs text-[#26313F] font-semibold">
                Add Topic(s)
              </label>
              <div className="space-y-1.5">
                <input
                  type="text"
                  required
                  value={newTopicTitle}
                  onChange={(e) => setNewTopicTitle(e.target.value)}
                  placeholder="e.g. Brachial Plexus, Axillary Artery"
                  className="w-full py-2 px-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-[#26313F] text-xs focus:border-[#72C9BE] focus:outline-none"
                />
                <p className="text-[11px] text-[#8E97A6]">
                  Enter one or multiple topics separated by commas or lines.
                </p>
              </div>
              <div className="flex justify-end pt-1">
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-[#72C9BE] hover:bg-[#5db8ad] text-[#13443e] text-xs font-semibold shadow-xs transition-colors cursor-pointer"
                >
                  Add Topic
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* POST-CLASS CHECK-IN MODAL */}
      <ClassCheckInModal
        isOpen={Boolean(checkInModalOcc)}
        occurrence={checkInModalOcc}
        onClose={() => setCheckInModalOcc(null)}
        onCheckInComplete={() => loadData()}
      />

      {/* TIMETABLE IMPORT MODAL */}
      <TimetableImportModal
        isOpen={importModal}
        onClose={() => setImportModal(false)}
        onParsedPreview={(preview) => {
          setImportPreviewData(preview);
          setReviewModal(true);
        }}
      />

      {/* REVIEW IMPORTED TIMETABLE MODAL */}
      <TimetableReviewModal
        isOpen={reviewModal}
        previewData={importPreviewData}
        onClose={() => {
          setReviewModal(false);
          setImportPreviewData(null);
        }}
        onImportSuccess={() => loadData()}
      />

      {/* SUBJECT MANAGEMENT MODAL */}
      <SubjectManagementModal
        isOpen={subjectModalConfig.isOpen}
        initialSubjectId={subjectModalConfig.subjectId}
        initialViewMode={subjectModalConfig.viewMode}
        onClose={() => setSubjectModalConfig((prev) => ({ ...prev, isOpen: false }))}
        onSubjectsChanged={handleSubjectsChanged}
      />

      {/* SCHEDULE START DATE SETTINGS MODAL */}
      {startDateModal && (
        <div className="fixed inset-0 z-50 bg-[#26313F]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-float border border-[#E7EAF0] animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-4 border-b border-[#E7EAF0]">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-[#CFEDE7] text-[#1A4B43]">
                  <Calendar className="w-5 h-5 stroke-[2.2]" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-[#26313F]">Schedule Start Date</h3>
                  <p className="text-xs text-[#6E7785]">Effective date for your recurring timetable</p>
                </div>
              </div>
              <button
                onClick={() => setStartDateModal(false)}
                className="p-1 rounded-lg text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveStartDate} className="space-y-4 pt-4">
              <div>
                <label className="block text-xs font-semibold text-[#26313F] mb-1.5">
                  Schedule starts from
                </label>
                <input
                  type="date"
                  required
                  value={selectedStartDate}
                  onChange={(e) => setSelectedStartDate(e.target.value)}
                  className="w-full py-2.5 px-3 bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-[#26313F] text-sm focus:border-[#72C9BE] focus:outline-none"
                />
                <p className="text-[11px] text-[#6E7785] mt-1.5 leading-relaxed">
                  Recurring classes and attendance check-ins will only be tracked from this date forward. Past days before this date will not generate pending attendance or alter attendance stats.
                </p>
              </div>

              <div className="p-3 rounded-2xl bg-[#CFEDE7]/30 border border-[#72C9BE]/30 text-xs text-[#1A4B43]">
                <p className="font-semibold mb-0.5">Mid-semester setup?</p>
                <p className="text-[11px] text-[#1A4B43]/80">
                  If your semester started earlier, you can pick an earlier date to generate historical classes intentionally.
                </p>
              </div>

              <div className="flex justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setStartDateModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-[#6E7785] hover:bg-[#F2F5F8] transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingSettings}
                  className="px-4 py-2 rounded-xl bg-[#72C9BE] hover:bg-[#5db8ad] text-[#13443e] text-xs font-semibold shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                >
                  {savingSettings ? 'Saving...' : 'Save Start Date'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
