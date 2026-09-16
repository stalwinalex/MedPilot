import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  User,
  Mail,
  GraduationCap,
  Building,
  Target,
  Clock,
  Save,
  CheckCircle,
  AlertCircle,
  BookOpen,
  Plus,
  Shield,
  Stethoscope,
  CalendarX,
  RotateCcw,
  RefreshCw,
  Trash2,
  AlertTriangle,
  Key,
  X,
  Database,
  Info,
  Check
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { apiRequest } from '../api/client';
import SubjectManagementModal from '../components/SubjectManagementModal';

const MBBS_YEARS = [
  'MBBS 1st Year (Pre-clinical)',
  'MBBS 2nd Year (Para-clinical)',
  'MBBS 3rd Year Part 1 (Clinical)',
  'MBBS 3rd Year Part 2 (Final Year)',
  'Internship / CRMI',
];

export default function ProfilePage() {
  const { user, updateProfile, logout } = useAuth();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    full_name: '',
    college: '',
    year_of_study: 'MBBS 1st Year (Pre-clinical)',
    target_attendance_percentage: 75,
    daily_study_target_minutes: 180,
  });

  const [subjects, setSubjects] = useState([]);
  const [newSubjectName, setNewSubjectName] = useState('');
  const [newSubjectCode, setNewSubjectCode] = useState('');
  const [newSubjectColor, setNewSubjectColor] = useState('#0D9488');
  const [addingSubject, setAddingSubject] = useState(false);
  const [showSubjectModal, setShowSubjectModal] = useState(false);

  const [saving, setSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState({ type: '', text: '' });

  // Account & Data Management modal states
  const [activeModal, setActiveModal] = useState(null); // 'reset_timetable' | 'reset_semester' | 'reset_all' | 'delete_account'
  const [confirmInput, setConfirmInput] = useState('');
  const [passwordInput, setPasswordInput] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [modalError, setModalError] = useState('');

  useEffect(() => {
    if (user) {
      setFormData({
        full_name: user.full_name || '',
        college: user.college || '',
        year_of_study: user.year_of_study || 'MBBS 1st Year (Pre-clinical)',
        target_attendance_percentage: user.target_attendance_percentage || 75,
        daily_study_target_minutes: user.daily_study_target_minutes || 180,
      });
    }
    loadSubjects();
  }, [user]);

  async function loadSubjects() {
    try {
      const data = await apiRequest('/subjects/');
      setSubjects(data || []);
    } catch (err) {
      console.error('Failed to load subjects', err);
    }
  }

  async function handleSaveProfile(e) {
    e.preventDefault();
    setSaving(true);
    setStatusMsg({ type: '', text: '' });
    try {
      await updateProfile({
        full_name: formData.full_name,
        college: formData.college,
        year_of_study: formData.year_of_study,
        target_attendance_percentage: parseFloat(formData.target_attendance_percentage),
        daily_study_target_minutes: parseInt(formData.daily_study_target_minutes, 10),
      });
      setStatusMsg({ type: 'success', text: 'Profile preferences updated successfully!' });
      setTimeout(() => setStatusMsg({ type: '', text: '' }), 3000);
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message || 'Failed to update profile' });
    } finally {
      setSaving(false);
    }
  }

  async function handleAddSubject(e) {
    e.preventDefault();
    if (!newSubjectName.trim()) return;
    setAddingSubject(true);
    try {
      const added = await apiRequest('/subjects/', {
        method: 'POST',
        body: JSON.stringify({
          name: newSubjectName.trim(),
          code: newSubjectCode.trim() || newSubjectName.slice(0, 4).toUpperCase(),
          color: newSubjectColor,
          target_attendance: parseFloat(formData.target_attendance_percentage),
        }),
      });
      setSubjects((prev) => [...prev, added]);
      setNewSubjectName('');
      setNewSubjectCode('');
    } catch (err) {
      alert('Failed to add subject: ' + err.message);
    } finally {
      setAddingSubject(false);
    }
  }

  const handleOpenModal = (modalType) => {
    setActiveModal(modalType);
    setConfirmInput('');
    setPasswordInput('');
    setModalError('');
  };

  const handleCloseModal = () => {
    if (actionLoading) return;
    setActiveModal(null);
    setConfirmInput('');
    setPasswordInput('');
    setModalError('');
  };

  const handleExecuteAction = async () => {
    setModalError('');
    setActionLoading(true);

    try {
      if (activeModal === 'reset_timetable') {
        const res = await apiRequest('/account/reset-timetable', { method: 'POST' });
        setStatusMsg({ type: 'success', text: res.message || 'Timetable reset successfully!' });
        handleCloseModal();
        loadSubjects();
      } else if (activeModal === 'reset_semester') {
        const res = await apiRequest('/account/reset-semester', { method: 'POST' });
        setStatusMsg({ type: 'success', text: res.message || 'Current semester data reset successfully!' });
        handleCloseModal();
        loadSubjects();
      } else if (activeModal === 'reset_all') {
        if (confirmInput.trim().toUpperCase() !== 'RESET') {
          setModalError("Please type 'RESET' to confirm full reset.");
          setActionLoading(false);
          return;
        }
        const res = await apiRequest('/account/reset-all', {
          method: 'POST',
          body: JSON.stringify({ confirm_text: confirmInput.trim().toUpperCase() })
        });
        setStatusMsg({ type: 'success', text: res.message || 'All data reset to clean onboarding state!' });
        handleCloseModal();
        loadSubjects();
      } else if (activeModal === 'delete_account') {
        if (confirmInput.trim().toUpperCase() !== 'DELETE') {
          setModalError("Please type 'DELETE' to confirm account deletion.");
          setActionLoading(false);
          return;
        }
        await apiRequest('/account/delete', {
          method: 'POST',
          body: JSON.stringify({
            confirm_text: confirmInput.trim().toUpperCase(),
            password: passwordInput
          })
        });
        handleCloseModal();
        logout();
        navigate('/auth');
      }
    } catch (err) {
      setModalError(err.message || 'Action failed. Please try again.');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-8 pb-24 max-w-4xl mx-auto px-4 sm:px-6 py-8">
      {/* Header */}
      <div className="border-b border-[#E7EAF0] pb-6">
        <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2.5">
          <span className="p-2 rounded-xl bg-[#CFEDE7] text-[#1A4B43]">
            <User className="w-5 h-5" />
          </span>
          <span>Student Profile & Academic Settings</span>
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Customize your academic targets, attendance thresholds, MBBS curriculum stage, and subjects.
        </p>
      </div>

      {statusMsg.text && (
        <div
          className={`p-4 rounded-2xl text-sm flex items-center gap-2.5 border animate-in fade-in ${
            statusMsg.type === 'success'
              ? 'bg-[#CFEDE7] text-[#1A4B43] border-[#72C9BE]'
              : 'bg-rose-50 text-rose-700 border-rose-200'
          }`}
        >
          {statusMsg.type === 'success' ? (
            <CheckCircle className="w-5 h-5 shrink-0" />
          ) : (
            <AlertCircle className="w-5 h-5 shrink-0" />
          )}
          <span>{statusMsg.text}</span>
        </div>
      )}

      {/* Main Profile Form */}
      <form onSubmit={handleSaveProfile} className="space-y-6">
        <div className="bg-white border border-[#E7EAF0] rounded-2xl p-6 shadow-card space-y-6">
          <div className="flex items-center gap-3.5 pb-4 border-b border-[#E7EAF0]">
            <div className="w-12 h-12 rounded-2xl bg-[#CFEDE7] text-[#1A4B43] font-bold flex items-center justify-center text-lg shadow-xs">
              {formData.full_name?.charAt(0) || 'M'}
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-800">{formData.full_name || 'Medical Student'}</h2>
              <p className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
                <Mail className="w-3.5 h-3.5" />
                {user?.email}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Full Name */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center gap-1.5">
                <User className="w-3.5 h-3.5 text-[#72C9BE]" />
                Full Name
              </label>
              <input
                type="text"
                required
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3.5 py-2.5 text-sm text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
              />
            </div>

            {/* Medical College */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center gap-1.5">
                <Building className="w-3.5 h-3.5 text-[#72C9BE]" />
                Medical College / Institution
              </label>
              <input
                type="text"
                required
                value={formData.college}
                onChange={(e) => setFormData({ ...formData, college: e.target.value })}
                className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3.5 py-2.5 text-sm text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
              />
            </div>

            {/* MBBS Year */}
            <div className="md:col-span-2">
              <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center gap-1.5">
                <GraduationCap className="w-3.5 h-3.5 text-[#72C9BE]" />
                Current Year of Study / Professional Phase
              </label>
              <select
                value={formData.year_of_study}
                onChange={(e) => setFormData({ ...formData, year_of_study: e.target.value })}
                className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3.5 py-2.5 text-sm text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
              >
                {MBBS_YEARS.map((yr) => (
                  <option key={yr} value={yr}>
                    {yr}
                  </option>
                ))}
              </select>
            </div>

            {/* Attendance Target */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
                  <Target className="w-3.5 h-3.5 text-[#72C9BE]" />
                  Target Attendance Threshold
                </label>
                <span className="text-xs font-bold text-[#1A4B43] font-mono">
                  {formData.target_attendance_percentage}%
                </span>
              </div>
              <input
                type="range"
                min="50"
                max="95"
                step="1"
                value={formData.target_attendance_percentage}
                onChange={(e) =>
                  setFormData({ ...formData, target_attendance_percentage: Number(e.target.value) })
                }
                className="w-full accent-[#72C9BE] cursor-pointer"
              />
              <div className="flex justify-between text-[11px] text-slate-400 mt-1">
                <span>50%</span>
                <span className="text-[#1A4B43] font-semibold">75% (NMC Standard)</span>
                <span>95%</span>
              </div>
            </div>

            {/* Daily Study Target */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-[#72C9BE]" />
                  Daily Study Goal
                </label>
                <span className="text-xs font-bold text-[#1A4B43] font-mono">
                  {Math.floor(formData.daily_study_target_minutes / 60)}h{' '}
                  {formData.daily_study_target_minutes % 60}m
                </span>
              </div>
              <input
                type="range"
                min="60"
                max="480"
                step="30"
                value={formData.daily_study_target_minutes}
                onChange={(e) =>
                  setFormData({ ...formData, daily_study_target_minutes: Number(e.target.value) })
                }
                className="w-full accent-[#72C9BE] cursor-pointer"
              />
              <div className="flex justify-between text-[11px] text-slate-400 mt-1">
                <span>1 hour</span>
                <span>3 hours</span>
                <span>8 hours</span>
              </div>
            </div>
          </div>

          <div className="pt-2 flex justify-end border-t border-[#E7EAF0]">
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-semibold bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 shadow-sm transition-all disabled:opacity-50 cursor-pointer active:scale-95"
            >
              <Save className="w-4 h-4" />
              <span>{saving ? 'Saving...' : 'Save Profile Changes'}</span>
            </button>
          </div>
        </div>
      </form>

      {/* Enrolled Subjects Management */}
      <div className="bg-white border border-[#E7EAF0] rounded-2xl p-6 shadow-card space-y-5">
        <div className="flex items-center justify-between pb-3 border-b border-[#E7EAF0]">
          <div>
            <h2 className="text-base font-bold text-slate-800 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-[#72C9BE]" />
              Enrolled MBBS Subjects
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Subjects tracked in your timetable, attendance calculator, and study planner.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowSubjectModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors cursor-pointer"
            >
              <BookOpen className="w-3.5 h-3.5 text-[#72C9BE]" />
              <span>Manage Subjects</span>
            </button>
            <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-slate-50 text-slate-600 border border-slate-200">
              {subjects.length} Subjects
            </span>
          </div>
        </div>

        {/* Subjects Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {subjects.map((sub) => (
            <div
              key={sub.id}
              className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center gap-3"
            >
              <div
                className="w-3.5 h-10 rounded-md shrink-0"
                style={{ backgroundColor: sub.color || '#72C9BE' }}
              />
              <div className="overflow-hidden">
                <p className="text-xs font-semibold text-slate-800 truncate">{sub.name}</p>
                <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
                  <span className="font-mono text-[#1A4B43] font-medium">{sub.code}</span>
                  <span>&bull;</span>
                  <span>Target: {sub.target_attendance}%</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Add Subject Form */}
        <form onSubmit={handleAddSubject} className="pt-4 border-t border-[#E7EAF0]">
          <p className="text-xs font-semibold text-slate-700 mb-3">Add Additional Subject / Posting</p>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
            <input
              type="text"
              required
              placeholder="Subject Name (e.g. ENT, Ophtha)"
              value={newSubjectName}
              onChange={(e) => setNewSubjectName(e.target.value)}
              className="sm:col-span-2 bg-slate-50 border border-[#E7EAF0] rounded-xl px-3.5 py-2 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-[#72C9BE]"
            />
            <input
              type="text"
              placeholder="Code (e.g. ENT)"
              value={newSubjectCode}
              onChange={(e) => setNewSubjectCode(e.target.value)}
              className="bg-slate-50 border border-[#E7EAF0] rounded-xl px-3.5 py-2 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-[#72C9BE]"
            />
            <button
              type="submit"
              disabled={addingSubject || !newSubjectName.trim()}
              className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 transition-colors disabled:opacity-50 cursor-pointer shadow-xs"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>{addingSubject ? 'Adding...' : 'Add Subject'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Account & Data Management */}
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
            <Database className="w-5 h-5 text-slate-600" />
            <span>Account & Data Management</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Manage your academic records, reset semesters, re-initialize your workspace, or permanently delete your account.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Card 1: Reset Timetable Only */}
          <div className="bg-white border border-[#E7EAF0] rounded-2xl p-5 shadow-xs flex flex-col justify-between hover:border-amber-300 transition-colors">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center border border-amber-100">
                <CalendarX className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-800">Reset Timetable Only</h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Clear weekly timetable rules and upcoming scheduled class occurrences. Keeps past attendance records, subjects, and study tasks.
                </p>
              </div>
            </div>
            <div className="pt-4 border-t border-slate-100 mt-4">
              <button
                type="button"
                onClick={() => handleOpenModal('reset_timetable')}
                className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 transition-colors cursor-pointer"
              >
                <CalendarX className="w-3.5 h-3.5" />
                <span>Reset Timetable</span>
              </button>
            </div>
          </div>

          {/* Card 2: Reset Current Semester */}
          <div className="bg-white border border-[#E7EAF0] rounded-2xl p-5 shadow-xs flex flex-col justify-between hover:border-amber-300 transition-colors">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center border border-amber-100">
                <RotateCcw className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-800">Reset Current Semester</h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Wipe current semester timetable, attendance logs, class topics, study tasks, and exams. Preserves past archived semesters.
                </p>
              </div>
            </div>
            <div className="pt-4 border-t border-slate-100 mt-4">
              <button
                type="button"
                onClick={() => handleOpenModal('reset_semester')}
                className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 transition-colors cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Reset Semester</span>
              </button>
            </div>
          </div>

          {/* Card 3: Reset All MedPilot Data */}
          <div className="bg-white border border-[#E7EAF0] rounded-2xl p-5 shadow-xs flex flex-col justify-between hover:border-orange-300 transition-colors">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-orange-50 text-orange-600 flex items-center justify-center border border-orange-100">
                <RefreshCw className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-800">Reset All Academic Data</h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Clear your entire workspace (timetable, attendance, study plans, exams, habits, AI data) and return to clean onboarding. Login is kept.
                </p>
              </div>
            </div>
            <div className="pt-4 border-t border-slate-100 mt-4">
              <button
                type="button"
                onClick={() => handleOpenModal('reset_all')}
                className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold bg-orange-50 hover:bg-orange-100 text-orange-800 border border-orange-200 transition-colors cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Reset Workspace</span>
              </button>
            </div>
          </div>
        </div>

        {/* Danger Zone: Delete Account */}
        <div className="bg-rose-50/60 border border-rose-200 rounded-2xl p-5 shadow-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-rose-800 font-bold text-sm">
                <AlertTriangle className="w-4 h-4 text-rose-600" />
                <span>Danger Zone &mdash; Delete Account</span>
              </div>
              <p className="text-xs text-rose-700/80 leading-relaxed max-w-xl">
                Permanently delete your MedPilot account, profile, credentials, and all associated academic records. This action cannot be undone.
              </p>
            </div>
            <div>
              <button
                type="button"
                onClick={() => handleOpenModal('delete_account')}
                className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 hover:bg-rose-700 text-white transition-colors cursor-pointer shadow-xs whitespace-nowrap"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Delete Account</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Academic Integrity & Disclaimer Notice */}
      <div className="bg-slate-50 border border-slate-200 rounded-2xl p-5 space-y-2 text-xs text-slate-500">
        <div className="flex items-center gap-2 text-[#1A4B43] font-semibold">
          <Shield className="w-4 h-4 text-[#72C9BE]" />
          <span>Educational Disclaimer & Academic Terms</span>
        </div>
        <p className="leading-relaxed text-slate-600">
          MedPilot is an AI academic companion designed exclusively to support medical students in curriculum planning, deterministic attendance tracking, study task management, and academic comprehension. MedPilot does not provide clinical diagnosis, patient management directives, or drug prescription advice. All study content generated should be cross-referenced with standard medical textbooks and institutional guidelines.
        </p>
      </div>

      {/* Subject Management Modal */}
      <SubjectManagementModal
        isOpen={showSubjectModal}
        onClose={() => setShowSubjectModal(false)}
        onSubjectsChanged={loadSubjects}
      />

      {/* Account & Data Management Action Confirmation Modal */}
      {activeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in">
          <div className="bg-white border border-[#E7EAF0] rounded-3xl max-w-lg w-full p-6 shadow-xl space-y-5 animate-in zoom-in-95">
            {/* Modal Header */}
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div
                  className={`w-10 h-10 rounded-2xl flex items-center justify-center border ${
                    activeModal === 'delete_account'
                      ? 'bg-rose-100 text-rose-600 border-rose-200'
                      : activeModal === 'reset_all'
                      ? 'bg-orange-100 text-orange-600 border-orange-200'
                      : 'bg-amber-100 text-amber-700 border-amber-200'
                  }`}
                >
                  {activeModal === 'delete_account' ? (
                    <AlertTriangle className="w-5 h-5" />
                  ) : activeModal === 'reset_all' ? (
                    <RefreshCw className="w-5 h-5" />
                  ) : activeModal === 'reset_semester' ? (
                    <RotateCcw className="w-5 h-5" />
                  ) : (
                    <CalendarX className="w-5 h-5" />
                  )}
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-800">
                    {activeModal === 'reset_timetable' && 'Reset Timetable Only'}
                    {activeModal === 'reset_semester' && 'Reset Current Semester'}
                    {activeModal === 'reset_all' && 'Reset All Academic Data'}
                    {activeModal === 'delete_account' && 'Permanently Delete Account'}
                  </h3>
                  <p className="text-xs text-slate-500">
                    {activeModal === 'delete_account'
                      ? 'Irreversible action. Please confirm carefully.'
                      : 'Please review the details below before proceeding.'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={handleCloseModal}
                disabled={actionLoading}
                className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Explanatory breakdown: Deleted vs Kept */}
            <div className="space-y-3 text-xs">
              <div className="bg-rose-50/70 border border-rose-200/70 rounded-xl p-3.5 space-y-1.5">
                <div className="font-semibold text-rose-800 flex items-center gap-1.5">
                  <X className="w-3.5 h-3.5 text-rose-600" />
                  <span>What will be removed:</span>
                </div>
                <ul className="list-disc list-inside text-rose-700/90 space-y-1 pl-1">
                  {activeModal === 'reset_timetable' && (
                    <>
                      <li>All weekly timetable rules</li>
                      <li>Upcoming scheduled and pending class occurrences</li>
                    </>
                  )}
                  {activeModal === 'reset_semester' && (
                    <>
                      <li>Current semester timetable rules & class occurrences</li>
                      <li>Active semester attendance records and class topics</li>
                      <li>Current semester study tasks & upcoming exams</li>
                    </>
                  )}
                  {activeModal === 'reset_all' && (
                    <>
                      <li>All timetable rules, occurrences & pending check-ins</li>
                      <li>All attendance logs, topic coverage & notes</li>
                      <li>All study plans, tasks & study sessions</li>
                      <li>All exams, habits, routines & wellbeing records</li>
                    </>
                  )}
                  {activeModal === 'delete_account' && (
                    <>
                      <li>Your entire student profile and login account</li>
                      <li>All timetable, attendance, and topic history</li>
                      <li>All study plans, tasks, exams, and routines</li>
                      <li>All friends, shared resources & activity history</li>
                    </>
                  )}
                </ul>
              </div>

              <div className="bg-emerald-50/70 border border-emerald-200/70 rounded-xl p-3.5 space-y-1.5">
                <div className="font-semibold text-emerald-800 flex items-center gap-1.5">
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                  <span>What will be preserved:</span>
                </div>
                <ul className="list-disc list-inside text-emerald-700/90 space-y-1 pl-1">
                  {activeModal === 'reset_timetable' && (
                    <>
                      <li>Past attendance records and overall attendance percentage</li>
                      <li>Enrolled subjects and custom subject list</li>
                      <li>Study plans, study tasks, and exams</li>
                      <li>Your account login and profile preferences</li>
                    </>
                  )}
                  {activeModal === 'reset_semester' && (
                    <>
                      <li>User account and profile credentials</li>
                      <li>Enrolled subjects list</li>
                      <li>Previously archived semesters (if any)</li>
                      <li>Habit settings and wellbeing configuration</li>
                    </>
                  )}
                  {activeModal === 'reset_all' && (
                    <>
                      <li>Your login credentials (email and password preserved)</li>
                      <li>Fresh starter subjects & habits for clean onboarding</li>
                    </>
                  )}
                  {activeModal === 'delete_account' && (
                    <>
                      <li>Nothing &mdash; all account data is permanently deleted</li>
                    </>
                  )}
                </ul>
              </div>
            </div>

            {/* Required user inputs for Reset All / Delete */}
            {activeModal === 'reset_all' && (
              <div className="space-y-2 pt-1">
                <label className="block text-xs font-semibold text-slate-700">
                  Type <span className="font-mono text-orange-700 font-bold">RESET</span> to confirm workspace wipe:
                </label>
                <input
                  type="text"
                  placeholder="RESET"
                  value={confirmInput}
                  onChange={(e) => setConfirmInput(e.target.value)}
                  className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3.5 py-2.5 text-xs text-slate-800 font-mono tracking-wider placeholder-slate-400 focus:outline-none focus:bg-white focus:border-orange-400"
                />
              </div>
            )}

            {activeModal === 'delete_account' && (
              <div className="space-y-3 pt-1">
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-slate-700">
                    Type <span className="font-mono text-rose-700 font-bold">DELETE</span> to confirm permanent deletion:
                  </label>
                  <input
                    type="text"
                    placeholder="DELETE"
                    value={confirmInput}
                    onChange={(e) => setConfirmInput(e.target.value)}
                    className="w-full bg-slate-50 border border-rose-200 rounded-xl px-3.5 py-2.5 text-xs text-slate-800 font-mono tracking-wider placeholder-slate-400 focus:outline-none focus:bg-white focus:border-rose-500"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-slate-700 flex items-center gap-1.5">
                    <Key className="w-3.5 h-3.5 text-slate-500" />
                    <span>Enter your account password:</span>
                  </label>
                  <input
                    type="password"
                    placeholder="Account password"
                    value={passwordInput}
                    onChange={(e) => setPasswordInput(e.target.value)}
                    className="w-full bg-slate-50 border border-[#E7EAF0] rounded-xl px-3.5 py-2.5 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-rose-500"
                  />
                </div>
              </div>
            )}

            {/* Error Message */}
            {modalError && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
                <span>{modalError}</span>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={handleCloseModal}
                disabled={actionLoading}
                className="px-4 py-2 rounded-xl text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleExecuteAction}
                disabled={
                  actionLoading ||
                  (activeModal === 'reset_all' && confirmInput.trim().toUpperCase() !== 'RESET') ||
                  (activeModal === 'delete_account' &&
                    (confirmInput.trim().toUpperCase() !== 'DELETE' || !passwordInput))
                }
                className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold text-white transition-colors cursor-pointer shadow-xs disabled:opacity-40 disabled:cursor-not-allowed ${
                  activeModal === 'delete_account'
                    ? 'bg-rose-600 hover:bg-rose-700'
                    : activeModal === 'reset_all'
                    ? 'bg-orange-600 hover:bg-orange-700'
                    : 'bg-amber-600 hover:bg-amber-700'
                }`}
              >
                {actionLoading ? (
                  <span>Processing...</span>
                ) : (
                  <>
                    {activeModal === 'delete_account' && <Trash2 className="w-3.5 h-3.5" />}
                    {activeModal === 'reset_all' && <RefreshCw className="w-3.5 h-3.5" />}
                    {activeModal === 'reset_semester' && <RotateCcw className="w-3.5 h-3.5" />}
                    {activeModal === 'reset_timetable' && <CalendarX className="w-3.5 h-3.5" />}
                    <span>
                      {activeModal === 'reset_timetable' && 'Reset Timetable'}
                      {activeModal === 'reset_semester' && 'Reset Current Semester'}
                      {activeModal === 'reset_all' && 'Reset All Data'}
                      {activeModal === 'delete_account' && 'Permanently Delete Account'}
                    </span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

