import React, { useState, useEffect } from 'react';
import {
  Calendar,
  Clock,
  BookOpen,
  Check,
  X,
  Plus,
  AlertCircle,
  MapPin,
  User,
  FileText
} from 'lucide-react';
import { apiRequest } from '../api/client';

export default function ManualAttendanceModal({ isOpen, onClose, onAdded }) {
  const [subjects, setSubjects] = useState([]);
  const [loadingSubjects, setLoadingSubjects] = useState(true);

  // Form Fields
  const [subjectId, setSubjectId] = useState('');
  const [dateVal, setDateVal] = useState(new Date().toISOString().split('T')[0]);
  const [startTime, setStartTime] = useState('09:00');
  const [endTime, setEndTime] = useState('10:00');
  const [status, setStatus] = useState('present'); // 'present', 'absent', 'cancelled'
  const [faculty, setFaculty] = useState('');
  const [room, setRoom] = useState('');
  const [notes, setNotes] = useState('');

  // Inline Quick Subject Creation
  const [showQuickSubject, setShowQuickSubject] = useState(false);
  const [newSubjName, setNewSubjName] = useState('');
  const [creatingSubject, setCreatingSubject] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    if (isOpen) {
      loadSubjects();
      setErrorMsg('');
      setShowQuickSubject(false);
    }
  }, [isOpen]);

  async function loadSubjects() {
    setLoadingSubjects(true);
    try {
      const data = await apiRequest('/subjects/');
      setSubjects(data || []);
      if (data && data.length > 0 && !subjectId) {
        setSubjectId(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load subjects:', err);
    } finally {
      setLoadingSubjects(false);
    }
  }

  async function handleQuickCreateSubject(e) {
    e.preventDefault();
    if (!newSubjName.trim()) return;
    setCreatingSubject(true);
    try {
      const created = await apiRequest('/subjects/', {
        method: 'POST',
        body: JSON.stringify({
          name: newSubjName.trim(),
          code: newSubjName.slice(0, 4).toUpperCase(),
          color: '#72C9BE',
        }),
      });
      setSubjects((prev) => [...prev, created]);
      setSubjectId(created.id);
      setNewSubjName('');
      setShowQuickSubject(false);
    } catch (err) {
      alert('Failed to create subject: ' + err.message);
    } finally {
      setCreatingSubject(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!subjectId) {
      setErrorMsg('Please select or create a subject.');
      return;
    }
    setSubmitting(true);
    setErrorMsg('');
    try {
      await apiRequest('/attendance/manual', {
        method: 'POST',
        body: JSON.stringify({
          subject_id: subjectId,
          date: dateVal,
          start_time: startTime.length === 5 ? `${startTime}:00` : startTime,
          end_time: endTime.length === 5 ? `${endTime}:00` : endTime,
          status,
          faculty,
          room,
          notes,
        }),
      });
      if (onAdded) onAdded();
      onClose();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to record attendance');
    } finally {
      setSubmitting(false);
    }
  }

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white border border-[#E7EAF0] rounded-3xl w-full max-w-lg shadow-float overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-5 border-b border-[#E7EAF0] flex items-center justify-between bg-slate-50/60">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-[#CFEDE7] rounded-xl text-[#1A4B43]">
              <Calendar className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-800">+ Add Class / Attendance</h2>
              <p className="text-xs text-slate-400">Record an extra class, clinical posting, or unscheduled session.</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {errorMsg && (
            <div className="p-3.5 rounded-xl text-xs bg-rose-50 border border-rose-200 text-rose-700 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Subject Dropdown & Quick Create */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-slate-700">
                Subject <span className="text-rose-500">*</span>
              </label>
              <button
                type="button"
                onClick={() => setShowQuickSubject(!showQuickSubject)}
                className="text-xs text-[#1A4B43] hover:underline font-semibold flex items-center gap-1 cursor-pointer"
              >
                <Plus className="w-3 h-3" />
                {showQuickSubject ? 'Cancel' : 'New Subject'}
              </button>
            </div>

            {showQuickSubject ? (
              <div className="flex gap-2 p-2 bg-slate-50 rounded-xl border border-slate-200">
                <input
                  type="text"
                  placeholder="Subject Name (e.g. Ophthalmology)"
                  value={newSubjName}
                  onChange={(e) => setNewSubjName(e.target.value)}
                  className="flex-1 bg-white border border-[#E7EAF0] px-3 py-1.5 rounded-lg text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:border-[#72C9BE]"
                />
                <button
                  type="button"
                  onClick={handleQuickCreateSubject}
                  disabled={creatingSubject || !newSubjName.trim()}
                  className="px-3.5 py-1.5 bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 rounded-lg text-xs font-semibold cursor-pointer shadow-xs"
                >
                  {creatingSubject ? 'Adding...' : 'Add'}
                </button>
              </div>
            ) : (
              <select
                required
                value={subjectId}
                onChange={(e) => setSubjectId(e.target.value)}
                className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3.5 py-2.5 text-sm text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
              >
                {subjects.length === 0 ? (
                  <option value="">No subjects yet. Click 'New Subject' above.</option>
                ) : (
                  subjects.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} {s.code ? `(${s.code})` : ''}
                    </option>
                  ))
                )}
              </select>
            )}
          </div>

          {/* Date & Time Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">Date</label>
              <input
                type="date"
                required
                value={dateVal}
                onChange={(e) => setDateVal(e.target.value)}
                className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE]"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">Start Time</label>
              <input
                type="time"
                required
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE]"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">End Time</label>
              <input
                type="time"
                required
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE]"
              />
            </div>
          </div>

          {/* Attendance Status Selector */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-2">
              Attendance Status <span className="text-rose-500">*</span>
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setStatus('present')}
                className={`py-2.5 px-3 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
                  status === 'present'
                    ? 'bg-[#CFEDE7] text-[#1A4B43] border-[#72C9BE] shadow-xs'
                    : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                Present
              </button>
              <button
                type="button"
                onClick={() => setStatus('absent')}
                className={`py-2.5 px-3 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
                  status === 'absent'
                    ? 'bg-[#EABFC5]/30 text-[#69242E] border-[#EABFC5] shadow-xs'
                    : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                Absent
              </button>
              <button
                type="button"
                onClick={() => setStatus('cancelled')}
                className={`py-2.5 px-3 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
                  status === 'cancelled'
                    ? 'bg-[#F3DFAB]/40 text-[#6B4E17] border-[#F3DFAB] shadow-xs'
                    : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                Cancelled
              </button>
            </div>
            {status === 'cancelled' && (
              <p className="text-[11px] text-amber-800 mt-1.5 flex items-center gap-1 font-medium">
                <span>&bull;</span>
                <span>Cancelled classes are strictly excluded from total conducted classes and percentage.</span>
              </p>
            )}
          </div>

          {/* Faculty & Room (Optional) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Faculty Name (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Dr. Verma"
                value={faculty}
                onChange={(e) => setFaculty(e.target.value)}
                className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE]"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Room / Venue (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Ward 4B, LT-2"
                value={room}
                onChange={(e) => setRoom(e.target.value)}
                className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE]"
              />
            </div>
          </div>

          {/* Notes (Optional) */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Class Notes / Topic Covered (Optional)
            </label>
            <textarea
              rows="2"
              placeholder="e.g. Bedside case presentation on mitral stenosis"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl p-3 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE]"
            />
          </div>

          {/* Footer Buttons */}
          <div className="pt-2 flex items-center justify-end gap-3 border-t border-[#E7EAF0]">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !subjectId}
              className="px-5 py-2.5 rounded-xl text-xs font-semibold bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 disabled:opacity-50 transition-colors flex items-center gap-1.5 cursor-pointer shadow-xs active:scale-95"
            >
              <Check className="w-4 h-4 stroke-[2.5]" />
              <span>{submitting ? 'Recording...' : 'Record Class'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
