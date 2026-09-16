import React, { useState, useRef, useEffect } from 'react';
import { Menu, Sparkles, ShieldCheck, Bell, Clock, CheckCircle2, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAttendanceNotification } from '../context/AttendanceNotificationContext';

export default function Navbar({ onMenuClick }) {
  const navigate = useNavigate();
  const {
    unmarkedClasses,
    unmarkedCount,
    markAttendance,
    markingId,
    openCheckIn,
    notificationPermission,
    requestNotificationPermission
  } = useAttendanceNotification();

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="sticky top-0 z-30 bg-white/90 backdrop-blur-md border-b border-[#E7EAF0] px-4 lg:px-8 py-3.5 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="p-2 rounded-xl text-[#6E7785] hover:text-[#26313F] hover:bg-[#F2F5F8] lg:hidden transition-colors"
          aria-label="Open navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div>
          <span className="hidden sm:inline-block text-xs font-medium text-[#6E7785]">
            MedPilot &bull; <span className="text-[#3D8C82] font-semibold">Academic Companion</span>
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        {/* Enable Desktop Notifications prompt if not granted yet */}
        {notificationPermission === 'default' && (
          <button
            onClick={requestNotificationPermission}
            title="Enable desktop notifications for class-ended reminders"
            className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-[#CFEDE7]/60 text-[#1A4B43] hover:bg-[#CFEDE7] transition-all cursor-pointer"
          >
            <Bell className="w-3.5 h-3.5 text-[#3D8C82]" />
            <span>Enable Reminders</span>
          </button>
        )}

        {/* Academic Disclaimer Badge */}
        <div className="hidden md:flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#F2F5F8] border border-[#E7EAF0] text-[11px] text-[#6E7785]">
          <ShieldCheck className="w-3.5 h-3.5 text-[#72C9BE]" />
          <span>Academic Support Only</span>
        </div>

        {/* Attendance Notification Bell */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setDropdownOpen((prev) => !prev)}
            title={unmarkedCount > 0 ? `${unmarkedCount} classes need attendance confirmation` : 'No pending class reminders'}
            className={`p-2 rounded-xl transition-all relative cursor-pointer ${
              unmarkedCount > 0
                ? 'bg-[#F3DFAB]/50 text-[#6B4E17] hover:bg-[#F3DFAB]/80'
                : 'bg-[#F2F5F8] text-[#6E7785] hover:text-[#26313F] hover:bg-[#E7EAF0]'
            }`}
          >
            <Bell className="w-4 h-4" />
            {unmarkedCount > 0 && (
              <span className="absolute -top-1 -right-1 min-w-4 h-4 px-1 rounded-full bg-[#F3DFAB] text-[#6B4E17] font-bold text-[10px] flex items-center justify-center border border-white shadow-sm">
                {unmarkedCount}
              </span>
            )}
          </button>

          {/* Unmarked Attendance Notification Dropdown */}
          {dropdownOpen && (
            <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl bg-white border border-[#E7EAF0] shadow-xl shadow-[#26313F]/5 p-4 space-y-3 z-50 animate-in fade-in zoom-in-95 duration-100">
              <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-2.5">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-[#26313F] text-xs">
                    Pending Attendance
                  </span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#F3DFAB]/50 text-[#6B4E17]">
                    {unmarkedCount} waiting
                  </span>
                </div>

                <button
                  onClick={() => {
                    setDropdownOpen(false);
                    navigate('/attendance');
                  }}
                  className="text-xs text-[#3D8C82] hover:underline font-semibold flex items-center gap-1"
                >
                  <span>View All</span>
                  <ArrowRight className="w-3 h-3" />
                </button>
              </div>

              {unmarkedClasses.length === 0 ? (
                <div className="text-center py-6 text-xs text-[#6E7785] space-y-1">
                  <CheckCircle2 className="w-6 h-6 text-[#72C9BE] mx-auto mb-1" />
                  <p className="font-semibold text-[#26313F]">All caught up!</p>
                  <p className="text-[11px] text-[#6E7785]">
                    No ended classes currently awaiting attendance.
                  </p>
                </div>
              ) : (
                <div className="max-h-72 overflow-y-auto space-y-2 pr-1">
                  {unmarkedClasses.map((occ) => (
                    <div
                      key={occ.id}
                      className="p-3 rounded-xl bg-[#F7F8FC] border border-[#E7EAF0] space-y-2"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h5 className="text-xs font-semibold text-[#26313F]">
                            {occ.subject?.name || 'Class'}
                          </h5>
                          <div className="flex items-center gap-1.5 text-[11px] text-[#6E7785] mt-0.5">
                            <Clock className="w-3 h-3 text-[#72C9BE]" />
                            <span>
                              {occ.start_time?.slice(0, 5)} – {occ.end_time?.slice(0, 5)}
                              {occ.room ? ` • ${occ.room}` : ''}
                            </span>
                          </div>
                        </div>

                        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#F3DFAB]/50 text-[#6B4E17] shrink-0">
                          Waiting
                        </span>
                      </div>

                      <div className="grid grid-cols-3 gap-1.5 pt-1 text-[11px] font-medium">
                        <button
                          type="button"
                          disabled={markingId === occ.id}
                          onClick={() => markAttendance(occ.id, 'present')}
                          className="py-1 px-2 rounded-lg bg-[#CFEDE7] hover:bg-[#b5e7dc] text-[#1A4B43] font-semibold transition-all text-center cursor-pointer"
                        >
                          Present
                        </button>
                        <button
                          type="button"
                          disabled={markingId === occ.id}
                          onClick={() => markAttendance(occ.id, 'absent')}
                          className="py-1 px-2 rounded-lg bg-[#EABFC5]/40 hover:bg-[#EABFC5]/70 text-[#69242E] font-semibold transition-all text-center cursor-pointer"
                        >
                          Absent
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setDropdownOpen(false);
                            openCheckIn(occ);
                          }}
                          className="py-1 px-2 rounded-lg bg-white hover:bg-[#F2F5F8] text-[#26313F] border border-[#E7EAF0] transition-all text-center cursor-pointer"
                        >
                          + Topic
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Quick Launch "Ask Assistant" */}
        <button
          onClick={() => navigate('/assistant')}
          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-[#72C9BE] text-[#13443e] hover:bg-[#5db8ad] transition-all cursor-pointer shadow-sm active:scale-98"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Ask Assistant</span>
          <span className="sm:hidden">Ask</span>
        </button>
      </div>
    </header>
  );
}
