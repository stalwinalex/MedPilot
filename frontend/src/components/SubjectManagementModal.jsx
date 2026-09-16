import React, { useState, useEffect } from 'react';
import {
  BookOpen,
  Plus,
  Edit2,
  Trash2,
  Check,
  X,
  AlertTriangle,
  Clock,
  History,
  GraduationCap,
  User,
  CheckCircle2,
  Calendar
} from 'lucide-react';
import { apiRequest } from '../api/client';

export default function SubjectManagementModal({
  isOpen,
  onClose,
  onSubjectsChanged,
  initialSubjectId = null,
  initialViewMode = 'list'
}) {
  const [subjects, setSubjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState('list'); // 'list', 'add', 'edit', 'history'

  // Selected / Editing Subject
  const [selectedSubject, setSelectedSubject] = useState(null);
  const [subjectHistory, setSubjectHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Form State
  const [formData, setFormData] = useState({
    name: '',
    code: '',
    color: '#72C9BE',
    target_attendance: 75.0,
    faculty: '',
    academic_year: 'MBBS 1st Year',
  });
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Delete Confirmation State
  const [deleteConfirmSubject, setDeleteConfirmSubject] = useState(null);
  const [deleteWarning, setDeleteWarning] = useState('');
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setErrorMsg('');
      loadSubjects().then((data) => {
        if (initialSubjectId && data && data.length > 0) {
          const target = data.find((s) => s.id === initialSubjectId);
          if (target) {
            handleOpenEdit(target);
            return;
          }
        }
        if (initialViewMode === 'add') {
          handleOpenAdd();
        } else {
          setViewMode('list');
        }
      });
    }
  }, [isOpen, initialSubjectId, initialViewMode]);

  async function loadSubjects() {
    setLoading(true);
    try {
      const data = await apiRequest('/subjects/');
      setSubjects(data || []);
      return data || [];
    } catch (err) {
      setErrorMsg('Failed to load subjects: ' + err.message);
      return [];
    } finally {
      setLoading(false);
    }
  }

  function handleOpenAdd() {
    setFormData({
      name: '',
      code: '',
      color: '#72C9BE',
      target_attendance: 75.0,
      faculty: '',
      academic_year: 'MBBS 1st Year',
    });
    setErrorMsg('');
    setViewMode('add');
  }

  function handleOpenEdit(subj) {
    setSelectedSubject(subj);
    setFormData({
      name: subj.name,
      code: subj.code || '',
      color: subj.color || '#72C9BE',
      target_attendance: subj.target_attendance || 75.0,
      faculty: subj.faculty || '',
      academic_year: subj.academic_year || 'MBBS 1st Year',
    });
    setErrorMsg('');
    setViewMode('edit');
  }

  async function handleOpenHistory(subj) {
    setSelectedSubject(subj);
    setViewMode('history');
    setHistoryLoading(true);
    try {
      const data = await apiRequest(`/subjects/${subj.id}/history`);
      setSubjectHistory(data || []);
    } catch (err) {
      console.error('Failed to load history:', err);
    } finally {
      setHistoryLoading(false);
    }
  }

  async function handleSaveSubject(e) {
    e.preventDefault();
    if (!formData.name.trim()) return;
    setSubmitting(true);
    setErrorMsg('');
    try {
      let savedSubj = null;
      if (viewMode === 'add') {
        savedSubj = await apiRequest('/subjects/', {
          method: 'POST',
          body: JSON.stringify({
            ...formData,
            code: formData.code.trim() || formData.name.slice(0, 4).toUpperCase(),
            target_attendance: parseFloat(formData.target_attendance),
          }),
        });
      } else if (viewMode === 'edit' && selectedSubject) {
        savedSubj = await apiRequest(`/subjects/${selectedSubject.id}`, {
          method: 'PUT',
          body: JSON.stringify({
            ...formData,
            target_attendance: parseFloat(formData.target_attendance),
          }),
        });
      }
      await loadSubjects();
      if (onSubjectsChanged) onSubjectsChanged();
      setViewMode('list');
    } catch (err) {
      setErrorMsg(err.message || 'Failed to save subject');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeleteClick(subj) {
    try {
      // First try standard delete
      await apiRequest(`/subjects/${subj.id}`, { method: 'DELETE' });
      await loadSubjects();
      if (onSubjectsChanged) onSubjectsChanged();
    } catch (err) {
      // Check if it's a 409 Conflict with history
      setDeleteConfirmSubject(subj);
      setDeleteWarning(err.message);
    }
  }

  async function handleForceDelete() {
    if (!deleteConfirmSubject) return;
    setDeleting(true);
    try {
      await apiRequest(`/subjects/${deleteConfirmSubject.id}?force=true`, { method: 'DELETE' });
      setDeleteConfirmSubject(null);
      await loadSubjects();
      if (onSubjectsChanged) onSubjectsChanged();
    } catch (err) {
      alert('Failed to delete subject: ' + err.message);
    } finally {
      setDeleting(false);
    }
  }

  if (!isOpen) return null;

  const colorOptions = [
    '#72C9BE', '#B7D4F4', '#D4C8F4', '#CADFCB',
    '#F4D5C2', '#F3DFAB', '#EABFC5', '#64748B'
  ];

  return (
    <div className="fixed inset-0 z-[60] bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white border border-[#E7EAF0] rounded-3xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-float overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="p-5 border-b border-[#E7EAF0] flex items-center justify-between bg-slate-50/60">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-[#CFEDE7] rounded-xl text-[#1A4B43]">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-800">
                {viewMode === 'list' && 'Manage Enrolled Subjects'}
                {viewMode === 'add' && 'Add New MBBS Subject'}
                {viewMode === 'edit' && `Edit Subject: ${selectedSubject?.name}`}
                {viewMode === 'history' && `${selectedSubject?.name} — Attendance History`}
              </h2>
              <p className="text-xs text-slate-400">
                {viewMode === 'list' && 'Track attendance metrics, customize faculty, and adjust target thresholds.'}
                {viewMode === 'add' && 'Enter subject details and required attendance threshold.'}
                {viewMode === 'edit' && 'Modify subject name, faculty, color, or target threshold.'}
                {viewMode === 'history' && 'Chronological record of every conducted, missed, and cancelled class.'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {viewMode === 'list' && (
              <button
                onClick={handleOpenAdd}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 shadow-xs transition-all cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Subject</span>
              </button>
            )}
            {(viewMode === 'add' || viewMode === 'edit' || viewMode === 'history') && (
              <button
                onClick={() => setViewMode('list')}
                className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors cursor-pointer"
              >
                Back to Subjects
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {errorMsg && (
            <div className="p-3.5 rounded-xl text-xs bg-rose-50 border border-rose-200 text-rose-700 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* VIEW: SUBJECTS LIST */}
          {viewMode === 'list' && (
            <>
              {loading ? (
                <div className="text-center py-12 text-slate-400 text-xs">Loading enrolled subjects...</div>
              ) : subjects.length === 0 ? (
                <div className="text-center py-12 bg-white border border-dashed border-[#E7EAF0] rounded-2xl p-8 shadow-card">
                  <BookOpen className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                  <h3 className="text-base font-bold text-slate-700">No subjects enrolled yet</h3>
                  <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
                    Add your MBBS subjects to track attendance, timetable schedules, and study goals.
                  </p>
                  <button
                    onClick={handleOpenAdd}
                    className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-[#72C9BE] text-slate-900 hover:bg-[#5bb8ac] shadow-xs"
                  >
                    <Plus className="w-4 h-4" />
                    Add First Subject
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {subjects.map((subj) => {
                    const isBelow = subj.is_below_target;
                    const isClose = !isBelow && subj.current_percentage < (subj.target_attendance + 5.0);

                    return (
                      <div
                        key={subj.id}
                        className="bg-white border border-[#E7EAF0] rounded-2xl p-4.5 flex flex-col justify-between hover:border-slate-300 transition-all shadow-card space-y-3"
                      >
                        {/* Subject Top Info */}
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-center gap-3">
                            <div
                              className="w-3 h-12 rounded-lg shrink-0 shadow-xs"
                              style={{ backgroundColor: subj.color || '#72C9BE' }}
                            />
                            <div>
                              <div className="flex items-center gap-2">
                                <h3 className="text-sm font-bold text-slate-800">{subj.name}</h3>
                                {subj.code && (
                                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 border border-slate-200">
                                    {subj.code}
                                  </span>
                                )}
                              </div>
                              <p className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
                                {subj.faculty ? (
                                  <span>{subj.faculty}</span>
                                ) : (
                                  <span className="text-slate-400">Faculty unassigned</span>
                                )}
                                {subj.academic_year && (
                                  <>
                                    <span>&bull;</span>
                                    <span>{subj.academic_year}</span>
                                  </>
                                )}
                              </p>
                            </div>
                          </div>

                          {/* Percentage Badge */}
                          <div className="text-right">
                            <span
                              className={`text-base font-bold font-mono ${
                                subj.classes_conducted > 0 && subj.current_percentage !== null
                                  ? (isBelow ? 'text-[#69242E]' : isClose ? 'text-[#6B4E17]' : 'text-[#1A4B43]')
                                  : 'text-slate-400'
                              }`}
                            >
                              {subj.classes_conducted > 0 && subj.current_percentage !== null && subj.current_percentage !== undefined
                                ? `${subj.current_percentage}%`
                                : '—'}
                            </span>
                            <div className="text-[10px] text-slate-400 font-medium">
                              Target: {subj.target_attendance}%
                            </div>
                          </div>
                        </div>

                        {/* Progress Bar */}
                        <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden relative">
                          <div
                            className={`h-full transition-all ${
                              isBelow ? 'bg-[#EABFC5]' : isClose ? 'bg-[#F3DFAB]' : 'bg-[#72C9BE]'
                            }`}
                            style={{ width: `${subj.classes_conducted > 0 && subj.current_percentage ? Math.min(100, subj.current_percentage) : 0}%` }}
                          />
                        </div>

                        {/* Stats Breakdown */}
                        <div className="grid grid-cols-4 gap-2 text-center text-[11px] bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                          <div>
                            <span className="text-slate-400 block text-[10px]">Conducted</span>
                            <span className="font-semibold text-slate-800">{subj.classes_conducted}</span>
                          </div>
                          <div>
                            <span className="text-[#1A4B43] block text-[10px]">Attended</span>
                            <span className="font-semibold text-[#1A4B43]">{subj.classes_attended}</span>
                          </div>
                          <div>
                            <span className="text-[#69242E] block text-[10px]">Absent</span>
                            <span className="font-semibold text-[#69242E]">{subj.classes_missed}</span>
                          </div>
                          <div>
                            <span className="text-[#6B4E17] block text-[10px]">Cancelled</span>
                            <span className="font-semibold text-[#6B4E17]">{subj.classes_cancelled || 0}</span>
                          </div>
                        </div>

                        {/* Recommendation Note */}
                        <div className="text-[11px] text-slate-500 pt-1">
                          {isBelow ? (
                            <span className="text-[#69242E] font-medium">
                              Need {subj.classes_needed_for_target} consecutive classes to reach {subj.target_attendance}%.
                            </span>
                          ) : (
                            <span className="text-[#1A4B43] font-medium">
                              Can safely miss {subj.bunk_buffer} class{subj.bunk_buffer !== 1 ? 'es' : ''} above {subj.target_attendance}%.
                            </span>
                          )}
                        </div>

                        {/* Actions */}
                        <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                          <button
                            onClick={() => handleOpenHistory(subj)}
                            className="inline-flex items-center gap-1.5 text-xs text-[#1A4B43] hover:underline font-semibold cursor-pointer"
                          >
                            <History className="w-3.5 h-3.5" />
                            <span>View History</span>
                          </button>

                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => handleOpenEdit(subj)}
                              title="Edit Subject"
                              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-800 hover:bg-slate-100 transition-colors"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => handleDeleteClick(subj)}
                              title="Delete Subject"
                              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}

          {/* VIEW: ADD / EDIT SUBJECT FORM */}
          {(viewMode === 'add' || viewMode === 'edit') && (
            <form onSubmit={handleSaveSubject} className="space-y-4 max-w-2xl mx-auto py-2">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Subject Name */}
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Subject Name <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Human Anatomy, Pathology, ENT"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3.5 py-2.5 text-sm text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                  />
                </div>

                {/* Short Code */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Short Code (e.g. ANAT, PATH)
                  </label>
                  <input
                    type="text"
                    placeholder="Auto-generated if empty"
                    value={formData.code}
                    onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                    className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3.5 py-2.5 text-sm text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                  />
                </div>

                {/* Faculty Name */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Faculty / Professor Name (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Dr. A. Sharma"
                    value={formData.faculty}
                    onChange={(e) => setFormData({ ...formData, faculty: e.target.value })}
                    className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3.5 py-2.5 text-sm text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                  />
                </div>

                {/* Academic Year / Phase */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Academic Year / Phase
                  </label>
                  <select
                    value={formData.academic_year}
                    onChange={(e) => setFormData({ ...formData, academic_year: e.target.value })}
                    className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3.5 py-2.5 text-sm text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                  >
                    <option value="MBBS 1st Year">MBBS 1st Year (Pre-clinical)</option>
                    <option value="MBBS 2nd Year">MBBS 2nd Year (Para-clinical)</option>
                    <option value="MBBS 3rd Year Part 1">MBBS 3rd Year Part 1</option>
                    <option value="MBBS 3rd Year Part 2">MBBS 3rd Year Part 2 (Final)</option>
                    <option value="Internship / CRMI">Internship / CRMI</option>
                  </select>
                </div>

                {/* Target Attendance */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-semibold text-slate-700">
                      Target Attendance %
                    </label>
                    <span className="text-xs font-bold text-[#1A4B43] font-mono">
                      {formData.target_attendance}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="50"
                    max="95"
                    step="1"
                    value={formData.target_attendance}
                    onChange={(e) => setFormData({ ...formData, target_attendance: Number(e.target.value) })}
                    className="w-full accent-[#72C9BE] cursor-pointer"
                  />
                  <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                    <span>50%</span>
                    <span className="text-[#1A4B43] font-semibold">75% (NMC Minimum)</span>
                    <span>95%</span>
                  </div>
                </div>

                {/* Color Identifier */}
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-slate-700 mb-2">
                    Subject Color Tag
                  </label>
                  <div className="flex items-center gap-3 flex-wrap">
                    {colorOptions.map((c) => (
                      <button
                        type="button"
                        key={c}
                        onClick={() => setFormData({ ...formData, color: c })}
                        className={`w-8 h-8 rounded-xl transition-transform ${
                          formData.color === c ? 'scale-110 ring-2 ring-slate-800 ring-offset-2 ring-offset-white shadow-xs' : 'opacity-70 hover:opacity-100'
                        }`}
                        style={{ backgroundColor: c }}
                      />
                    ))}
                  </div>
                </div>
              </div>

              <div className="pt-4 flex items-center justify-end gap-3 border-t border-[#E7EAF0]">
                <button
                  type="button"
                  onClick={() => setViewMode('list')}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || !formData.name.trim()}
                  className="px-6 py-2 rounded-xl text-xs font-semibold bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 disabled:opacity-50 transition-colors flex items-center gap-2 cursor-pointer shadow-xs"
                >
                  <Check className="w-4 h-4" />
                  <span>{submitting ? 'Saving...' : viewMode === 'add' ? 'Create Subject' : 'Update Subject'}</span>
                </button>
              </div>
            </form>
          )}

          {/* VIEW: SUBJECT HISTORY */}
          {viewMode === 'history' && (
            <div className="space-y-4">
              {historyLoading ? (
                <div className="text-center py-12 text-slate-400 text-xs">Loading attendance history...</div>
              ) : subjectHistory.length === 0 ? (
                <div className="text-center py-10 text-slate-400 text-xs">
                  No classes recorded for this subject yet.
                </div>
              ) : (
                <div className="space-y-2">
                  {subjectHistory.map((occ) => {
                    const status = occ.attendance?.status || (occ.status === 'cancelled' ? 'cancelled' : 'not_marked');
                    return (
                      <div
                        key={occ.id}
                        className="bg-white border border-[#E7EAF0] shadow-card rounded-xl p-3.5 flex items-center justify-between text-xs"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-800 flex items-center gap-1.5">
                              <Calendar className="w-3.5 h-3.5 text-slate-400" />
                              {new Date(occ.date).toLocaleDateString(undefined, {
                                weekday: 'short',
                                month: 'short',
                                day: 'numeric',
                              })}
                            </span>
                            <span className="text-slate-400 font-mono">
                              {occ.start_time?.slice(0, 5)} – {occ.end_time?.slice(0, 5)}
                            </span>
                            {occ.is_extra_class && (
                              <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#D4C8F4]/40 text-[#4C1D95]">
                                Extra Class
                              </span>
                            )}
                          </div>
                          {occ.topics && occ.topics.length > 0 && (
                            <p className="text-[11px] text-slate-500 mt-1">
                              Topic: {occ.topics.map((t) => t.title).join(', ')}
                            </p>
                          )}
                          {occ.notes && (
                            <p className="text-[11px] text-slate-400 italic mt-0.5">{occ.notes}</p>
                          )}
                        </div>

                        <div>
                          {status === 'present' && (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-[#CFEDE7] text-[#1A4B43]">
                              <CheckCircle2 className="w-3.5 h-3.5" /> Present
                            </span>
                          )}
                          {status === 'absent' && (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-[#EABFC5]/40 text-[#69242E]">
                              <X className="w-3.5 h-3.5" /> Absent
                            </span>
                          )}
                          {status === 'cancelled' && (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-[#F3DFAB]/50 text-[#6B4E17]">
                              <AlertTriangle className="w-3.5 h-3.5" /> Cancelled
                            </span>
                          )}
                          {status === 'not_marked' && (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-500">
                              <Clock className="w-3.5 h-3.5" /> Pending
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* CONFIRM FORCE DELETE DIALOG */}
      {deleteConfirmSubject && (
        <div className="fixed inset-0 z-60 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white border border-rose-200 rounded-2xl w-full max-w-md p-5 space-y-4 shadow-float animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center gap-3 text-rose-600">
              <div className="p-2 bg-rose-50 rounded-xl">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-slate-900">Delete Subject with History?</h3>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              {deleteWarning || `Subject '${deleteConfirmSubject.name}' contains existing attendance records. Deleting this subject will permanently remove all associated classes and attendance logs.`}
            </p>

            <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-[11px] text-amber-800">
              ⚠️ This action cannot be undone. Historical attendance records will be permanently removed.
            </div>

            <div className="flex items-center justify-end gap-3 pt-2 border-t border-[#E7EAF0]">
              <button
                type="button"
                onClick={() => setDeleteConfirmSubject(null)}
                className="px-4 py-2 rounded-xl text-xs font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100"
              >
                Keep Subject
              </button>
              <button
                type="button"
                onClick={handleForceDelete}
                disabled={deleting}
                className="px-5 py-2 rounded-xl text-xs font-semibold bg-rose-600 hover:bg-rose-700 text-white disabled:opacity-50 transition-colors flex items-center gap-2 cursor-pointer shadow-xs"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>{deleting ? 'Deleting...' : 'Confirm & Delete'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
