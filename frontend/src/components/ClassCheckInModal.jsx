import React, { useState, useEffect } from 'react';
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  X,
  Clock,
  MapPin,
  UserCheck,
  BookOpen,
  ArrowRight,
  Sparkles,
  Info
} from 'lucide-react';
import { apiRequest } from '../api/client';

export default function ClassCheckInModal({
  isOpen,
  onClose,
  occurrence,
  pendingList = [],
  onCheckInComplete
}) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [activeOcc, setActiveOcc] = useState(null);

  // Form State
  const [status, setStatus] = useState('present');
  const [topicTitle, setTopicTitle] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Determine active occurrence
  useEffect(() => {
    if (!isOpen) return;
    if (pendingList && pendingList.length > 0) {
      setCurrentIndex(0);
      setActiveOcc(pendingList[0]);
    } else if (occurrence) {
      setActiveOcc(occurrence);
    }
  }, [isOpen, occurrence, pendingList]);

  // Sync form with activeOcc
  useEffect(() => {
    if (!activeOcc) return;
    const currentAtt = activeOcc.attendance?.status;
    if (currentAtt && currentAtt !== 'not_marked') {
      setStatus(currentAtt);
    } else if (activeOcc.status === 'cancelled') {
      setStatus('cancelled');
    } else {
      setStatus('present');
    }

    // Existing topics
    if (activeOcc.topics && activeOcc.topics.length > 0) {
      setTopicTitle('');
    } else {
      setTopicTitle('');
    }
    setNotes(activeOcc.attendance?.notes || activeOcc.notes || '');
    setErrorMsg('');
  }, [activeOcc]);

  if (!isOpen || !activeOcc) return null;

  const totalPending = pendingList?.length || 0;
  const isQueueMode = totalPending > 1;
  const hasMore = isQueueMode && currentIndex < totalPending - 1;

  const handleSubmit = async (saveAndNext = false) => {
    try {
      setSubmitting(true);
      setErrorMsg('');

      const payload = {
        occurrence_id: activeOcc.id,
        status,
        topic_title: topicTitle.trim() || undefined,
        notes: notes.trim() || undefined
      };

      const updated = await apiRequest('/attendance/check-in', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      if (onCheckInComplete) {
        onCheckInComplete(updated);
      }

      if (saveAndNext && hasMore) {
        const nextIdx = currentIndex + 1;
        setCurrentIndex(nextIdx);
        setActiveOcc(pendingList[nextIdx]);
        setSubmitting(false);
      } else {
        onClose();
      }
    } catch (err) {
      setErrorMsg(err.message || 'Failed to save check-in');
      setSubmitting(false);
    }
  };

  const handleDeleteExistingTopic = async (topicId) => {
    try {
      await apiRequest(`/timetable/topics/${topicId}`, { method: 'DELETE' });
      setActiveOcc((prev) => ({
        ...prev,
        topics: (prev.topics || []).filter((t) => t.id !== topicId)
      }));
      if (onCheckInComplete) {
        onCheckInComplete();
      }
    } catch (err) {
      setErrorMsg(err.message || 'Failed to delete topic');
    }
  };

  const subjectName = activeOcc.subject?.name || 'Class';
  const subjectCode = activeOcc.subject?.code || '';
  const startTime = activeOcc.start_time?.slice(0, 5) || '';
  const endTime = activeOcc.end_time?.slice(0, 5) || '';
  const dateFormatted = new Date(activeOcc.date + 'T00:00:00').toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric'
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        className="w-full max-w-lg bg-white border border-[#E7EAF0] rounded-3xl shadow-float overflow-hidden flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="p-5 border-b border-[#E7EAF0] flex items-center justify-between bg-slate-50/60">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-[#1A4B43]">
                Post-Class Attendance Check-In
              </span>
              {isQueueMode && (
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#CFEDE7] text-[#1A4B43]">
                  {currentIndex + 1} of {totalPending} Pending
                </span>
              )}
            </div>
            <h2 className="text-xl font-bold text-slate-800 mt-0.5 flex items-center gap-2">
              <span>{subjectName}</span>
              {subjectCode && (
                <span className="text-xs font-mono text-slate-500 px-2 py-0.5 rounded bg-slate-200">
                  {subjectCode}
                </span>
              )}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6">
          {errorMsg && (
            <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Class Details Pill Bar */}
          <div className="flex flex-wrap items-center gap-2.5 p-3 rounded-2xl bg-slate-50 border border-slate-200 text-xs text-slate-600">
            <span className="flex items-center gap-1.5 font-medium">
              <Clock className="w-3.5 h-3.5 text-[#72C9BE]" />
              <span>{dateFormatted} &bull; {startTime} - {endTime}</span>
            </span>
            {activeOcc.room && (
              <span className="flex items-center gap-1.5 text-slate-500">
                <MapPin className="w-3.5 h-3.5 text-slate-400" />
                <span>{activeOcc.room}</span>
              </span>
            )}
            {activeOcc.faculty && (
              <span className="flex items-center gap-1.5 text-slate-500">
                <UserCheck className="w-3.5 h-3.5 text-slate-400" />
                <span>{activeOcc.faculty}</span>
              </span>
            )}
          </div>

          {/* Status Selection: 3 Cards */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-700 block">
              Were you present in this class?
            </label>
            <div className="grid grid-cols-3 gap-2.5">
              {/* Present */}
              <button
                type="button"
                onClick={() => setStatus('present')}
                className={`p-3.5 rounded-2xl border text-center transition-all cursor-pointer flex flex-col items-center gap-1.5 ${
                  status === 'present'
                    ? 'bg-[#CFEDE7] border-[#72C9BE] text-[#1A4B43] shadow-xs'
                    : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                <CheckCircle2 className={`w-5 h-5 ${status === 'present' ? 'text-[#1A4B43]' : 'text-slate-400'}`} />
                <span className="text-xs font-bold block">Present</span>
                <span className="text-[10px] text-slate-500">I attended</span>
              </button>

              {/* Absent */}
              <button
                type="button"
                onClick={() => setStatus('absent')}
                className={`p-3.5 rounded-2xl border text-center transition-all cursor-pointer flex flex-col items-center gap-1.5 ${
                  status === 'absent'
                    ? 'bg-[#EABFC5]/30 border-[#EABFC5] text-[#69242E] shadow-xs'
                    : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                <XCircle className={`w-5 h-5 ${status === 'absent' ? 'text-[#69242E]' : 'text-slate-400'}`} />
                <span className="text-xs font-bold block">Absent</span>
                <span className="text-[10px] text-slate-500">I missed</span>
              </button>

              {/* Cancelled */}
              <button
                type="button"
                onClick={() => setStatus('cancelled')}
                className={`p-3.5 rounded-2xl border text-center transition-all cursor-pointer flex flex-col items-center gap-1.5 ${
                  status === 'cancelled'
                    ? 'bg-[#F3DFAB]/40 border-[#F3DFAB] text-[#6B4E17] shadow-xs'
                    : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                <AlertCircle className={`w-5 h-5 ${status === 'cancelled' ? 'text-[#6B4E17]' : 'text-slate-400'}`} />
                <span className="text-xs font-bold block">Cancelled</span>
                <span className="text-[10px] text-slate-500">Class called off</span>
              </button>
            </div>
          </div>

          {/* Cancellation Info Callout */}
          {status === 'cancelled' && (
            <div className="p-3.5 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start gap-2.5">
              <Info className="w-4 h-4 shrink-0 text-amber-600 mt-0.5" />
              <div className="space-y-0.5">
                <span className="font-semibold block text-amber-900">Safe Exclusion</span>
                <p className="text-[11px] text-amber-800/90 leading-relaxed">
                  Cancelled classes are strictly excluded from your conducted count. They will not hurt your attendance percentage or safe bunk buffer.
                </p>
              </div>
            </div>
          )}

          {/* Existing Topics Already Logged */}
          {activeOcc.topics && activeOcc.topics.length > 0 && (
            <div className="space-y-1.5">
              <label className="text-[11px] font-semibold text-slate-500 block">
                Topics already recorded for this lecture:
              </label>
              <div className="flex flex-wrap gap-1.5">
                {activeOcc.topics.map((t) => (
                  <span
                    key={t.id}
                    className="text-xs px-2.5 py-1 rounded-xl bg-[#CFEDE7]/40 text-[#1A4B43] border border-[#72C9BE]/30 flex items-center gap-1.5 font-medium"
                  >
                    <BookOpen className="w-3 h-3 text-[#72C9BE]" />
                    <span>{t.title}</span>
                    <button
                      type="button"
                      onClick={() => handleDeleteExistingTopic(t.id)}
                      className="text-[#69242E] hover:text-rose-700 ml-1 p-0.5 rounded-full hover:bg-rose-100 transition-colors"
                      title="Delete this topic"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Topic Covered Field (Only if not cancelled) */}
          {status !== 'cancelled' && (
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 flex items-center justify-between">
                <span>
                  {activeOcc.topics && activeOcc.topics.length > 0
                    ? 'Add Another Topic'
                    : status === 'present'
                    ? 'Topic Covered'
                    : 'Topic Covered (Optional)'}
                </span>
                {status === 'absent' && (
                  <span className="text-[10px] text-slate-400 font-normal">You can add this later from classmates</span>
                )}
              </label>
              <div className="relative">
                <BookOpen className="w-4 h-4 absolute left-3.5 top-3.5 text-slate-400" />
                <input
                  type="text"
                  value={topicTitle}
                  onChange={(e) => setTopicTitle(e.target.value)}
                  placeholder={status === 'present' ? "e.g. Brachial Plexus, Axillary Artery" : "Ask a classmate later or leave blank"}
                  className="w-full pl-10 pr-4 py-2.5 rounded-2xl bg-slate-50 border border-[#E7EAF0] text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                />
              </div>
              <p className="text-[11px] text-slate-400">
                Topics are saved to your timetable and automatically link to study notes and revision tasks. Multiple topics can be comma-separated.
              </p>
            </div>
          )}

          {/* Notes Field */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 block">
              Personal Notes (Optional)
            </label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Clinical case discussed, test announced for next week"
              className="w-full px-4 py-2.5 rounded-2xl bg-slate-50 border border-[#E7EAF0] text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
            />
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-5 border-t border-[#E7EAF0] bg-slate-50/60 flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium transition-colors cursor-pointer"
          >
            Cancel
          </button>

          <div className="flex items-center gap-2">
            {hasMore && (
              <button
                type="button"
                disabled={submitting}
                onClick={() => handleSubmit(true)}
                className="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold flex items-center gap-1.5 transition-colors disabled:opacity-50 cursor-pointer"
              >
                <span>Save & Next ({totalPending - currentIndex - 1} left)</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}

            <button
              type="button"
              disabled={submitting}
              onClick={() => handleSubmit(false)}
              className="px-5 py-2.5 rounded-xl bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 text-xs font-semibold shadow-xs flex items-center gap-2 transition-all disabled:opacity-50 cursor-pointer active:scale-95"
            >
              {submitting ? 'Saving...' : 'Save Check-In'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
