import React, { useState, useEffect } from 'react';
import {
  Calendar,
  Clock,
  BookOpen,
  User,
  MapPin,
  Trash2,
  Plus,
  Check,
  X,
  AlertTriangle,
  Sparkles,
  HelpCircle,
  ShieldCheck
} from 'lucide-react';
import { apiRequest } from '../api/client';

const DAYS = [
  { value: 0, label: 'Monday' },
  { value: 1, label: 'Tuesday' },
  { value: 2, label: 'Wednesday' },
  { value: 3, label: 'Thursday' },
  { value: 4, label: 'Friday' },
  { value: 5, label: 'Saturday' },
  { value: 6, label: 'Sunday' },
];

export default function TimetableReviewModal({
  isOpen,
  previewData,
  onClose,
  onImportSuccess
}) {
  const [items, setItems] = useState([]);
  const [existingSubjects, setExistingSubjects] = useState([]);
  const [duplicateMode, setDuplicateMode] = useState('skip'); // 'skip', 'replace', 'keep_all'
  const [scheduleStartsFrom, setScheduleStartsFrom] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  });
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    if (isOpen && previewData) {
      setItems(
        (previewData.extracted_items || []).map((it, idx) => ({
          ...it,
          temp_id: `item_${idx}_${Date.now()}`,
          is_new_mode: it.is_new_subject || !it.matched_subject_id,
        }))
      );
      loadSubjects();
      setErrorMsg('');
    }
  }, [isOpen, previewData]);

  async function loadSubjects() {
    try {
      const data = await apiRequest('/subjects/');
      setExistingSubjects(data || []);
    } catch (err) {
      console.error('Failed to load user subjects:', err);
    }
  }

  function handleItemChange(tempId, field, value) {
    setItems((prev) =>
      prev.map((item) => {
        if (item.temp_id !== tempId) return item;
        const updated = { ...item, [field]: value };
        if (field === 'day_of_week') {
          const dayObj = DAYS.find((d) => d.value === parseInt(value, 10));
          updated.day_name = dayObj ? dayObj.label : 'Monday';
          updated.day_of_week = parseInt(value, 10);
        }
        return updated;
      })
    );
  }

  function handleSubjectSelect(tempId, value) {
    setItems((prev) =>
      prev.map((item) => {
        if (item.temp_id !== tempId) return item;
        if (value === '__new__') {
          return {
            ...item,
            is_new_mode: true,
            matched_subject_id: null,
            subject_name: item.subject_name || 'New Subject',
          };
        } else {
          const found = existingSubjects.find((s) => s.id === value);
          return {
            ...item,
            is_new_mode: false,
            matched_subject_id: value,
            matched_subject_name: found ? found.name : item.subject_name,
            subject_name: found ? found.name : item.subject_name,
          };
        }
      })
    );
  }

  function handleAddRow() {
    const defaultSubj = existingSubjects[0];
    const newItem = {
      temp_id: `item_manual_${Date.now()}`,
      day_of_week: 0,
      day_name: 'Monday',
      start_time: '09:00',
      end_time: '10:00',
      subject_name: defaultSubj ? defaultSubj.name : 'Anatomy',
      matched_subject_id: defaultSubj ? defaultSubj.id : null,
      matched_subject_name: defaultSubj ? defaultSubj.name : null,
      is_new_mode: !defaultSubj,
      faculty: '',
      room: '',
      confidence: 1.0,
      has_conflict: false,
    };
    setItems([...items, newItem]);
  }

  function handleDeleteRow(tempId) {
    setItems((prev) => prev.filter((item) => item.temp_id !== tempId));
  }

  async function handleConfirmImport() {
    if (items.length === 0) {
      setErrorMsg('Cannot import an empty timetable. Add at least one class row.');
      return;
    }
    setSubmitting(true);
    setErrorMsg('');
    try {
      const payload = {
        items: items.map((it) => ({
          day_of_week: parseInt(it.day_of_week, 10),
          day_name: it.day_name,
          start_time: it.start_time.length === 5 ? it.start_time : it.start_time.slice(0, 5),
          end_time: it.end_time.length === 5 ? it.end_time : it.end_time.slice(0, 5),
          subject_name: it.subject_name,
          matched_subject_id: it.is_new_mode ? null : it.matched_subject_id,
          faculty: it.faculty || '',
          room: it.room || '',
        })),
        duplicate_mode: duplicateMode,
        schedule_starts_from: scheduleStartsFrom || null,
      };

      const res = await apiRequest('/timetable/import/confirm', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      alert(res.message || 'Timetable successfully imported!');
      onClose();
      if (onImportSuccess) onImportSuccess();
    } catch (err) {
      setErrorMsg(err.message || 'Import failed');
    } finally {
      setSubmitting(false);
    }
  }

  if (!isOpen) return null;

  const conflictCount = items.filter((i) => i.has_conflict).length;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-2 sm:p-4">
      <div className="bg-white border border-[#E7EAF0] rounded-3xl w-full max-w-5xl max-h-[92vh] flex flex-col shadow-float overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-[#E7EAF0] flex items-center justify-between bg-slate-50/60">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-[#CFEDE7] rounded-xl text-[#1A4B43]">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base sm:text-lg font-bold text-slate-800 flex items-center gap-2">
                Review Extracted Timetable
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[#CFEDE7] text-[#1A4B43]">
                  {items.length} classes
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Verify and correct detected subjects, days, and times before saving to your medical timetable.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={submitting}
            className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
          {/* Warnings Banner */}
          {previewData?.warnings && previewData.warnings.length > 0 && (
            <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800 space-y-1">
              {previewData.warnings.map((w, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <HelpCircle className="w-3.5 h-3.5 shrink-0 text-amber-600" />
                  <span>{w}</span>
                </div>
              ))}
            </div>
          )}

          {/* Duplicate Conflict Warning & Mode Selector */}
          {conflictCount > 0 && (
            <div className="p-4 rounded-xl bg-amber-50/50 border border-amber-200 space-y-3">
              <div className="flex items-start gap-2.5 text-amber-800">
                <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5 text-amber-600" />
                <div>
                  <h4 className="text-xs font-bold text-slate-900">
                    {conflictCount} Class Conflict{conflictCount !== 1 ? 's' : ''} Detected
                  </h4>
                  <p className="text-xs text-slate-600 mt-0.5">
                    Some classes overlap with existing recurring rules in your timetable. Choose how to handle them:
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs pt-1">
                <label
                  className={`flex items-center gap-2 p-2.5 rounded-xl border cursor-pointer transition-all ${
                    duplicateMode === 'skip'
                      ? 'bg-[#CFEDE7] border-[#72C9BE] text-[#1A4B43] font-semibold'
                      : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  <input
                    type="radio"
                    name="dup_mode"
                    value="skip"
                    checked={duplicateMode === 'skip'}
                    onChange={(e) => setDuplicateMode(e.target.value)}
                    className="accent-[#72C9BE]"
                  />
                  <span>Skip Duplicates (Keep existing)</span>
                </label>

                <label
                  className={`flex items-center gap-2 p-2.5 rounded-xl border cursor-pointer transition-all ${
                    duplicateMode === 'replace'
                      ? 'bg-[#CFEDE7] border-[#72C9BE] text-[#1A4B43] font-semibold'
                      : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  <input
                    type="radio"
                    name="dup_mode"
                    value="replace"
                    checked={duplicateMode === 'replace'}
                    onChange={(e) => setDuplicateMode(e.target.value)}
                    className="accent-[#72C9BE]"
                  />
                  <span>Replace Matching Classes</span>
                </label>

                <label
                  className={`flex items-center gap-2 p-2.5 rounded-xl border cursor-pointer transition-all ${
                    duplicateMode === 'keep_all'
                      ? 'bg-[#CFEDE7] border-[#72C9BE] text-[#1A4B43] font-semibold'
                      : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  <input
                    type="radio"
                    name="dup_mode"
                    value="keep_all"
                    checked={duplicateMode === 'keep_all'}
                    onChange={(e) => setDuplicateMode(e.target.value)}
                    className="accent-[#72C9BE]"
                  />
                  <span>Keep All (Allow Duplicates)</span>
                </label>
              </div>
            </div>
          )}

          {errorMsg && (
            <div className="p-3.5 rounded-xl text-xs bg-rose-50 border border-rose-200 text-rose-700 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Schedule Effective Start Date */}
          <div className="p-3.5 sm:p-4 rounded-2xl bg-white border border-[#E7EAF0] shadow-soft flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-[#CFEDE7] text-[#1A4B43]">
                <Calendar className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs sm:text-sm font-semibold text-slate-800 flex items-center gap-2">
                  <span>Schedule starts from</span>
                  <span className="text-[10px] font-medium text-[#1A4B43] bg-[#CFEDE7] px-2 py-0.5 rounded-full">
                    Default: Today
                  </span>
                </h4>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Recurring classes and attendance check-ins will only be tracked from this date forward.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 self-start sm:self-auto">
              <input
                type="date"
                value={scheduleStartsFrom}
                onChange={(e) => setScheduleStartsFrom(e.target.value)}
                className="px-3 py-1.5 text-xs sm:text-sm bg-[#F7F8FC] border border-[#E7EAF0] rounded-xl text-slate-700 font-semibold focus:border-[#72C9BE] focus:outline-none transition-all"
              />
            </div>
          </div>

          {/* Desktop Table View (>= 768px) */}
          <div className="hidden md:block overflow-x-auto rounded-2xl border border-[#E7EAF0]">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-[#E7EAF0]">
                <tr>
                  <th className="p-3">Day</th>
                  <th className="p-3">Start</th>
                  <th className="p-3">End</th>
                  <th className="p-3">Subject</th>
                  <th className="p-3">Faculty</th>
                  <th className="p-3">Room / Venue</th>
                  <th className="p-3 text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E7EAF0] bg-white">
                {items.map((item) => (
                  <tr
                    key={item.temp_id}
                    className={`hover:bg-slate-50 transition-colors ${
                      item.has_conflict ? 'bg-amber-50/40' : ''
                    }`}
                  >
                    {/* Day */}
                    <td className="p-2.5">
                      <select
                        value={item.day_of_week}
                        onChange={(e) => handleItemChange(item.temp_id, 'day_of_week', e.target.value)}
                        className="bg-slate-50 border border-[#E7EAF0] rounded-lg px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE]"
                      >
                        {DAYS.map((d) => (
                          <option key={d.value} value={d.value}>
                            {d.label}
                          </option>
                        ))}
                      </select>
                    </td>

                    {/* Start Time */}
                    <td className="p-2.5">
                      <input
                        type="time"
                        value={item.start_time.slice(0, 5)}
                        onChange={(e) => handleItemChange(item.temp_id, 'start_time', e.target.value)}
                        className="bg-slate-50 border border-[#E7EAF0] rounded-lg px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE] font-mono"
                      />
                    </td>

                    {/* End Time */}
                    <td className="p-2.5">
                      <input
                        type="time"
                        value={item.end_time.slice(0, 5)}
                        onChange={(e) => handleItemChange(item.temp_id, 'end_time', e.target.value)}
                        className="bg-slate-50 border border-[#E7EAF0] rounded-lg px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE] font-mono"
                      />
                    </td>

                    {/* Subject Selector & Creator */}
                    <td className="p-2.5">
                      {item.is_new_mode ? (
                        <div className="flex items-center gap-1.5">
                          <input
                            type="text"
                            placeholder="Enter Subject Name"
                            value={item.subject_name}
                            onChange={(e) => handleItemChange(item.temp_id, 'subject_name', e.target.value)}
                            className="bg-white border border-[#72C9BE] rounded-lg px-2 py-1.5 text-xs text-[#1A4B43] focus:outline-none focus:border-[#72C9BE] w-36 font-semibold"
                          />
                          <span className="text-[10px] uppercase font-bold text-[#1A4B43] px-1.5 py-0.5 bg-[#CFEDE7] rounded">
                            New
                          </span>
                        </div>
                      ) : (
                        <select
                          value={item.matched_subject_id || ''}
                          onChange={(e) => handleSubjectSelect(item.temp_id, e.target.value)}
                          className="bg-slate-50 border border-[#E7EAF0] rounded-lg px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE] max-w-[170px] truncate"
                        >
                          {existingSubjects.map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.name}
                            </option>
                          ))}
                          <option value="__new__">+ Create New Subject...</option>
                        </select>
                      )}
                    </td>

                    {/* Faculty */}
                    <td className="p-2.5">
                      <input
                        type="text"
                        placeholder="e.g. Dr. Sharma"
                        value={item.faculty || ''}
                        onChange={(e) => handleItemChange(item.temp_id, 'faculty', e.target.value)}
                        className="bg-slate-50 border border-[#E7EAF0] rounded-lg px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE] w-28"
                      />
                    </td>

                    {/* Room */}
                    <td className="p-2.5">
                      <input
                        type="text"
                        placeholder="e.g. LT-1"
                        value={item.room || ''}
                        onChange={(e) => handleItemChange(item.temp_id, 'room', e.target.value)}
                        className="bg-slate-50 border border-[#E7EAF0] rounded-lg px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE] w-20"
                      />
                    </td>

                    {/* Action */}
                    <td className="p-2.5 text-center">
                      <button
                        onClick={() => handleDeleteRow(item.temp_id)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile Card Stack (< 768px) */}
          <div className="md:hidden space-y-3">
            {items.map((item, index) => (
              <div
                key={item.temp_id}
                className="bg-white border border-[#E7EAF0] rounded-2xl p-4 space-y-3 shadow-card"
              >
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold text-[#1A4B43] font-mono">#{index + 1}</span>
                    <select
                      value={item.day_of_week}
                      onChange={(e) => handleItemChange(item.temp_id, 'day_of_week', e.target.value)}
                      className="bg-slate-50 border border-[#E7EAF0] rounded-lg px-2 py-1 text-xs text-slate-800 focus:outline-none focus:border-[#72C9BE] font-semibold"
                    >
                      {DAYS.map((d) => (
                        <option key={d.value} value={d.value}>
                          {d.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <button
                    onClick={() => handleDeleteRow(item.temp_id)}
                    className="p-1 text-slate-400 hover:text-rose-600"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[10px] text-slate-500 font-medium mb-1">Start Time</label>
                    <input
                      type="time"
                      value={item.start_time.slice(0, 5)}
                      onChange={(e) => handleItemChange(item.temp_id, 'start_time', e.target.value)}
                      className="w-full bg-slate-50 border border-[#E7EAF0] rounded-lg p-1.5 text-xs text-slate-800 font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-slate-500 font-medium mb-1">End Time</label>
                    <input
                      type="time"
                      value={item.end_time.slice(0, 5)}
                      onChange={(e) => handleItemChange(item.temp_id, 'end_time', e.target.value)}
                      className="w-full bg-slate-50 border border-[#E7EAF0] rounded-lg p-1.5 text-xs text-slate-800 font-mono"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[10px] text-slate-500 font-medium mb-1">Subject</label>
                  {item.is_new_mode ? (
                    <input
                      type="text"
                      placeholder="Subject Name"
                      value={item.subject_name}
                      onChange={(e) => handleItemChange(item.temp_id, 'subject_name', e.target.value)}
                      className="w-full bg-white border border-[#72C9BE] rounded-lg p-1.5 text-xs text-[#1A4B43] font-semibold"
                    />
                  ) : (
                    <select
                      value={item.matched_subject_id || ''}
                      onChange={(e) => handleSubjectSelect(item.temp_id, e.target.value)}
                      className="w-full bg-slate-50 border border-[#E7EAF0] rounded-lg p-1.5 text-xs text-slate-800"
                    >
                      {existingSubjects.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                      <option value="__new__">+ Create New Subject...</option>
                    </select>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[10px] text-slate-500 font-medium mb-1">Faculty</label>
                    <input
                      type="text"
                      placeholder="e.g. Dr. Sharma"
                      value={item.faculty || ''}
                      onChange={(e) => handleItemChange(item.temp_id, 'faculty', e.target.value)}
                      className="w-full bg-slate-50 border border-[#E7EAF0] rounded-lg p-1.5 text-xs text-slate-800"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-slate-500 font-medium mb-1">Room</label>
                    <input
                      type="text"
                      placeholder="e.g. LT-1"
                      value={item.room || ''}
                      onChange={(e) => handleItemChange(item.temp_id, 'room', e.target.value)}
                      className="w-full bg-slate-50 border border-[#E7EAF0] rounded-lg p-1.5 text-xs text-slate-800"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Add Row Button */}
          <div className="flex justify-start">
            <button
              type="button"
              onClick={handleAddRow}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5 text-[#72C9BE]" />
              <span>Add Class Row</span>
            </button>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 sm:p-5 border-t border-[#E7EAF0] bg-slate-50/60 flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2 rounded-xl text-xs font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100"
          >
            Cancel Import
          </button>

          <button
            type="button"
            onClick={handleConfirmImport}
            disabled={submitting || items.length === 0}
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-semibold bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 shadow-xs disabled:opacity-50 transition-all cursor-pointer active:scale-95"
          >
            <ShieldCheck className="w-4 h-4" />
            <span>{submitting ? 'Importing Classes...' : `Confirm & Import (${items.length})`}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
