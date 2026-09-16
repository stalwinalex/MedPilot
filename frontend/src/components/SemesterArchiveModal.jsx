import React, { useState } from 'react';
import { GraduationCap, Archive, X, RefreshCw, CheckCircle2, ShieldAlert } from 'lucide-react';
import { apiRequest } from '../api/client';

export default function SemesterArchiveModal({
  isOpen,
  onClose,
  onSemesterStarted
}) {
  const [semesterLabel, setSemesterLabel] = useState('Semester 1');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    const cleanLabel = semesterLabel.trim();
    if (!cleanLabel) {
      setErrorMsg('Please enter a semester label.');
      return;
    }

    setSubmitting(true);
    setErrorMsg('');

    try {
      await apiRequest('/attendance/new-semester', {
        method: 'POST',
        body: JSON.stringify({
          semester_label: cleanLabel
        })
      });

      onClose();
      if (onSemesterStarted) {
        onSemesterStarted();
      }
    } catch (err) {
      setErrorMsg(err.message || 'Failed to archive semester');
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
            <div className="p-2.5 rounded-xl bg-[#CFEDE7] text-[#1A4B43]">
              <GraduationCap className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-800">Start New Semester</h2>
              <p className="text-xs text-slate-400">Archive current logs &amp; begin fresh counts</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Explanation banner */}
          <div className="p-3.5 rounded-2xl bg-[#F2FBF9] border border-[#CFEDE7] text-xs text-[#1A4B43] space-y-1.5">
            <div className="flex items-center gap-2 font-semibold">
              <Archive className="w-4 h-4 text-[#72C9BE] shrink-0" />
              <span>Safe Archival (No Deletion)</span>
            </div>
            <p className="text-[11px] text-slate-600 leading-relaxed">
              Your previous classes, attendance statuses, and topics will be safely archived under the label you provide.
              Active attendance will restart fresh at 0% (No attendance yet). You can review past records anytime in <b>Attendance History</b>.
            </p>
          </div>

          {errorMsg && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs">
              {errorMsg}
            </div>
          )}

          {/* Semester Label Input */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 block">
              Label for Current Semester Archive:
            </label>
            <input
              type="text"
              required
              placeholder="e.g., Semester 1, 2nd Professional, Fall 2025"
              value={semesterLabel}
              onChange={(e) => setSemesterLabel(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 border border-[#E7EAF0] text-slate-800 text-xs placeholder:text-slate-400 focus:outline-none focus:bg-white focus:border-[#72C9BE]"
            />
            <span className="text-[10px] text-slate-400 block">
              Used to filter and identify these records in the Attendance History log.
            </span>
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
              disabled={submitting || !semesterLabel.trim()}
              className="px-5 py-2.5 rounded-xl text-xs font-semibold bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 shadow-xs transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50 active:scale-95"
            >
              {submitting ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Archiving...</span>
                </>
              ) : (
                <>
                  <Archive className="w-3.5 h-3.5" />
                  <span>Archive &amp; Start New Semester</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
