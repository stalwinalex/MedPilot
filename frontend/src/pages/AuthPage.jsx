import React, { useState } from 'react';
import { Stethoscope, Sparkles, ShieldAlert, ArrowRight, Lock, Mail, User, Building, GraduationCap } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const MBBS_YEARS = [
  'MBBS 1st Year',
  'MBBS 2nd Year',
  'MBBS 3rd Year Part 1',
  'MBBS Final Year',
  'Intern / Post-Graduate Aspirant'
];

export default function AuthPage() {
  const { login, register } = useAuth();
  const [isLogin, setIsLogin] = useState(true);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const [formData, setFormData] = useState({
    email: '',
    password: '',
    full_name: '',
    college: 'AIIMS / Medical College',
    year_of_study: 'MBBS 1st Year'
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isLogin) {
        await login(formData.email, formData.password);
      } else {
        await register(formData);
      }
    } catch (err) {
      setError(err.message || 'Authentication failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F7F8FC] text-slate-800 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Background soft pastel glow accents */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 bg-[#CFEDE7]/40 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-80 h-80 bg-[#B7D4F4]/30 rounded-full blur-3xl pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10 text-center">
        <div className="inline-flex p-3.5 bg-[#CFEDE7] rounded-2xl text-[#1A4B43] shadow-soft mb-4">
          <Stethoscope className="w-8 h-8" />
        </div>
        <h2 className="text-3xl font-bold tracking-tight text-slate-900">
          MedPilot
        </h2>
        <p className="mt-1 text-sm text-[#1A4B43] font-semibold">
          A Calm Academic Companion
        </p>
        <p className="mt-2 text-xs text-slate-500 max-w-xs mx-auto">
          Intelligent schedule management, deterministic attendance tracking, and medical study revision.
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <div className="bg-white border border-[#E7EAF0] py-8 px-6 shadow-card rounded-3xl sm:px-10">
          {/* Mode Switcher */}
          <div className="flex rounded-xl bg-slate-100 p-1 mb-6 border border-slate-200">
            <button
              type="button"
              onClick={() => { setIsLogin(true); setError(''); }}
              className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${
                isLogin
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => { setIsLogin(false); setError(''); }}
              className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${
                !isLogin
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Create Account
            </button>
          </div>

          {error && (
            <div className="mb-5 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{error}</span>
            </div>
          )}

          <form className="space-y-4" onSubmit={handleSubmit}>
            {!isLogin && (
              <>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Full Name
                  </label>
                  <div className="relative rounded-xl shadow-xs">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                      <User className="w-4 h-4" />
                    </div>
                    <input
                      type="text"
                      required
                      value={formData.full_name}
                      onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                      placeholder="Dr. Student Name"
                      className="block w-full pl-10 pr-3.5 py-2.5 bg-slate-50 border border-[#E7EAF0] rounded-xl text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Medical College
                  </label>
                  <div className="relative rounded-xl shadow-xs">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                      <Building className="w-4 h-4" />
                    </div>
                    <input
                      type="text"
                      required
                      value={formData.college}
                      onChange={(e) => setFormData({ ...formData, college: e.target.value })}
                      placeholder="AIIMS / Government Medical College"
                      className="block w-full pl-10 pr-3.5 py-2.5 bg-slate-50 border border-[#E7EAF0] rounded-xl text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Year of Study
                  </label>
                  <div className="relative rounded-xl shadow-xs">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                      <GraduationCap className="w-4 h-4" />
                    </div>
                    <select
                      value={formData.year_of_study}
                      onChange={(e) => setFormData({ ...formData, year_of_study: e.target.value })}
                      className="block w-full pl-10 pr-3.5 py-2.5 bg-slate-50 border border-[#E7EAF0] rounded-xl text-sm text-slate-800 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                    >
                      {MBBS_YEARS.map((yr) => (
                        <option key={yr} value={yr}>
                          {yr}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Institutional Email
              </label>
              <div className="relative rounded-xl shadow-xs">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  type="email"
                  required
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="student@medical.edu"
                  className="block w-full pl-10 pr-3.5 py-2.5 bg-slate-50 border border-[#E7EAF0] rounded-xl text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Password
              </label>
              <div className="relative rounded-xl shadow-xs">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type="password"
                  required
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  placeholder="••••••••••••"
                  className="block w-full pl-10 pr-3.5 py-2.5 bg-slate-50 border border-[#E7EAF0] rounded-xl text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-[#72C9BE] transition-colors"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-6 flex items-center justify-center gap-2 py-3 px-4 border border-transparent rounded-xl shadow-sm text-sm font-semibold text-slate-900 bg-[#72C9BE] hover:bg-[#5bb8ac] focus:outline-none disabled:opacity-50 transition-all cursor-pointer active:scale-95"
            >
              {loading ? (
                <span className="inline-block animate-pulse">Connecting...</span>
              ) : (
                <>
                  <span>{isLogin ? 'Sign In to MedPilot' : 'Complete Registration'}</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Educational Disclaimer Notice */}
          <div className="mt-6 pt-4 border-t border-[#E7EAF0] text-center">
            <p className="text-[11px] text-slate-400 leading-relaxed">
              MedPilot is exclusively an educational study companion for medical students. It does not provide clinical diagnosis or prescription advice.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
