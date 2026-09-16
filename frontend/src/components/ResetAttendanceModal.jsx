import React, { useState } from 'react';
import { AlertTriangle, Trash2, X, RefreshCw, CheckCircle2 } from 'lucide-react';
import { apiRequest } from '../api/client';

export default function ResetAttendanceModal({
  isOpen,
  onClose,
  subjects = [],
  onResetComplete
}) {
  const [selectedSubject, setSelectedSubject] = useState('all');
  const [removeTopics, setRemoveTopics] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  if (!isOpen) return null;

  const isConfirmed = confirmText.trim() === 'RESET';

  const handleReset = async (e) => {
    e.preventDefault();
    if (!isConfirmed) return;

    setSubmitting(true);
    setErrorMsg('');

    try {
      const subjectId = selectedSubject === 'all' ? null : selectedSubject;
      await apiRequest('/attendance/reset', {
        method: 'POST',
        body: JSON.stringify({
          subject_id: subjectId,
          remove_topics: removeTopics,
          confirmation: confirmText.trim()
        })
      });

      setConfirmText('');
      setSelectedSubject('all');
      setRemoveTopics(false);
      onClose();
      if (onResetComplete) {
        onResetComplete();
      }
    } catch (err) {
      setErrorMsg(err.message || 'Failed to reset attendance data');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-150">
      <div className="bg-white border border-[#E7EAF0] rounded-3xl w-full max-w-md shadow-float overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-[#E7EAF0] flex items-center justify-between bg-slate-50/60">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-rose-50 text-rose-600 border border-rose-200">
              <Trash2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-800">Reset Attendance Data</h2>
              <p className="text-xs text-slate-400">Clear attendance records and start clean</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleReset} className="p-6 space-y-4">
          {/* Safeguard Notice */}
          <div className="p-3.5 rounded-2xl bg-rose-50 border border-rose-200 text-xs text-rose-800 space-y-1.5">
            <div className="flex items-center gap-2 font-semibold">
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>Permanent Reset Action</span>
            </div>
            <p className="text-[11px] text-rose-700 leading-relaxed">
              This resets your attendance records and calculations to 0. Your weekly timetable schedule and subjects will be kept intact.
            </p>
          </div>

          {errorMsg && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs">
              {errorMsg}
            </div>
          )}

          {/* Scope Select */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700">
              Select Attendance Scope to Reset
            </label>
            <select
              value={selectedSubject}
              onChange={(e) => setSelectedSubject(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 border border-[#E7EAF0] text-slate-800 text-xs focus:outline-none focus:bg-white focus:border-[#72C9BE]"
            >
              <option value="all">All Subjects (Entire Attendance)</option>
              {subjects.map((s) => (
                <option key={s.subject_id || s.id} value={s.subject_id || s.id}>
                  {s.subject_name || s.name} only
                </option>
              ))}
            </select>
          </div>

          {/* Remove Topics Checkbox */}
          <label className="flex items-start gap-2.5 p-3 rounded-xl bg-slate-50 border border-slate-200 cursor-pointer hover:border-slate-300 transition-colors">
            <input
              type="checkbox"
              checked={removeTopics}
              onChange={(e) => setRemoveTopics(e.target.checked)}
              className="mt-0.5 rounded border-slate-300 text-[#72C9BE] focus:ring-[#72C9BE]"
            />
            <div className="text-xs">
              <span className="font-semibold text-slate-800 block">
                Also remove saved class topics
              </span>
              <span className="text-[11px] text-slate-500 block mt-0.5">
                If unchecked, topic notes are preserved for future reference while attendance counts reset to 0.
              </span>
            </div>
          </label>

          {/* Confirmation Input */}
          <div className="space-y-1.5 pt-1">
            <label className="text-xs font-semibold text-slate-700 block">
              Type <span className="font-mono text-rose-600 font-bold tracking-wider">RESET</span> to confirm:
            </label>
            <input
              type="text"
              placeholder="RESET"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 border border-[#E7EAF0] text-slate-800 text-xs font-mono placeholder:text-slate-400 focus:outline-none focus:bg-white focus:border-rose-500"
              autoComplete="off"
            />
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-[#E7EAF0]">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!isConfirmed || submitting}
              className={`px-4 py-2.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 shadow-xs ${
                isConfirmed && !submitting
                  ? 'bg-rose-600 hover:bg-rose-700 text-white cursor-pointer active:scale-95'
                  : 'bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200'
              }`}
            >
              {submitting ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Resetting...</span>
                </>
              ) : (
                <>
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Reset Attendance Data</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
