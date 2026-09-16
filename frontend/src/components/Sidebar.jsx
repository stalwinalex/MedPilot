import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Calendar,
  CheckSquare,
  BookOpen,
  Bot,
  GraduationCap,
  FolderDown,
  FileQuestion,
  HeartPulse,
  Users,
  User,
  Stethoscope,
  Sparkles,
  LogOut,
  AlertTriangle,
  X
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useAttendanceNotification } from '../context/AttendanceNotificationContext';

const navItems = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'AI Assistant', path: '/assistant', icon: Bot, badge: 'Smart' },
  { name: 'Timetable', path: '/timetable', icon: Calendar },
  { name: 'Attendance', path: '/attendance', icon: CheckSquare },
  { name: 'Study Planner', path: '/planner', icon: BookOpen },
  { name: 'Exams', path: '/exams', icon: GraduationCap },
  { name: 'Resources & PDFs', path: '/resources', icon: FolderDown },
  { name: 'PYQ Analyzer', path: '/pyq', icon: FileQuestion },
  { name: 'Routine & Wellbeing', path: '/habits', icon: HeartPulse },
  { name: 'Friends & Sharing', path: '/friends', icon: Users },
  { name: 'Profile & Settings', path: '/profile', icon: User },
];

export default function Sidebar({ isOpen, onClose }) {
  const { user, logout } = useAuth();
  const { unmarkedCount } = useAttendanceNotification();

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-[#26313F]/25 backdrop-blur-sm lg:hidden transition-opacity"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 bg-white border-r border-[#E7EAF0] flex flex-col transition-transform duration-300 ease-in-out lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand Header */}
        <div className="p-5 border-b border-[#E7EAF0] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-[#CFEDE7] text-[#1A4B43] rounded-2xl flex items-center justify-center shadow-sm">
              <Stethoscope className="w-5 h-5 stroke-[2.2]" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <h1 className="text-lg font-bold tracking-tight text-[#26313F]">
                  MedPilot
                </h1>
                <span className="text-[10px] uppercase font-semibold px-1.5 py-0.2 rounded-md bg-[#CFEDE7] text-[#1A4B43]">
                  MBBS
                </span>
              </div>
              <p className="text-[11px] text-[#6E7785] font-medium">Academic Companion</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1 rounded-lg text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] lg:hidden"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 overflow-y-auto px-3.5 py-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isAttendance = item.path === '/attendance';
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all group ${
                    isActive
                      ? 'bg-[#CFEDE7] text-[#1A4B43] font-semibold shadow-sm'
                      : 'text-[#6E7785] hover:bg-[#F2F5F8] hover:text-[#26313F]'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <div className="flex items-center gap-3 min-w-0">
                      <Icon
                        className={`w-4 h-4 shrink-0 transition-colors ${
                          isActive ? 'text-[#1A4B43]' : 'text-[#8E97A6] group-hover:text-[#26313F]'
                        }`}
                      />
                      <span className="truncate">{item.name}</span>
                    </div>

                    {isAttendance && unmarkedCount > 0 ? (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#F3DFAB] text-[#6B4E17] flex items-center gap-1">
                        <span>{unmarkedCount}</span>
                      </span>
                    ) : item.badge ? (
                      <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-md bg-[#B7D4F4]/40 text-[#1E3A8A]">
                        {item.badge}
                      </span>
                    ) : null}
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* User Card / Bottom Info */}
        <div className="p-4 border-t border-[#E7EAF0] bg-[#F7F8FC]">
          <div className="flex items-center justify-between mb-2">
            <div className="overflow-hidden">
              <p className="text-xs font-semibold text-[#26313F] truncate">{user?.full_name || 'Medical Student'}</p>
              <p className="text-[11px] text-[#6E7785] truncate">{user?.year_of_study || 'MBBS Student'}</p>
            </div>
            <button
              onClick={logout}
              title="Log out"
              className="p-1.5 rounded-lg text-[#6E7785] hover:text-[#69242E] hover:bg-[#EABFC5]/20 transition-colors cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
          <div className="flex items-center justify-between text-[11px] text-[#6E7785] bg-white px-2.5 py-1.5 rounded-xl border border-[#E7EAF0]">
            <span>Target Attendance</span>
            <span className="font-semibold text-[#1A4B43]">{user?.target_attendance_percentage || 75}%</span>
          </div>
        </div>
      </aside>
    </>
  );
}
