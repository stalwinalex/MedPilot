import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiRequest } from '../api/client';
import { useAuth } from './AuthContext';
import ClassCheckInModal from '../components/ClassCheckInModal';
import {
  Bell,
  Clock,
  CheckCircle2,
  XCircle,
  X,
  Sparkles
} from 'lucide-react';

const AttendanceNotificationContext = createContext(null);

export function AttendanceNotificationProvider({ children }) {
  const { user } = useAuth();
  const [unmarkedClasses, setUnmarkedClasses] = useState([]);
  const [justEndedClass, setJustEndedClass] = useState(null);
  const [notificationPermission, setNotificationPermission] = useState(
    typeof window !== 'undefined' && 'Notification' in window
      ? Notification.permission
      : 'unsupported'
  );
  const [markingId, setMarkingId] = useState(null);

  // Global Check-In Modal state
  const [modalOcc, setModalOcc] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isQueueMode, setIsQueueMode] = useState(false);

  // Request browser notification permission
  const requestNotificationPermission = async () => {
    if (!('Notification' in window)) return 'unsupported';
    try {
      const perm = await Notification.requestPermission();
      setNotificationPermission(perm);
      return perm;
    } catch (err) {
      console.warn('Could not request notification permission:', err);
      return 'denied';
    }
  };

  // Poll for ended classes & pending check-ins
  const checkClasses = useCallback(async () => {
    if (!user) return;
    try {
      const pending = await apiRequest('/attendance/pending-checkins');
      const pendingList = pending || [];
      setUnmarkedClasses(pendingList);

      const todayStr = new Date().toISOString().split('T')[0];

      // Check if any class ended today that hasn't triggered an instant notification yet
      for (const occ of pendingList) {
        if (occ.date === todayStr) {
          const storageKey = `medpilot_notified_end_${user.id}_${occ.id}`;
          const alreadyNotified = localStorage.getItem(storageKey);

          if (!alreadyNotified) {
            // Mark as notified in localStorage
            localStorage.setItem(storageKey, 'true');

            // 1. Trigger Native Web Notification
            if ('Notification' in window && Notification.permission === 'granted') {
              try {
                const title = `Class Ended: ${occ.subject?.name || 'Class'} 🔔`;
                const body = `Your ${occ.subject?.name} lecture (${occ.start_time?.slice(0, 5)} – ${occ.end_time?.slice(0, 5)}) has finished. Tap to mark your attendance!`;
                const notif = new Notification(title, {
                  body,
                  icon: '/favicon.ico',
                  tag: `class-ended-${occ.id}`,
                  requireInteraction: true
                });
                notif.onclick = () => {
                  window.focus();
                  setModalOcc(occ);
                  setIsQueueMode(false);
                  setIsModalOpen(true);
                  notif.close();
                };
              } catch (e) {
                console.warn('Browser notification error:', e);
              }
            }

            // 2. Trigger In-App Instant Reminder Toast
            setJustEndedClass(occ);
            break; // Show one at a time
          }
        }
      }
    } catch (err) {
      console.error('Error checking attendance pending classes:', err);
    }
  }, [user]);

  // Initial check & interval polling
  useEffect(() => {
    if (!user) return;

    checkClasses();

    // Auto request notification permission on first interaction if default
    if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'default') {
      const permTimer = setTimeout(() => {
        Notification.requestPermission().then((perm) => {
          setNotificationPermission(perm);
        }).catch(() => {});
      }, 2500);
      return () => clearTimeout(permTimer);
    }

    // Check periodically every 20 seconds
    const interval = setInterval(() => {
      checkClasses();
    }, 20000);

    // Also check whenever user switches back to this tab
    const handleFocus = () => checkClasses();
    window.addEventListener('focus', handleFocus);

    return () => {
      clearInterval(interval);
      window.removeEventListener('focus', handleFocus);
    };
  }, [user, checkClasses]);

  // Mark attendance for an occurrence
  const markAttendance = async (occurrenceId, status) => {
    try {
      setMarkingId(occurrenceId);
      await apiRequest('/attendance/mark', {
        method: 'POST',
        body: JSON.stringify({ occurrence_id: occurrenceId, status })
      });

      // Clear from justEndedClass if it was this one
      if (justEndedClass?.id === occurrenceId) {
        setJustEndedClass(null);
      }

      // Re-fetch pending classes
      await checkClasses();
    } catch (err) {
      alert(`Error updating attendance: ${err.message}`);
    } finally {
      setMarkingId(null);
    }
  };

  const openCheckIn = (occ) => {
    setModalOcc(occ);
    setIsQueueMode(false);
    setIsModalOpen(true);
  };

  const openQueueCheckIn = () => {
    if (unmarkedClasses.length > 0) {
      setModalOcc(unmarkedClasses[0]);
      setIsQueueMode(true);
      setIsModalOpen(true);
    }
  };

  return (
    <AttendanceNotificationContext.Provider
      value={{
        unmarkedClasses,
        unmarkedCount: unmarkedClasses.length,
        justEndedClass,
        dismissJustEnded: () => setJustEndedClass(null),
        markAttendance,
        markingId,
        openCheckIn,
        openQueueCheckIn,
        refreshPending: checkClasses,
        notificationPermission,
        requestNotificationPermission
      }}
    >
      {children}

      {/* -----------------------------------------------------------------
          A. INSTANT CLASS-ENDED POPUP TOAST (AS SOON AS CLASS IS OVER)
      ----------------------------------------------------------------- */}
      {justEndedClass && (
        <aside
          aria-label="Class ended reminder"
          className="fixed top-4 right-4 sm:right-6 z-50 max-w-md w-[calc(100vw-2rem)] bg-slate-900/95 backdrop-blur-md border border-teal-500/50 rounded-2xl p-4 shadow-2xl shadow-teal-500/10 animate-bounce-short"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-teal-500/20 text-teal-300 border border-teal-500/30">
                <Bell className="w-5 h-5 animate-pulse" />
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-teal-500/20 text-teal-300 border border-teal-500/30">
                  Class Over Just Now
                </span>
                <h4 className="text-sm font-bold text-white mt-1">
                  {justEndedClass.subject?.name || 'Your Class'}
                </h4>
              </div>
            </div>

            <button
              onClick={() => setJustEndedClass(null)}
              className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
              title="Dismiss reminder"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="text-xs text-slate-300 mt-2 font-mono flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-teal-400 shrink-0" />
            <span>
              {justEndedClass.start_time?.slice(0, 5)} – {justEndedClass.end_time?.slice(0, 5)}
              {justEndedClass.room ? ` • Room: ${justEndedClass.room}` : ''}
            </span>
          </div>

          <p className="text-xs text-slate-300 mt-1.5 font-medium">
            Did you attend this lecture? Mark your attendance now:
          </p>

          {/* Quick Action 1-Click Buttons */}
          <div className="grid grid-cols-3 gap-2 mt-3 text-xs font-semibold">
            <button
              type="button"
              disabled={markingId === justEndedClass.id}
              onClick={() => markAttendance(justEndedClass.id, 'present')}
              className="py-2 px-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold transition-all shadow-md shadow-emerald-600/20 flex items-center justify-center gap-1 cursor-pointer"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Present</span>
            </button>
            <button
              type="button"
              disabled={markingId === justEndedClass.id}
              onClick={() => markAttendance(justEndedClass.id, 'absent')}
              className="py-2 px-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold transition-all shadow-md shadow-rose-600/20 flex items-center justify-center gap-1 cursor-pointer"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>Absent</span>
            </button>
            <button
              type="button"
              onClick={() => {
                const target = justEndedClass;
                setJustEndedClass(null);
                openCheckIn(target);
              }}
              className="py-2 px-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-teal-300 border border-teal-500/30 font-semibold transition-all flex items-center justify-center gap-1 cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>+ Topic</span>
            </button>
          </div>
        </aside>
      )}

      {/* -----------------------------------------------------------------
          B. GLOBAL CHECK-IN MODAL
      ----------------------------------------------------------------- */}
      <ClassCheckInModal
        isOpen={isModalOpen}
        occurrence={modalOcc}
        pendingList={isQueueMode ? unmarkedClasses : []}
        onClose={() => {
          setIsModalOpen(false);
          setModalOcc(null);
        }}
        onCheckInComplete={() => {
          checkClasses();
        }}
      />
    </AttendanceNotificationContext.Provider>
  );
}

export function useAttendanceNotification() {
  const context = useContext(AttendanceNotificationContext);
  if (!context) {
    throw new Error('useAttendanceNotification must be used within an AttendanceNotificationProvider');
  }
  return context;
}
