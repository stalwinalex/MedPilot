import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  GraduationCap,
  Plus,
  Calendar,
  Clock,
  Trash2,
  Edit2,
  Sparkles,
  BookOpen,
  CheckCircle2,
  AlertCircle,
  X,
  Check
} from 'lucide-react';
import { apiRequest } from '../api/client';

export default function ExamsPage() {
  const navigate = useNavigate();
  const [exams, setExams] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [loading, setLoading] = useState(true);

  // Modal & Topic state
  const [modalOpen, setModalOpen] = useState(false);
  const [editingExamId, setEditingExamId] = useState(null);
  const [examForm, setExamForm] = useState({
    name: '',
    subject_id: '',
    syllabus_portion: '',
    exam_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
    exam_type: 'Internal Assessment',
    target_score: 75.0,
    prep_status: 'not_started'
  });
  const [selectedTopics, setSelectedTopics] = useState([]);
  const [editingTopicIndex, setEditingTopicIndex] = useState(null);
  const [editingTopicText, setEditingTopicText] = useState('');
  const [topicInput, setTopicInput] = useState('');
  const [suggestedTopics, setSuggestedTopics] = useState([]);
  const [availablePortions, setAvailablePortions] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [validationWarning, setValidationWarning] = useState(null);
  const [validatingTopic, setValidatingTopic] = useState(false);
  const [suggestionMeta, setSuggestionMeta] = useState(null);

  const loadExams = async () => {
    try {
      setLoading(true);
      const [examList, subjList] = await Promise.all([
        apiRequest('/exams/'),
        apiRequest('/subjects/')
      ]);
      setExams(examList);
      setSubjects(subjList);
      if (subjList.length > 0 && !examForm.subject_id) {
        setExamForm(prev => ({ ...prev, subject_id: subjList[0].id }));
      }
    } catch (err) {
      console.error('Error loading exams:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadExams();
  }, []);

  const handleOpenModal = () => {
    setEditingExamId(null);
    setSelectedTopics([]);
    setEditingTopicIndex(null);
    setTopicInput('');
    setValidationWarning(null);
    setSuggestionMeta(null);
    setExamForm({
      name: '',
      subject_id: subjects.length > 0 ? subjects[0].id : '',
      syllabus_portion: '',
      exam_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
      exam_type: 'Internal Assessment',
      target_score: 75.0,
      prep_status: 'not_started'
    });
    setModalOpen(true);
  };

  const handleEditExam = (e) => {
    setEditingExamId(e.id);
    setSelectedTopics(Array.isArray(e.important_topics) ? [...e.important_topics] : []);
    setEditingTopicIndex(null);
    setTopicInput('');
    setValidationWarning(null);
    setSuggestionMeta(null);
    setExamForm({
      name: e.name || '',
      subject_id: e.subject_id || (subjects[0]?.id || ''),
      syllabus_portion: e.syllabus_portion || '',
      exam_date: e.exam_date || new Date().toISOString().split('T')[0],
      exam_type: e.exam_type || 'Internal Assessment',
      target_score: e.target_score || 75.0,
      prep_status: e.prep_status || 'not_started'
    });
    setModalOpen(true);
  };

  useEffect(() => {
    if (!examForm.subject_id) return;
    let active = true;
    const fetchSuggestions = async () => {
      try {
        setLoadingSuggestions(true);
        const queryParams = new URLSearchParams({ subject_id: examForm.subject_id });
        if (examForm.syllabus_portion && examForm.syllabus_portion.trim()) {
          queryParams.set('portion', examForm.syllabus_portion.trim());
        }
        if (examForm.exam_date) {
          const days = Math.round((new Date(examForm.exam_date) - new Date()) / 86400000);
          if (!isNaN(days)) queryParams.set('days_remaining', days);
        }
        if (examForm.target_score) {
          queryParams.set('target_score', examForm.target_score);
        }
        const res = await apiRequest(`/exams/topic-suggestions?${queryParams.toString()}`);
        if (active) {
          setSuggestedTopics(res?.suggestions || []);
          if (Array.isArray(res?.available_portions)) {
            setAvailablePortions(res.available_portions);
          }
          setSuggestionMeta({
            confidence: res?.confidence,
            matched_portion: res?.matched_portion,
            match_message: res?.match_message,
            ai_ranked: res?.ai_ranked,
            ai_provider: res?.ai_provider
          });
        }
      } catch (err) {
        console.error('Error loading topic suggestions:', err);
      } finally {
        if (active) setLoadingSuggestions(false);
      }
    };
    fetchSuggestions();
    return () => { active = false; };
  }, [examForm.subject_id, examForm.syllabus_portion, examForm.exam_date, examForm.target_score]);

  const handleAddTopic = async (topicToAdd, bypassValidation = false) => {
    const trimmed = (topicToAdd || '').trim();
    if (!trimmed) return;

    if (selectedTopics.some(t => t.toLowerCase() === trimmed.toLowerCase())) {
      setTopicInput('');
      setValidationWarning(null);
      return;
    }

    if (!bypassValidation && examForm.subject_id) {
      try {
        setValidatingTopic(true);
        const res = await apiRequest('/exams/validate-topic', {
          method: 'POST',
          body: JSON.stringify({
            subject_id: examForm.subject_id,
            topic: trimmed
          })
        });
        if (!res.is_valid && res.warning) {
          setValidationWarning({
            topic: trimmed,
            warning: res.warning,
            suggested_subject: res.suggested_subject
          });
          setValidatingTopic(false);
          return;
        }
      } catch (err) {
        console.error('Topic validation check failed:', err);
      } finally {
        setValidatingTopic(false);
      }
    }

    setSelectedTopics(prev => [...prev, trimmed]);
    setTopicInput('');
    setValidationWarning(null);
  };

  const handleRemoveTopic = (indexToRemove) => {
    setSelectedTopics(prev => prev.filter((_, idx) => idx !== indexToRemove));
    if (editingTopicIndex === indexToRemove) {
      setEditingTopicIndex(null);
      setEditingTopicText('');
    }
  };

  const handleStartEditTopic = (index) => {
    setEditingTopicIndex(index);
    setEditingTopicText(selectedTopics[index] || '');
  };

  const handleSaveEditTopic = (index) => {
    const trimmed = editingTopicText.trim();
    if (trimmed) {
      setSelectedTopics(prev => prev.map((t, idx) => (idx === index ? trimmed : t)));
    }
    setEditingTopicIndex(null);
    setEditingTopicText('');
  };

  const handleCancelEditTopic = () => {
    setEditingTopicIndex(null);
    setEditingTopicText('');
  };

  const handleSaveExam = async (e) => {
    e.preventDefault();
    try {
      let finalTopics = [...selectedTopics];
      if (topicInput.trim() && !validationWarning) {
        if (!finalTopics.some(t => t.toLowerCase() === topicInput.trim().toLowerCase())) {
          finalTopics.push(topicInput.trim());
        }
      }
      const payload = {
        name: examForm.name,
        subject_id: examForm.subject_id,
        exam_date: examForm.exam_date,
        exam_type: examForm.exam_type,
        target_score: parseFloat(examForm.target_score),
        syllabus_portion: examForm.syllabus_portion?.trim() || null,
        important_topics: finalTopics,
        prep_status: examForm.prep_status
      };

      if (editingExamId) {
        await apiRequest(`/exams/${editingExamId}`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        });
      } else {
        await apiRequest('/exams/', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
      }
      setModalOpen(false);
      setEditingExamId(null);
      setSelectedTopics([]);
      setTopicInput('');
      setValidationWarning(null);
      loadExams();
    } catch (err) {
      alert(`Error saving exam: ${err.message}`);
    }
  };

  const handleDeleteExam = async (examId) => {
    if (!confirm('Are you sure you want to remove this exam?')) return;
    try {
      await apiRequest(`/exams/${examId}`, { method: 'DELETE' });
      loadExams();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleStatusChange = async (examId, newStatus) => {
    try {
      await apiRequest(`/exams/${examId}`, {
        method: 'PUT',
        body: JSON.stringify({ prep_status: newStatus })
      });
      loadExams();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-6 pb-24">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#E7EAF0] pb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-800 flex items-center gap-2.5">
            <span className="p-2 rounded-xl bg-[#D4C8F4]/50 text-[#4C1D95]">
              <GraduationCap className="w-5 h-5" />
            </span>
            <span>Academic Exam Schedule</span>
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Keep track of university prof exams, internal assessments, and clinical vivas with calm countdowns.
          </p>
        </div>

        <button
          onClick={handleOpenModal}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 text-sm font-semibold shadow-sm transition-all active:scale-95 self-start cursor-pointer"
        >
          <Plus className="w-4 h-4 stroke-[2.5]" />
          <span>Add Exam</span>
        </button>
      </div>

      {/* Loading state */}
      {loading ? (
        <div className="p-12 text-center rounded-2xl bg-white border border-[#E7EAF0] shadow-card">
          <div className="w-6 h-6 border-2 border-[#72C9BE] border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p className="text-xs text-slate-500">Loading exams...</p>
        </div>
      ) : exams.length === 0 ? (
        <div className="p-12 text-center rounded-2xl bg-white border border-dashed border-[#E7EAF0] shadow-card space-y-3">
          <GraduationCap className="w-10 h-10 text-slate-300 mx-auto" />
          <h3 className="text-slate-800 font-semibold text-base">No upcoming exams recorded</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Add upcoming internal assessments or university prof exams to keep deadlines clear and study tasks organized.
          </p>
          <button
            onClick={handleOpenModal}
            className="px-4 py-2 rounded-xl bg-[#CFEDE7] hover:bg-[#bce6dc] text-[#1A4B43] text-xs font-semibold inline-flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add First Exam</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {exams.map((e) => {
            const isUrgent = e.days_remaining <= 5;
            return (
              <div
                key={e.id}
                className={`p-5 rounded-2xl border transition-all flex flex-col justify-between space-y-4 shadow-card hover:shadow-soft ${
                  isUrgent
                    ? 'bg-[#FCF9F7] border-[#F4D5C2]'
                    : 'bg-white border-[#E7EAF0]'
                }`}
              >
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="font-bold text-slate-800 text-base block">{e.name}</span>
                      <span className="text-xs font-semibold text-[#1A4B43] mt-0.5 block">
                        {e.subject?.name || 'Subject'}
                      </span>
                    </div>

                    <div className="text-right shrink-0">
                      <span className={`text-xl font-bold block ${
                        isUrgent ? 'text-[#7C2D12]' : 'text-slate-800'
                      }`}>
                        {e.days_remaining}
                      </span>
                      <span className="text-[10px] uppercase font-semibold text-slate-400">
                        {e.days_remaining === 1 ? 'Day Left' : 'Days Left'}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs text-slate-600 bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                    <span className="flex items-center gap-1.5 font-medium">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      {e.exam_date}
                    </span>
                    <span className="font-semibold text-slate-700">{e.exam_type}</span>
                  </div>

                  {e.syllabus_portion && (
                    <div className="flex items-center gap-1.5 text-xs text-[#3C2D69] bg-[#EAE5F8]/70 px-2.5 py-1 rounded-xl border border-[#D4C8F4]">
                      <BookOpen className="w-3.5 h-3.5 text-[#6B46C1] shrink-0" />
                      <span className="font-semibold truncate">Portion: {e.syllabus_portion}</span>
                    </div>
                  )}

                  {/* Important Topics */}
                  {e.important_topics?.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">
                        High-Yield Topics:
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {e.important_topics.map((t, idx) => {
                          const warning = e.topic_warnings?.find(
                            (w) => w.topic?.toLowerCase() === String(t).toLowerCase()
                          );
                          return (
                            <span
                              key={idx}
                              title={warning ? warning.warning : undefined}
                              className={`text-[11px] px-2 py-0.5 rounded-md border inline-flex items-center gap-1 ${
                                warning
                                  ? 'bg-amber-50 text-amber-800 border-amber-200 font-medium'
                                  : 'bg-slate-100 text-slate-600 border-slate-200'
                              }`}
                            >
                              {warning && <AlertCircle className="w-2.5 h-2.5 text-amber-600 shrink-0" />}
                              <span>{t}</span>
                            </span>
                          );
                        })}
                      </div>
                      {e.topic_warnings?.length > 0 && (
                        <div className="flex items-center gap-1 text-[10px] text-amber-700 font-medium bg-amber-50/70 px-2 py-1 rounded-md border border-amber-100 mt-1">
                          <AlertCircle className="w-3 h-3 text-amber-600 shrink-0" />
                          <span>
                            {e.topic_warnings.length} topic flagged for cross-subject review. Saved data preserved.
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="pt-3 border-t border-[#E7EAF0] space-y-3">
                  {/* Preparation status selector */}
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-500 font-medium text-[11px]">Prep Status:</span>
                    <select
                      value={e.prep_status}
                      onChange={(ev) => handleStatusChange(e.id, ev.target.value)}
                      className="py-1 px-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-700 focus:outline-none focus:border-[#72C9BE]"
                    >
                      <option value="not_started">Not Started</option>
                      <option value="in_progress">In Progress</option>
                      <option value="revision_needed">Revision Needed</option>
                      <option value="well_prepared">Well Prepared</option>
                    </select>
                  </div>

                  <div className="flex items-center justify-between gap-2">
                    <button
                      onClick={() => navigate(`/planner`)}
                      className="flex-1 py-1.5 rounded-xl bg-[#CFEDE7] text-[#1A4B43] hover:bg-[#bce6dc] text-xs font-semibold transition-colors flex items-center justify-center gap-1.5"
                    >
                      <BookOpen className="w-3.5 h-3.5" />
                      <span>Plan Tasks</span>
                    </button>
                    <button
                      onClick={() => handleEditExam(e)}
                      className="p-1.5 rounded-xl text-slate-400 hover:text-[#1A4B43] hover:bg-[#CFEDE7]/40 transition-colors cursor-pointer"
                      title="Edit Exam"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDeleteExam(e.id)}
                      className="p-1.5 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                      title="Delete Exam"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* MODAL: Add / Edit Exam */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="bg-white border border-[#E7EAF0] rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-float max-h-[92vh] overflow-y-auto animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <h3 className="text-base font-bold text-slate-800 flex items-center gap-2">
                <span className="p-1.5 rounded-lg bg-[#D4C8F4]/50 text-[#4C1D95]">
                  <GraduationCap className="w-4 h-4" />
                </span>
                <span>{editingExamId ? 'Edit Examination' : 'Add Upcoming Examination'}</span>
              </h3>
              <button
                onClick={() => setModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveExam} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Exam Name</label>
                <input
                  type="text"
                  required
                  value={examForm.name}
                  onChange={(e) => setExamForm({ ...examForm, name: e.target.value })}
                  placeholder="e.g. 2nd Internal Assessment or University Prof"
                  className="w-full py-2.5 px-3.5 bg-slate-50 border border-[#E7EAF0] rounded-xl text-slate-800 placeholder-slate-400 text-sm focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Subject</label>
                  <select
                    value={examForm.subject_id}
                    onChange={(e) => {
                      setExamForm({ ...examForm, subject_id: e.target.value, syllabus_portion: '' });
                      setValidationWarning(null);
                    }}
                    className="w-full py-2.5 px-3 bg-slate-50 border border-[#E7EAF0] rounded-xl text-slate-800 text-sm focus:outline-none focus:bg-white focus:border-[#72C9BE]"
                  >
                    {subjects.map((s) => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Exam Date</label>
                  <input
                    type="date"
                    required
                    value={examForm.exam_date}
                    onChange={(e) => setExamForm({ ...examForm, exam_date: e.target.value })}
                    className="w-full py-2.5 px-3 bg-slate-50 border border-[#E7EAF0] rounded-xl text-slate-800 text-sm focus:outline-none focus:bg-white focus:border-[#72C9BE]"
                  />
                </div>
              </div>

              {/* Exam Portion / Unit / Syllabus Field */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="block text-slate-700 font-semibold">
                    Exam Portion / Unit / Syllabus <span className="text-slate-400 font-normal">(Optional)</span>
                  </label>
                  {examForm.syllabus_portion && (
                    <button
                      type="button"
                      onClick={() => setExamForm({ ...examForm, syllabus_portion: '' })}
                      className="text-[10px] text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
                    >
                      Clear Portion
                    </button>
                  )}
                </div>
                <input
                  type="text"
                  value={examForm.syllabus_portion}
                  onChange={(e) => setExamForm({ ...examForm, syllabus_portion: e.target.value })}
                  placeholder="e.g. Upper Limb, Cardiovascular System, Carbohydrate Metabolism"
                  className="w-full py-2.5 px-3.5 bg-slate-50 border border-[#E7EAF0] rounded-xl text-slate-800 placeholder-slate-400 text-xs focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                />

                {/* AI-Assisted Portion Matching Confidence Feedback */}
                {examForm.syllabus_portion && suggestionMeta?.confidence === 'medium' && suggestionMeta?.matched_portion && examForm.syllabus_portion.toLowerCase().trim() !== suggestionMeta.matched_portion.toLowerCase().trim() && (
                  <div className="p-3 bg-[#CFEDE7]/40 border border-[#72C9BE]/60 rounded-xl flex items-center justify-between gap-3 animate-in fade-in duration-150">
                    <div className="text-xs text-[#13443e] font-medium flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-[#72C9BE] shrink-0" />
                      <span>
                        Did you mean <span className="font-bold underline decoration-[#72C9BE]">{suggestionMeta.matched_portion}</span>?
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        type="button"
                        onClick={() => setExamForm({ ...examForm, syllabus_portion: suggestionMeta.matched_portion })}
                        className="px-3 py-1 text-xs font-semibold bg-[#72C9BE] hover:bg-[#5bb8ac] text-[#13443e] rounded-lg transition-colors cursor-pointer shadow-2xs"
                      >
                        Yes
                      </button>
                      <button
                        type="button"
                        onClick={() => setExamForm({ ...examForm, syllabus_portion: '' })}
                        className="px-2.5 py-1 text-xs font-medium text-slate-600 hover:text-slate-800 bg-white border border-[#E7EAF0] rounded-lg transition-colors cursor-pointer"
                      >
                        Choose another portion
                      </button>
                    </div>
                  </div>
                )}

                {examForm.syllabus_portion && suggestionMeta?.confidence === 'low' && (
                  <div className="p-3 bg-amber-50/70 border border-amber-200/80 rounded-xl flex items-center gap-2 text-xs text-amber-900 animate-in fade-in duration-150">
                    <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                    <span>
                      We couldn't confidently match this portion to the syllabus. Add topics manually or choose a syllabus unit.
                    </span>
                  </div>
                )}

                {/* Quick select portion chips from available syllabus units */}
                {availablePortions.length > 0 && (
                  <div className="pt-1">
                    <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                      Quick Syllabus Units:
                    </span>
                    <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto p-1.5 bg-slate-50/70 border border-[#E7EAF0] rounded-xl">
                      <button
                        type="button"
                        onClick={() => setExamForm({ ...examForm, syllabus_portion: '' })}
                        className={`text-[11px] px-2 py-0.5 rounded-lg border transition-all cursor-pointer font-medium ${
                          !examForm.syllabus_portion
                            ? 'bg-[#CFEDE7] border-[#72C9BE] text-[#1A4B43] shadow-2xs font-semibold'
                            : 'bg-white border-[#E7EAF0] text-slate-600 hover:border-[#72C9BE]'
                        }`}
                      >
                        All Units
                      </button>
                      {availablePortions.map((portionName, pIdx) => {
                        const isMatch = examForm.syllabus_portion?.toLowerCase().trim() === portionName.toLowerCase().trim();
                        return (
                          <button
                            key={pIdx}
                            type="button"
                            onClick={() => setExamForm({ ...examForm, syllabus_portion: portionName })}
                            className={`text-[11px] px-2.5 py-0.5 rounded-lg border transition-all cursor-pointer font-medium ${
                              isMatch
                                ? 'bg-[#CFEDE7] border-[#72C9BE] text-[#1A4B43] shadow-2xs font-semibold'
                                : 'bg-white border-[#E7EAF0] text-slate-600 hover:border-[#72C9BE] hover:bg-slate-50'
                            }`}
                          >
                            {portionName}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Exam Type</label>
                  <select
                    value={examForm.exam_type}
                    onChange={(e) => setExamForm({ ...examForm, exam_type: e.target.value })}
                    className="w-full py-2.5 px-3 bg-slate-50 border border-[#E7EAF0] rounded-xl text-slate-800 text-sm focus:outline-none focus:bg-white focus:border-[#72C9BE]"
                  >
                    <option value="Internal Assessment">Internal Assessment</option>
                    <option value="University Prof Exam">University Prof Exam</option>
                    <option value="Viva Voce">Viva Voce</option>
                    <option value="Clinical Spotters">Clinical Spotters</option>
                    <option value="Weekly Quiz">Weekly Quiz</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Target Score (%)</label>
                  <input
                    type="number"
                    min="50"
                    max="100"
                    value={examForm.target_score}
                    onChange={(e) => setExamForm({ ...examForm, target_score: e.target.value })}
                    className="w-full py-2.5 px-3 bg-slate-50 border border-[#E7EAF0] rounded-xl text-slate-800 text-sm focus:outline-none focus:bg-white focus:border-[#72C9BE]"
                  />
                </div>
              </div>

              {/* Subject-Aware Important Topics Section */}
              <div className="space-y-2.5 pt-1 border-t border-[#E7EAF0]">
                <div className="flex items-center justify-between">
                  <label className="block text-slate-700 font-semibold text-xs">
                    Important Topics ({selectedTopics.length})
                  </label>
                  <span className="text-[11px] text-slate-400">
                    High-yield focus for Study Planner
                  </span>
                </div>

                {/* Selected Topic Chips with Inline Edit */}
                {selectedTopics.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5 p-2 bg-slate-50 border border-[#E7EAF0] rounded-xl max-h-32 overflow-y-auto">
                    {selectedTopics.map((t, idx) => {
                      const isEditing = editingTopicIndex === idx;
                      if (isEditing) {
                        return (
                          <span
                            key={idx}
                            className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg bg-white border border-[#72C9BE] shadow-2xs"
                          >
                            <input
                              type="text"
                              value={editingTopicText}
                              onChange={(ev) => setEditingTopicText(ev.target.value)}
                              onKeyDown={(ev) => {
                                if (ev.key === 'Enter') {
                                  ev.preventDefault();
                                  handleSaveEditTopic(idx);
                                } else if (ev.key === 'Escape') {
                                  handleCancelEditTopic();
                                }
                              }}
                              className="text-xs text-slate-800 focus:outline-none border-b border-[#72C9BE] py-0.5 px-1 min-w-[120px]"
                              autoFocus
                            />
                            <button
                              type="button"
                              onClick={() => handleSaveEditTopic(idx)}
                              className="text-[#1A4B43] hover:text-[#72C9BE] p-0.5 cursor-pointer"
                              title="Save topic edit"
                            >
                              <Check className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={handleCancelEditTopic}
                              className="text-slate-400 hover:text-slate-600 p-0.5 cursor-pointer"
                              title="Cancel edit"
                            >
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </span>
                        );
                      }
                      return (
                        <span
                          key={idx}
                          className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg bg-white border border-[#72C9BE] text-[#1A4B43] shadow-2xs font-medium group"
                        >
                          <span>{t}</span>
                          <button
                            type="button"
                            onClick={() => handleStartEditTopic(idx)}
                            className="text-slate-300 hover:text-slate-600 transition-colors p-0.5 rounded cursor-pointer"
                            title="Edit topic"
                          >
                            <Edit2 className="w-2.5 h-2.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRemoveTopic(idx)}
                            className="text-slate-400 hover:text-rose-600 transition-colors p-0.5 rounded cursor-pointer"
                            title="Remove topic"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </span>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-[11px] text-slate-400 italic bg-slate-50/50 p-2 rounded-xl border border-dashed border-[#E7EAF0]">
                    No topics added yet. Type below or pick from syllabus suggestions.
                  </p>
                )}

                {/* Custom Topic Input */}
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={topicInput}
                    onChange={(e) => {
                      setTopicInput(e.target.value);
                      if (validationWarning) setValidationWarning(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleAddTopic(topicInput);
                      }
                    }}
                    placeholder="Add important topics for this exam"
                    className="flex-1 py-2 px-3.5 bg-slate-50 border border-[#E7EAF0] rounded-xl text-slate-800 placeholder-slate-400 text-xs focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                  />
                  <button
                    type="button"
                    disabled={!topicInput.trim() || validatingTopic}
                    onClick={() => handleAddTopic(topicInput)}
                    className="px-3.5 py-2 bg-[#CFEDE7] hover:bg-[#bce6dc] text-[#1A4B43] rounded-xl font-semibold text-xs inline-flex items-center gap-1 disabled:opacity-40 transition-all cursor-pointer shadow-2xs"
                  >
                    {validatingTopic ? (
                      <span className="w-3 h-3 border-2 border-[#1A4B43] border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
                    )}
                    <span>Add</span>
                  </button>
                </div>

                {/* Gentle Validation Warning Banner */}
                {validationWarning && (
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl space-y-2 animate-in fade-in duration-150">
                    <div className="flex items-start gap-2 text-amber-900 text-xs">
                      <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                      <div className="space-y-0.5">
                        <p className="font-semibold text-amber-950">
                          This topic may not belong to the selected subject. Add anyway?
                        </p>
                        <p className="text-[11px] leading-relaxed text-amber-800">
                          {validationWarning.warning}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center justify-end gap-2 pt-1 border-t border-amber-200/60">
                      <button
                        type="button"
                        onClick={() => setValidationWarning(null)}
                        className="px-2.5 py-1 text-xs font-medium text-slate-600 hover:text-slate-800 rounded-lg transition-colors cursor-pointer"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={() => handleAddTopic(validationWarning.topic, true)}
                        className="px-3 py-1 text-xs font-semibold bg-amber-600 hover:bg-amber-700 text-white rounded-lg transition-colors shadow-2xs cursor-pointer"
                      >
                        Add Anyway
                      </button>
                    </div>
                  </div>
                )}

                {/* Suggested Topics Container */}
                <div className="space-y-1.5 pt-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-500 font-semibold flex items-center gap-1.5 flex-wrap">
                      <Sparkles className="w-3.5 h-3.5 text-[#72C9BE]" />
                      <span>
                        Suggested Topics for {subjects.find(s => s.id === examForm.subject_id)?.name || 'Subject'}
                        {examForm.syllabus_portion ? ` • ${examForm.syllabus_portion}` : ''}:
                      </span>
                      {suggestionMeta?.ai_ranked && (
                        <span className="text-[10px] px-2 py-0.5 rounded-md bg-[#CFEDE7] text-[#13443e] font-semibold tracking-wide">
                          AI-Ranked
                        </span>
                      )}
                    </span>
                    {loadingSuggestions && (
                      <span className="text-[10px] text-slate-400 animate-pulse">Loading topics...</span>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto p-2 bg-slate-50/70 border border-[#E7EAF0] rounded-xl">
                    {suggestedTopics.length > 0 ? (
                      suggestedTopics.map((top, idx) => {
                        const isSelected = selectedTopics.some(t => t.toLowerCase() === top.toLowerCase());
                        return (
                          <button
                            key={idx}
                            type="button"
                            disabled={isSelected}
                            onClick={() => handleAddTopic(top, true)}
                            className={`text-[11px] px-2.5 py-1 rounded-lg border transition-all inline-flex items-center gap-1 cursor-pointer ${
                              isSelected
                                ? 'bg-[#CFEDE7]/40 border-[#72C9BE]/50 text-[#1A4B43] opacity-60 cursor-default'
                                : 'bg-white border-[#E7EAF0] text-slate-700 hover:border-[#72C9BE] hover:bg-[#CFEDE7]/10'
                            }`}
                          >
                            {isSelected ? (
                              <CheckCircle2 className="w-3 h-3 text-[#72C9BE]" />
                            ) : (
                              <Plus className="w-3 h-3 text-slate-400" />
                            )}
                            <span>{top}</span>
                          </button>
                        );
                      })
                    ) : (
                      <p className="text-[11px] text-slate-400 italic py-1">
                        {loadingSuggestions ? 'Loading syllabus topics...' : 'No syllabus suggestions available yet. Add topics manually.'}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-[#E7EAF0]">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-slate-100 font-medium transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2.5 rounded-xl bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 font-semibold transition-colors shadow-xs cursor-pointer"
                >
                  {editingExamId ? 'Save Changes' : 'Save Exam'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
