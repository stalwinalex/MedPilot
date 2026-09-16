import React, { useState, useEffect } from 'react';
import {
  FileQuestion,
  Sparkles,
  BookOpen,
  TrendingUp,
  AlertCircle,
  HelpCircle,
  Layers,
  CheckCircle2,
  ChevronRight
} from 'lucide-react';
import { apiRequest } from '../api/client';

export default function PYQPage() {
  const [subjects, setSubjects] = useState([]);
  const [loading, setLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);

  const [form, setForm] = useState({
    subject_id: '',
    exam_name: 'University Professional Examination',
    years_covered: '2019 - 2024 (Last 5 Years)',
    raw_questions: ''
  });

  useEffect(() => {
    async function fetchSubjects() {
      try {
        const list = await apiRequest('/subjects/');
        setSubjects(list);
        if (list.length > 0) {
          setForm(prev => ({ ...prev, subject_id: list[0].id }));
        }
      } catch (err) {
        console.error(err);
      }
    }
    fetchSubjects();
  }, []);

  const handleAnalyze = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await apiRequest('/resources/pyq', {
        method: 'POST',
        body: JSON.stringify(form)
      });
      setAnalysisResult(res);
    } catch (err) {
      alert(`Error analyzing PYQs: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSampleLoad = () => {
    setForm(prev => ({
      ...prev,
      raw_questions: `1. Describe the anatomy of the Inguinal Canal with boundaries, contents, and clinical types of hernia. (10 marks)
2. Enumerate branches of the Axillary Artery and explain collateral circulation in ligature. (10 marks)
3. Describe the Femoral Triangle with its boundaries and contents. (5 marks)
4. Mechanism of Erb's Palsy and Klumpke's Paralysis with anatomical basis. (10 marks)
5. Boundaries and contents of the Cubital Fossa. (5 marks)
6. Describe the Inguinal Canal and direct vs indirect hernia. (Repeat Question, 10 marks)
7. Carpal Tunnel Syndrome: anatomical structures compressed and clinical signs. (5 marks)`
    }));
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-6 pb-24">
      {/* Header */}
      <div className="border-b border-[#E7EAF0] pb-6">
        <h1 className="text-2xl font-bold tracking-tight text-slate-800 flex items-center gap-2.5">
          <span className="p-2 rounded-xl bg-[#CFEDE7] text-[#1A4B43]">
            <FileQuestion className="w-5 h-5" />
          </span>
          <span>Previous-Year Question (PYQ) Analyzer</span>
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Extract repeated topics, frequent concept clusters, and question patterns from past university papers.
        </p>
      </div>

      {/* Input Form & Visualizer Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Left Column: Input Form */}
        <div className="bg-white border border-[#E7EAF0] rounded-2xl p-6 space-y-4 shadow-card">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
              Input Past Question Papers
            </h2>
            <button
              type="button"
              onClick={handleSampleLoad}
              className="text-xs text-[#1A4B43] hover:underline font-semibold"
            >
              Load Sample Paper
            </button>
          </div>

          <form onSubmit={handleAnalyze} className="space-y-3.5 text-xs">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Subject</label>
                <select
                  value={form.subject_id}
                  onChange={(e) => setForm({ ...form, subject_id: e.target.value })}
                  className="w-full py-2.5 px-3 bg-slate-50 border border-[#E7EAF0] rounded-xl text-slate-800 text-sm focus:outline-none focus:bg-white focus:border-[#72C9BE]"
                >
                  {subjects.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Years Covered</label>
                <input
                  type="text"
                  required
                  value={form.years_covered}
                  onChange={(e) => setForm({ ...form, years_covered: e.target.value })}
                  className="w-full py-2.5 px-3 bg-slate-50 border border-[#E7EAF0] rounded-xl text-slate-800 text-sm focus:outline-none focus:bg-white focus:border-[#72C9BE]"
                />
              </div>
            </div>

            <div>
              <label className="block text-slate-700 font-semibold mb-1">Exam Name / University</label>
              <input
                type="text"
                required
                value={form.exam_name}
                onChange={(e) => setForm({ ...form, exam_name: e.target.value })}
                className="w-full py-2.5 px-3 bg-slate-50 border border-[#E7EAF0] rounded-xl text-slate-800 text-sm focus:outline-none focus:bg-white focus:border-[#72C9BE]"
              />
            </div>

            <div>
              <label className="block text-slate-700 font-semibold mb-1">
                Raw Questions (Paste past university papers or question lists)
              </label>
              <textarea
                rows="8"
                required
                value={form.raw_questions}
                onChange={(e) => setForm({ ...form, raw_questions: e.target.value })}
                placeholder="Paste questions here e.g. 1. Describe the anatomy of inguinal canal..."
                className="w-full py-2.5 px-3.5 bg-slate-50 border border-[#E7EAF0] rounded-xl text-slate-800 text-xs font-mono leading-relaxed placeholder-slate-400 focus:outline-none focus:bg-white focus:border-[#72C9BE]"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !form.raw_questions.trim()}
              className="w-full py-3 rounded-xl bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 font-semibold text-xs shadow-xs disabled:opacity-50 transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <Sparkles className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              <span>{loading ? 'Analyzing Topic Patterns...' : 'Analyze Previous-Year Questions'}</span>
            </button>
          </form>
        </div>

        {/* Right Column: Analysis Output */}
        <div className="space-y-4">
          {analysisResult ? (
            <div className="bg-white border border-[#E7EAF0] rounded-2xl p-6 space-y-5 shadow-card animate-in fade-in">
              <div className="border-b border-[#E7EAF0] pb-3">
                <span className="text-xs font-semibold text-[#1A4B43] uppercase tracking-wider block">
                  PYQ Analytics Report &bull; {analysisResult.years_covered}
                </span>
                <h2 className="text-xl font-bold text-slate-800 mt-1">{analysisResult.exam_name}</h2>
              </div>

              {/* High-Yield Topics Frequency */}
              {analysisResult.topic_frequencies?.length > 0 && (
                <div className="space-y-2.5">
                  <span className="text-xs font-bold text-slate-600 uppercase tracking-wider flex items-center gap-1.5">
                    <TrendingUp className="w-4 h-4 text-[#72C9BE]" />
                    <span>Frequently Tested Concepts</span>
                  </span>
                  <div className="space-y-1.5">
                    {analysisResult.topic_frequencies.map((item, idx) => (
                      <div key={idx} className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-800">{item.topic}</span>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-[#1A4B43] font-bold">{item.frequency || 'Repeated'}</span>
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#CFEDE7] text-[#1A4B43] uppercase font-semibold">
                            {item.yield_level || 'High-Yield'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Question Patterns */}
              {analysisResult.repeated_patterns?.length > 0 && (
                <div className="space-y-2.5">
                  <span className="text-xs font-bold text-slate-600 uppercase tracking-wider flex items-center gap-1.5">
                    <Layers className="w-4 h-4 text-[#4C1D95]" />
                    <span>Examiner Question Patterns</span>
                  </span>
                  <div className="space-y-1.5">
                    {analysisResult.repeated_patterns.map((pat, idx) => (
                      <div key={idx} className="p-3 rounded-xl bg-[#F5F2FC] border border-[#D4C8F4]/50 text-xs space-y-1">
                        <span className="font-bold text-[#4C1D95] block">{pat.pattern}</span>
                        <p className="text-slate-600 text-[11px] leading-relaxed">{pat.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Guidance Notes */}
              {analysisResult.guidance_notes && (
                <div className="p-4 rounded-xl bg-[#F2FBF9] border border-[#CFEDE7] text-xs space-y-1">
                  <span className="font-bold text-[#1A4B43] block">Revision Guidance:</span>
                  <p className="text-slate-700 leading-relaxed text-[11px]">
                    {analysisResult.guidance_notes}
                  </p>
                </div>
              )}

              <div className="text-[10px] text-slate-400 italic text-center pt-2">
                * Note: PYQ analysis identifies historical patterns and does not guarantee specific questions will appear in future exams.
              </div>
            </div>
          ) : (
            <div className="p-16 text-center rounded-2xl bg-white border border-[#E7EAF0] shadow-card space-y-2 text-slate-500">
              <FileQuestion className="w-10 h-10 text-slate-300 mx-auto" />
              <p className="text-sm font-semibold text-slate-800">No analysis performed yet</p>
              <p className="text-xs text-slate-400 max-w-xs mx-auto">
                Paste past year question papers on the left and click "Analyze Previous-Year Questions" to see high-yield topic patterns.
              </p>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
