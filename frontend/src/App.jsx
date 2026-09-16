import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, NavLink, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar';

// Pages
import AuthPage from './pages/AuthPage';
import Dashboard from './pages/Dashboard';
import AssistantPage from './pages/AssistantPage';
import TimetablePage from './pages/TimetablePage';
import AttendancePage from './pages/AttendancePage';
import PlannerPage from './pages/PlannerPage';
import ExamsPage from './pages/ExamsPage';
import ResourcesPage from './pages/ResourcesPage';
import PYQPage from './pages/PYQPage';
import HabitsPage from './pages/HabitsPage';
import FriendsPage from './pages/FriendsPage';
import ProfilePage from './pages/ProfilePage';

import {
  LayoutDashboard,
  Calendar,
  CheckSquare,
  BookOpen,
  Bot,
  MoreHorizontal,
  Stethoscope,
  ShieldCheck,
  Sparkles,
  Clock,
  ArrowRight,
  X,
  GraduationCap,
  FolderDown,
  FileQuestion,
  HeartPulse,
  Users,
  User,
  LogOut
} from 'lucide-react';
import { AttendanceNotificationProvider, useAttendanceNotification } from './context/AttendanceNotificationContext';

function MobileBottomNav({ onOpenMore }) {
  const { unmarkedCount } = useAttendanceNotification();

  const navItems = [
    { name: 'Home', path: '/', icon: LayoutDashboard },
    { name: 'Schedule', path: '/timetable', icon: Calendar },
    { name: 'Attendance', path: '/attendance', icon: CheckSquare, badge: unmarkedCount > 0 },
    { name: 'Study', path: '/planner', icon: BookOpen },
    { name: 'AI', path: '/assistant', icon: Bot },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-md border-t border-[#E7EAF0] px-2 py-2 flex items-center justify-around lg:hidden shadow-[0_-4px_16px_rgba(0,0,0,0.03)]">
      {navItems.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex flex-col items-center gap-1 py-1 px-3 rounded-xl transition-all relative ${
                isActive ? 'text-[#1A4B43] font-semibold' : 'text-[#8E97A6] hover:text-[#26313F]'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <div
                  className={`p-1.5 rounded-xl transition-colors ${
                    isActive ? 'bg-[#CFEDE7] text-[#1A4B43]' : 'text-inherit'
                  }`}
                >
                  <Icon className="w-5 h-5 stroke-[2]" />
                </div>
                <span className="text-[10px] tracking-tight">{item.name}</span>
                {item.badge && (
                  <span className="absolute top-1 right-2.5 w-2 h-2 rounded-full bg-[#F3DFAB] ring-2 ring-white" />
                )}
              </>
            )}
          </NavLink>
        );
      })}

      {/* More trigger */}
      <button
        type="button"
        onClick={onOpenMore}
        className="flex flex-col items-center gap-1 py-1 px-3 text-[#8E97A6] hover:text-[#26313F] transition-all"
      >
        <div className="p-1.5 rounded-xl">
          <MoreHorizontal className="w-5 h-5 stroke-[2]" />
        </div>
        <span className="text-[10px] tracking-tight">More</span>
      </button>
    </nav>
  );
}

