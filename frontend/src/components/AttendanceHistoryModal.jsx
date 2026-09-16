import React, { useState, useEffect } from 'react';
import {
  History,
  X,
  RefreshCw,
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Sparkles,
  Edit2,
  Check,
  Archive,
  Calendar,
  User,
  MapPin
} from 'lucide-react';
import { apiRequest } from '../api/client';

export default function AttendanceHistoryModal({
  isOpen,
  onClose,
  initialSubjectId = '',
  subjects = [],
  onRecordUpdated
}) {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [subjectFilter, setSubjectFilter] = useState(initialSubjectId || '');
  const [archiveFilter, setArchiveFilter] = useState('all'); // 'all', 'active', 'archived'

  // Inline topic/notes editing state
  const [editingId, setEditingId] = useState(null);
  const [editTopicTitle, setEditTopicTitle] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [savingId, setSavingId] = useState(null);
  const [actionError, setActionError] = useState('');

  const loadHistory = async () => {
    if (!isOpen) return;
    setLoading(true);
    setActionError('');
    try {
      const params = new URLSearchParams();
      if (subjectFilter) params.set('subject_id', subjectFilter);
      if (archiveFilter !== 'all') params.set('archive_status', archiveFilter);

      const qs = params.toString() ? `?${params.toString()}` : '';
      const data = await apiRequest(`/attendance/history${qs}`);
      setRecords(data || []);
    } catch (err) {
      console.error('Failed to load history:', err);
      setActionError('Failed to load attendance history records');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      setSubjectFilter(initialSubjectId || '');
    }
  }, [isOpen, initialSubjectId]);

  useEffect(() => {
    if (isOpen) {
      loadHistory();
    }
  }, [isOpen, subjectFilter, archiveFilter]);

  if (!isOpen) return null;

  // Toggle status immediately
  const handleStatusChange = async (occ, newStatus) => {
    setSavingId(occ.id);
    setActionError('');
    try {
      const currentTopic = occ.topics && occ.topics.length > 0 ? occ.topics[0].title : '';
      const currentNotes = occ.attendance?.notes || occ.notes || '';

      const updated = await apiRequest(`/attendance/history/${occ.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          status: newStatus,
          topic_title: currentTopic,
          notes: currentNotes
        })
      });

      // Update local record
      setRecords((prev) => prev.map((r) => (r.id === occ.id ? updated : r)));

      if (onRecordUpdated) {
        onRecordUpdated();
      }
    } catch (err) {
      setActionError(`Failed to update status: ${err.message}`);
    } finally {
      setSavingId(null);
    }
  };

  // Start editing topic/notes
  const startEditing = (occ) => {
    setEditingId(occ.id);
    setEditTopicTitle(occ.topics && occ.topics.length > 0 ? occ.topics[0].title : '');
    setEditNotes(occ.attendance?.notes || occ.notes || '');
    setActionError('');
  };

  // Save topic/notes
  const saveTopicAndNotes = async (occ) => {
    setSavingId(occ.id);
    setActionError('');
    try {
      const currentStatus = occ.attendance?.status || (occ.status === 'cancelled' ? 'cancelled' : 'not_marked');

      const updated = await apiRequest(`/attendance/history/${occ.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          status: currentStatus,
          topic_title: editTopicTitle,
          notes: editNotes
        })
      });

      setRecords((prev) => prev.map((r) => (r.id === occ.id ? updated : r)));
      setEditingId(null);

      if (onRecordUpdated) {
        onRecordUpdated();
      }
    } catch (err) {
      setActionError(`Failed to save topic/notes: ${err.message}`);
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4 animate-in fade-in duration-150">
      <div className="bg-white border border-[#E7EAF0] rounded-3xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-float overflow-hidden">
        {/* Modal Header */}
        <div className="p-4 sm:p-5 border-b border-[#E7EAF0] flex items-center justify-between bg-slate-50/60">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-[#CFEDE7] text-[#1A4B43]">
              <History className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base sm:text-lg font-bold text-slate-800">Attendance History &amp; Logs</h2>
              <p className="text-xs text-slate-400">
                Review and edit past attendance, topics covered, and notes
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Filter Controls Bar */}
        <div className="p-3.5 sm:p-4 bg-slate-50 border-b border-[#E7EAF0] flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 flex-wrap">
            {/* Subject Selector */}
            <select
              value={subjectFilter}
              onChange={(e) => setSubjectFilter(e.target.value)}
              className="px-3 py-1.5 rounded-xl bg-white border border-[#E7EAF0] text-xs text-slate-800 focus:outline-none focus:border-[#72C9BE] shadow-xs font-medium"
            >
              <option value="">All Subjects</option>
              {subjects.map((s) => (
                <option key={s.subject_id || s.id} value={s.subject_id || s.id}>
                  {s.subject_name || s.name}
                </option>
              ))}
            </select>

            {/* Archive State Filter */}
            <div className="flex items-center rounded-xl bg-slate-200/70 p-0.5 border border-slate-200">
              <button
                type="button"
                onClick={() => setArchiveFilter('all')}
                className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-colors ${
                  archiveFilter === 'all'
                    ? 'bg-white text-slate-800 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                All Records
              </button>
              <button
                type="button"
                onClick={() => setArchiveFilter('active')}
                className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-colors ${
                  archiveFilter === 'active'
                    ? 'bg-white text-slate-800 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Active Semester
              </button>
              <button
                type="button"
                onClick={() => setArchiveFilter('archived')}
                className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-colors ${
                  archiveFilter === 'archived'
                    ? 'bg-white text-slate-800 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Archived
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-mono font-medium">
              {records.length} {records.length === 1 ? 'record' : 'records'}
            </span>
            <button
              onClick={loadHistory}
              title="Refresh history"
              className="p-1.5 rounded-lg bg-white border border-[#E7EAF0] text-slate-500 hover:text-slate-800 hover:bg-slate-50 transition-colors shadow-xs"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Action Error alert */}
        {actionError && (
          <div className="px-5 py-2.5 bg-rose-50 border-b border-rose-200 text-rose-700 text-xs flex items-center justify-between">
            <span>{actionError}</span>
            <button onClick={() => setActionError('')} className="text-rose-600 hover:text-rose-800">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* History List */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-3">
          {loading && records.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-2 text-slate-400 text-xs">
              <RefreshCw className="w-6 h-6 text-[#72C9BE] animate-spin" />
              <span>Loading attendance history...</span>
            </div>
          ) : records.length === 0 ? (
            <div className="text-center py-16 bg-white rounded-2xl border border-dashed border-[#E7EAF0] p-6 space-y-2 shadow-card">
              <Calendar className="w-10 h-10 text-slate-300 mx-auto" />
              <p className="text-sm font-bold text-slate-700">No attendance records found</p>
              <p className="text-xs text-slate-400 max-w-sm mx-auto">
                No classes match the selected subject or archive filter.
              </p>
            </div>
          ) : (
            records.map((occ) => {
              const currentStatus =
                occ.attendance?.status || (occ.status === 'cancelled' ? 'cancelled' : 'not_marked');
              const isEditingThis = editingId === occ.id;
              const isSavingThis = savingId === occ.id;
              const isArchived = occ.is_archived || occ.attendance?.is_archived;
              const archiveLabel = occ.archive_label || occ.attendance?.archive_label;

              return (
                <div
                  key={occ.id}
                  className={`p-4.5 rounded-2xl border transition-all space-y-3 shadow-card ${
                    isArchived
                      ? 'bg-slate-50/60 border-slate-200'
                      : 'bg-white border-[#E7EAF0] hover:border-slate-300'
                  }`}
                >
                  {/* Top Bar: Subject, Date, Room, Faculty, Archive Badge */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span
                        className="w-2.5 h-2.5 rounded-full shrink-0 shadow-xs"
                        style={{ backgroundColor: occ.subject?.color || '#72C9BE' }}
                      />
                      <span className="font-bold text-slate-800 text-sm">
                        {occ.subject?.name || 'Unknown Subject'}
                      </span>
                      {occ.subject?.code && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 border border-slate-200">
                          {occ.subject.code}
                        </span>
                      )}
                      <span className="text-xs text-slate-500 font-medium">
                        {new Date(occ.date + 'T00:00:00').toLocaleDateString(undefined, {
                          weekday: 'short',
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric'
                        })}
                      </span>
                      <span className="text-xs text-slate-400 font-mono">
                        {occ.start_time?.slice(0, 5)} – {occ.end_time?.slice(0, 5)}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      {isArchived && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-md bg-amber-50 text-amber-800 border border-amber-200">
                          <Archive className="w-3 h-3" />
                          <span>{archiveLabel || 'Archived'}</span>
                        </span>
                      )}
                      {occ.room && (
                        <span className="text-[10px] text-slate-500 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded-md">
                          {occ.room}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Middle: Topic covered & Notes */}
                  {isEditingThis ? (
                    <div className="p-3.5 rounded-xl bg-slate-50 border border-[#72C9BE]/50 space-y-2.5">
                      <div>
                        <label className="text-[11px] font-semibold text-[#1A4B43] block mb-1">
                          Topic Covered
                        </label>
                        <input
                          type="text"
                          placeholder="e.g., Brachial Plexus, Action Potentials"
                          value={editTopicTitle}
                          onChange={(e) => setEditTopicTitle(e.target.value)}
                          className="w-full px-3 py-1.5 rounded-lg bg-white border border-[#E7EAF0] text-slate-800 text-xs focus:outline-none focus:border-[#72C9BE]"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] font-semibold text-slate-600 block mb-1">
                          Class Notes / Details
                        </label>
                        <textarea
                          rows={2}
                          placeholder="Key clinical points or personal notes..."
                          value={editNotes}
                          onChange={(e) => setEditNotes(e.target.value)}
                          className="w-full px-3 py-1.5 rounded-lg bg-white border border-[#E7EAF0] text-slate-800 text-xs focus:outline-none focus:border-[#72C9BE]"
                        />
                      </div>
                      <div className="flex items-center justify-end gap-2 pt-1">
                        <button
                          type="button"
                          onClick={() => setEditingId(null)}
                          className="px-2.5 py-1 text-xs text-slate-500 hover:text-slate-800 rounded-lg hover:bg-slate-200"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={() => saveTopicAndNotes(occ)}
                          disabled={isSavingThis}
                          className="px-3 py-1 text-xs font-semibold bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer shadow-xs"
                        >
                          {isSavingThis ? (
                            <RefreshCw className="w-3 h-3 animate-spin" />
                          ) : (
                            <Check className="w-3 h-3 stroke-[2.5]" />
                          )}
                          <span>Save Changes</span>
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs bg-slate-50 p-2.5 rounded-xl border border-slate-200/80">
                      <div className="space-y-0.5">
                        {occ.topics && occ.topics.length > 0 ? (
                          <p className="text-[#1A4B43] font-medium flex items-center gap-1.5">
                            <Sparkles className="w-3 h-3 text-[#72C9BE] shrink-0" />
                            <span>Topic: {occ.topics.map((t) => t.title).join(', ')}</span>
                          </p>
                        ) : (
                          <p className="text-slate-400 text-[11px] italic">No topic recorded</p>
                        )}
                        {(occ.attendance?.notes || occ.notes) && (
                          <p className="text-slate-500 text-[11px]">
                            Notes: {occ.attendance?.notes || occ.notes}
                          </p>
                        )}
                      </div>

                      <button
                        type="button"
                        onClick={() => startEditing(occ)}
                        className="inline-flex items-center gap-1 text-[11px] text-[#1A4B43] hover:underline font-semibold px-2 py-1 rounded bg-[#CFEDE7]/40 border border-[#72C9BE]/30 self-start sm:self-auto cursor-pointer transition-colors"
                      >
                        <Edit2 className="w-3 h-3" />
                        <span>Edit Topic &amp; Notes</span>
                      </button>
                    </div>
                  )}

                  {/* Bottom: Editable Attendance Status Toggle (Present ↔ Absent ↔ Cancelled) */}
                  <div className="pt-2 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <span className="text-[11px] text-slate-500 font-medium">
                      Status:{' '}
                      <span className="text-slate-800 capitalize font-bold">
                        {currentStatus === 'not_marked' ? 'Pending' : currentStatus}
                      </span>
                    </span>

                    <div className="grid grid-cols-4 gap-1 sm:flex sm:items-center sm:gap-1.5 text-xs">
                      {/* PRESENT */}
                      <button
                        type="button"
                        disabled={isSavingThis}
                        onClick={() => handleStatusChange(occ, 'present')}
                        className={`px-3 py-1 rounded-lg border transition-all cursor-pointer font-semibold ${
                          currentStatus === 'present'
                            ? 'bg-[#CFEDE7] text-[#1A4B43] border-[#72C9BE] shadow-xs'
                            : 'bg-white border-slate-200 text-slate-600 hover:border-[#72C9BE]'
                        }`}
                      >
                        Present
                      </button>

                      {/* ABSENT */}
                      <button
                        type="button"
                        disabled={isSavingThis}
                        onClick={() => handleStatusChange(occ, 'absent')}
                        className={`px-3 py-1 rounded-lg border transition-all cursor-pointer font-semibold ${
                          currentStatus === 'absent'
                            ? 'bg-[#EABFC5]/40 text-[#69242E] border-[#EABFC5] shadow-xs'
                            : 'bg-white border-slate-200 text-slate-600 hover:border-rose-300'
                        }`}
                      >
                        Absent
                      </button>

                      {/* CANCELLED */}
                      <button
                        type="button"
                        disabled={isSavingThis}
                        onClick={() => handleStatusChange(occ, 'cancelled')}
                        className={`px-3 py-1 rounded-lg border transition-all cursor-pointer font-semibold ${
                          currentStatus === 'cancelled'
                            ? 'bg-[#F3DFAB]/50 text-[#6B4E17] border-[#F3DFAB] shadow-xs'
                            : 'bg-white border-slate-200 text-slate-600 hover:border-amber-300'
                        }`}
                      >
                        Cancelled
                      </button>

                      {/* UNMARK / PENDING */}
                      <button
                        type="button"
                        disabled={isSavingThis}
                        onClick={() => handleStatusChange(occ, 'not_marked')}
                        className={`px-2.5 py-1 rounded-lg border transition-all cursor-pointer font-medium ${
                          currentStatus === 'not_marked'
                            ? 'bg-slate-200 text-slate-800 border-slate-300 shadow-xs'
                            : 'bg-white border-slate-200 text-slate-400 hover:text-slate-600'
                        }`}
                      >
                        Unmark
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