function MobileMoreSheet({ isOpen, onClose }) {
  const { user, logout } = useAuth();
  if (!isOpen) return null;

  const moreLinks = [
    { name: 'Exams', path: '/exams', icon: GraduationCap },
    { name: 'Resources & PDFs', path: '/resources', icon: FolderDown },
    { name: 'PYQ Analyzer', path: '/pyq', icon: FileQuestion },
    { name: 'Routine & Wellbeing', path: '/habits', icon: HeartPulse },
    { name: 'Friends & Sharing', path: '/friends', icon: Users },
    { name: 'Profile & Settings', path: '/profile', icon: User },
  ];

  return (
    <div className="fixed inset-0 z-50 bg-[#26313F]/30 backdrop-blur-sm flex flex-col justify-end lg:hidden animate-in fade-in duration-150">
      <div
        className="fixed inset-0"
        onClick={onClose}
      />
      <div className="relative bg-white rounded-t-3xl border-t border-[#E7EAF0] p-5 space-y-4 max-h-[80vh] overflow-y-auto shadow-2xl">
        <div className="flex items-center justify-between pb-2 border-b border-[#E7EAF0]">
          <div>
            <h4 className="text-sm font-bold text-[#26313F]">More Destinations</h4>
            <p className="text-xs text-[#6E7785]">{user?.full_name || 'MBBS Student'}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-full text-[#6E7785] hover:bg-[#F2F5F8]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2">
          {moreLinks.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 p-3 rounded-2xl border text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-[#CFEDE7] border-[#72C9BE]/40 text-[#1A4B43] font-semibold'
                      : 'bg-[#F7F8FC] border-[#E7EAF0] text-[#26313F] hover:bg-[#F2F5F8]'
                  }`
                }
              >
                <Icon className="w-4 h-4 text-[#72C9BE] shrink-0" />
                <span className="truncate">{item.name}</span>
              </NavLink>
            );
          })}
        </div>

        <div className="pt-2 border-t border-[#E7EAF0] flex items-center justify-between text-xs text-[#6E7785]">
          <span>Target Attendance: {user?.target_attendance_percentage || 75}%</span>
          <button
            onClick={() => {
              onClose();
              logout();
            }}
            className="flex items-center gap-1 text-[#69242E] hover:underline font-medium"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign out</span>
          </button>
        </div>
      </div>
    </div>
  );
}

function ActiveStudyPill() {
  const location = useLocation();
  const [session, setSession] = useState(null);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const checkSession = () => {
      try {
        const raw = localStorage.getItem('medpilot_active_study_session');
        if (raw) {
          const parsed = JSON.parse(raw);
          if (parsed && parsed.task) {
            setSession(parsed);
            const accum = parsed.accumulatedSeconds || 0;
            const added = parsed.isRunning && parsed.lastStartedAt ? Math.max(0, Math.floor((Date.now() - parsed.lastStartedAt) / 1000)) : 0;
            setElapsed(accum + added);
            return;
          }
        }
        setSession(null);
      } catch {
        setSession(null);
      }
    };
    checkSession();
    const interval = setInterval(checkSession, 1000);
    return () => clearInterval(interval);
  }, []);

  if (!session || location.pathname === '/planner') return null;

  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  const timeStr = `${mins < 10 ? '0' : ''}${mins}:${secs < 10 ? '0' : ''}${secs}`;
  const subjectName = session.task?.subject?.name || session.task?.title || 'Study';

  return (
    <NavLink
      to="/planner"
      className="fixed bottom-20 lg:bottom-6 right-6 z-40 flex items-center gap-2 px-3.5 py-2 rounded-2xl bg-white/95 backdrop-blur-sm border border-[#72C9BE] text-[#13443e] shadow-float hover:shadow-lg transition-all animate-in slide-in-from-bottom-3 duration-200 cursor-pointer"
      title="Return to Study Planner"
    >
      <span className="text-sm">⏱</span>
      <span className="text-xs font-bold truncate max-w-[150px] sm:max-w-[190px]">
        {subjectName} • {timeStr}
      </span>
      {session.isRunning ? (
        <span className="w-2 h-2 rounded-full bg-[#10B981] animate-pulse" />
      ) : (
        <span className="text-[10px] font-medium text-[#92400E] bg-[#FEF3C7] px-1.5 py-0.2 rounded-md">paused</span>
      )}
    </NavLink>
  );
}

function AppLayout({ sidebarOpen, setSidebarOpen }) {
  const { unmarkedClasses, unmarkedCount, openQueueCheckIn, markAttendance, markingId } = useAttendanceNotification();
  const [mobileMoreOpen, setMobileMoreOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#F7F8FC] text-[#26313F] flex">
      {/* Responsive Desktop Sidebar */}
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main View Area */}
      <div className="flex-1 flex flex-col min-w-0 lg:pl-64 pb-16 lg:pb-0">
        <Navbar onMenuClick={() => setSidebarOpen(true)} />

        {/* Global Persistent Banner: Calm Pending Attendance Alert */}
        {unmarkedCount > 0 && (
          <div className="bg-[#F3DFAB]/40 border-b border-[#F3DFAB] px-4 py-2.5 sm:px-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs shadow-soft">
            <div className="flex items-center gap-2.5">
              <span className="p-1 rounded-lg bg-[#F3DFAB] text-[#6B4E17] shrink-0 font-bold text-[11px] px-2">
                {unmarkedCount}
              </span>
              <div>
                <span className="font-semibold text-[#26313F]">
                  Attendance to complete:
                </span>{' '}
                <span className="text-[#6E7785]">
                  {unmarkedCount === 1
                    ? `${unmarkedClasses[0]?.subject?.name || 'Class'} (${unmarkedClasses[0]?.start_time?.slice(0, 5)} – ${unmarkedClasses[0]?.end_time?.slice(0, 5)}) ended and requires your check-in.`
                    : `${unmarkedCount} finished classes are waiting for your attendance check-in.`}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
              {unmarkedCount === 1 ? (
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    disabled={markingId === unmarkedClasses[0]?.id}
                    onClick={() => markAttendance(unmarkedClasses[0].id, 'present')}
                    className="px-3 py-1 rounded-lg bg-[#CFEDE7] hover:bg-[#bceae0] text-[#1A4B43] font-semibold transition-all cursor-pointer shadow-sm text-xs"
                  >
                    Present
                  </button>
                  <button
                    type="button"
                    disabled={markingId === unmarkedClasses[0]?.id}
                    onClick={() => markAttendance(unmarkedClasses[0].id, 'absent')}
                    className="px-3 py-1 rounded-lg bg-[#EABFC5]/50 hover:bg-[#EABFC5]/80 text-[#69242E] font-semibold transition-all cursor-pointer shadow-sm text-xs"
                  >
                    Absent
                  </button>
                  <button
                    type="button"
                    onClick={openQueueCheckIn}
                    className="px-2.5 py-1 rounded-lg bg-white hover:bg-[#F2F5F8] text-[#26313F] border border-[#E7EAF0] font-medium transition-all cursor-pointer text-xs"
                  >
                    Details
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={openQueueCheckIn}
                  className="px-3.5 py-1.5 rounded-xl bg-white hover:bg-[#F2F5F8] text-[#26313F] border border-[#E7EAF0] font-semibold transition-all flex items-center gap-1.5 cursor-pointer shadow-soft text-xs"
                >
                  <span>Complete check-in</span>
                  <ArrowRight className="w-3.5 h-3.5 text-[#72C9BE]" />
                </button>
              )}
            </div>
          </div>
        )}

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/assistant" element={<AssistantPage />} />
            <Route path="/timetable" element={<TimetablePage />} />
            <Route path="/attendance" element={<AttendancePage />} />
            <Route path="/planner" element={<PlannerPage />} />
            <Route path="/exams" element={<ExamsPage />} />
            <Route path="/resources" element={<ResourcesPage />} />
            <Route path="/pyq" element={<PYQPage />} />
            <Route path="/habits" element={<HabitsPage />} />
            <Route path="/friends" element={<FriendsPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>

        {/* Global Footer with Academic Disclaimer */}
        <footer className="border-t border-[#E7EAF0] bg-white px-4 py-4 text-center text-xs text-[#6E7785]">
          <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-[#6E7785]">
              <ShieldCheck className="w-4 h-4 text-[#72C9BE] shrink-0" />
              <span className="text-[11px] text-left">
                <strong>Academic Support Notice:</strong> MedPilot is designed strictly for MBBS student academic planning, curriculum study, and attendance tracking. It does not provide clinical diagnosis, patient management, or medical treatment advice.
              </span>
            </div>
            <div className="text-[11px] text-[#8E97A6] shrink-0">
              &copy; {new Date().getFullYear()} MedPilot &bull; Version 2.0
            </div>
          </div>
        </footer>
      </div>

      {/* Mobile Bottom Navigation Bar & More Sheet */}
      <MobileBottomNav onOpenMore={() => setMobileMoreOpen(true)} />
      <MobileMoreSheet isOpen={mobileMoreOpen} onClose={() => setMobileMoreOpen(false)} />

      {/* Persistent Study Session Navigation Pill */}
      <ActiveStudyPill />
    </div>
  );
}

function AppContent() {
  const { user, loading } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Splash Loading Screen (Light Pastel)
  if (loading) {
    return (
      <div className="min-h-screen bg-[#F7F8FC] flex flex-col items-center justify-center p-6 text-[#26313F]">
        <div className="relative">
          <div className="w-16 h-16 rounded-3xl bg-[#CFEDE7] flex items-center justify-center text-[#1A4B43] shadow-card animate-pulse">
            <Stethoscope className="w-8 h-8 stroke-[2.2]" />
          </div>
          <div className="absolute -top-1 -right-1">
            <Sparkles className="w-5 h-5 text-[#72C9BE] animate-spin" />
          </div>
        </div>
        <h2 className="mt-4 text-lg font-bold tracking-tight text-[#26313F]">MedPilot</h2>
        <p className="text-xs text-[#6E7785] mt-1">Starting your academic companion...</p>
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/auth" element={!user ? <AuthPage /> : <Navigate to="/" replace />} />
      <Route
        path="/*"
        element={
          user ? (
            <AppLayout sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />
          ) : (
            <Navigate to="/auth" replace />
          )
        }
      />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AttendanceNotificationProvider>
        <AppContent />
      </AttendanceNotificationProvider>
    </AuthProvider>
  );
}
