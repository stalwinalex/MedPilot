import React, { useState, useEffect } from 'react';
import {
  FolderDown,
  Plus,
  Sparkles,
  Download,
  Share2,
  BookOpen,
  CheckCircle2,
  HelpCircle,
  Eye,
  RefreshCw,
  Clock,
  Layers,
  X
} from 'lucide-react';
import { apiRequest } from '../api/client';

export default function ResourcesPage() {
  const [resources, setResources] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [friends, setFriends] = useState([]);
  const [loading, setLoading] = useState(true);

  // Modals & Selected View
  const [generateModal, setGenerateModal] = useState(false);
  const [selectedResource, setSelectedResource] = useState(null);
  const [shareModal, setShareModal] = useState(null);
  const [generating, setGenerating] = useState(false);

  // Generation form
  const [genForm, setGenForm] = useState({
    subject_id: '',
    topic: '',
    resource_type: 'summary', // summary, revision_sheet, mcq_bank, flashcards
    additional_instructions: ''
  });

  // Flashcard flip state
  const [flippedCards, setFlippedCards] = useState({});
  // MCQ state
  const [selectedAnswers, setSelectedAnswers] = useState({});

  const loadResources = async () => {
    try {
      setLoading(true);
      const [resList, subjList, friendList] = await Promise.all([
        apiRequest('/resources/'),
        apiRequest('/subjects/'),
        apiRequest('/friends/')
      ]);
      setResources(resList);
      setSubjects(subjList);
      setFriends(friendList);

      if (subjList.length > 0 && !genForm.subject_id) {
        setGenForm(prev => ({ ...prev, subject_id: subjList[0].id }));
      }
      if (resList.length > 0 && !selectedResource) {
        setSelectedResource(resList[0]);
      }
    } catch (err) {
      console.error('Error loading resources:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadResources();
  }, []);

  const handleGenerate = async (e) => {
    e.preventDefault();
    setGenerating(true);
    try {
      const res = await apiRequest('/resources/generate', {
        method: 'POST',
        body: JSON.stringify(genForm)
      });
      setGenerateModal(false);
      setGenForm(prev => ({ ...prev, topic: '', additional_instructions: '' }));
      await loadResources();
      setSelectedResource(res);
    } catch (err) {
      alert(`Error generating resource: ${err.message}`);
    } finally {
      setGenerating(false);
    }
  };

  const handleDownloadPdf = async (resourceId, title) => {
    try {
      const blob = await apiRequest(`/resources/${resourceId}/download`);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `MedPilot_${title.replace(/\s+/g, '_')}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      alert(`Download failed: ${err.message}`);
    }
  };

  const handleShare = async (friendId) => {
    try {
      await apiRequest('/friends/share', {
        method: 'POST',
        body: JSON.stringify({
          resource_id: shareModal.id,
          recipient_user_id: friendId,
          permission: 'download'
        })
      });
      alert('Resource successfully shared with your friend!');
      setShareModal(null);
    } catch (err) {
      alert(`Sharing failed: ${err.message}`);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-6 pb-24">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#E7EAF0] pb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-800 flex items-center gap-2.5">
            <span className="p-2 rounded-xl bg-[#CFEDE7] text-[#1A4B43]">
              <FolderDown className="w-5 h-5" />
            </span>
            <span>Study Resources & Revision Library</span>
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Summaries, active-recall flashcards, and MCQ banks generated with standard medical citations. Available for PDF download and peer sharing.
          </p>
        </div>

        <button
          onClick={() => setGenerateModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 text-sm font-semibold shadow-sm transition-all active:scale-95 cursor-pointer self-start"
        >
          <Sparkles className="w-4 h-4" />
          <span>Generate Resource</span>
        </button>
      </div>

      {/* Main Grid: Resource List + Interactive Resource Viewer */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column: Resources List */}
        <div className="space-y-3">
          <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
            Your Study Library ({resources.length})
          </h2>

          {loading ? (
            <div className="p-8 text-center rounded-2xl bg-white border border-[#E7EAF0] shadow-card">
              <div className="w-5 h-5 border-2 border-[#72C9BE] border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              <p className="text-xs text-slate-500">Loading resources...</p>
            </div>
          ) : resources.length === 0 ? (
            <div className="p-8 text-center rounded-2xl bg-white border border-dashed border-[#E7EAF0] shadow-card text-xs text-slate-500">
              No resources generated yet. Click "Generate Resource" to build high-yield summaries, flashcards, or MCQs.
            </div>
          ) : (
            <div className="space-y-2.5 max-h-[70vh] overflow-y-auto pr-1">
              {resources.map((r) => {
                const isSelected = selectedResource?.id === r.id;
                return (
                  <div
                    key={r.id}
                    onClick={() => { setSelectedResource(r); setFlippedCards({}); }}
                    className={`p-4 rounded-2xl border transition-all cursor-pointer space-y-2 ${
                      isSelected
                        ? 'bg-[#CFEDE7]/20 border-[#72C9BE] shadow-xs'
                        : 'bg-white border-[#E7EAF0] hover:border-slate-300 shadow-card'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-semibold text-slate-800 text-sm line-clamp-1">
                        {r.title}
                      </span>
                      <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full bg-[#CFEDE7] text-[#1A4B43] shrink-0">
                        {r.resource_type.replace('_', ' ')}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span>{r.subject?.name || 'General MBBS'}</span>
                      <span className="text-[11px] text-slate-400">{r.created_at?.slice(0, 10)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Interactive Resource Viewer */}
        <div className="lg:col-span-2">
          {selectedResource ? (
            <div className="bg-white border border-[#E7EAF0] rounded-2xl p-6 space-y-6 shadow-card">
              {/* Resource Header & Actions */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#E7EAF0]">
                <div className="space-y-1">
                  <span className="text-xs font-semibold text-[#1A4B43] uppercase tracking-wider">
                    {selectedResource.subject?.name || 'MBBS Resource'} &bull; {selectedResource.resource_type.replace('_', ' ').toUpperCase()}
                  </span>
                  <h2 className="text-xl font-bold text-slate-800">{selectedResource.title}</h2>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleDownloadPdf(selectedResource.id, selectedResource.title)}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 text-xs font-semibold shadow-xs transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Download PDF</span>
                  </button>
                  <button
                    onClick={() => setShareModal(selectedResource)}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-colors"
                  >
                    <Share2 className="w-3.5 h-3.5" />
                    <span>Share</span>
                  </button>
                </div>
              </div>

              {/* Interactive Content Viewer */}
              {/* Type 1: Flashcards */}
              {selectedResource.resource_type === 'flashcards' && (
                <div className="space-y-4">
                  <p className="text-xs text-slate-500 font-medium">
                    Click any card to flip and review active recall answers and clinical correlation.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {selectedResource.content_json?.cards?.map((card, idx) => {
                      const isFlipped = flippedCards[idx];
                      return (
                        <div
                          key={idx}
                          onClick={() => setFlippedCards({ ...flippedCards, [idx]: !isFlipped })}
                          className={`min-h-[160px] p-5 rounded-2xl border cursor-pointer flex flex-col justify-between transition-all ${
                            isFlipped
                              ? 'bg-[#F2FBF9] border-[#CFEDE7] shadow-xs'
                              : 'bg-white border-[#E7EAF0] hover:border-slate-300 shadow-card'
                          }`}
                        >
                          <div className="flex items-center justify-between text-[11px] text-slate-400 pb-2 border-b border-slate-100">
                            <span className="font-semibold">Card {idx + 1}</span>
                            <span className="text-[#1A4B43] font-medium">
                              {isFlipped ? 'Answer (Click to flip)' : 'Question (Click to flip)'}
                            </span>
                          </div>

                          <div className="py-3 text-sm text-slate-800 font-medium leading-relaxed">
                            {isFlipped ? card.back : card.front}
                          </div>

                          <div className="text-[11px] text-slate-400 flex items-center justify-between">
                            <span>{isFlipped ? 'Recalled concept' : 'Active recall'}</span>
                            <Layers className="w-3.5 h-3.5 text-[#72C9BE]" />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Type 2: MCQ Bank */}
              {selectedResource.resource_type === 'mcq_bank' && (
                <div className="space-y-5">
                  <p className="text-xs text-slate-500 font-medium">
                    Select an option to test your understanding and view clinical rationale.
                  </p>
                  {selectedResource.content_json?.questions?.map((q, qIdx) => {
                    const chosen = selectedAnswers[qIdx];
                    return (
                      <div key={qIdx} className="p-5 rounded-2xl bg-white border border-[#E7EAF0] space-y-3.5 shadow-card">
                        <span className="font-bold text-slate-800 text-sm block">
                          Q{qIdx + 1}. {q.question}
                        </span>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {q.options?.map((opt, oIdx) => {
                            const isCorrect = opt === q.correct_answer;
                            const isChosen = chosen === opt;
                            return (
                              <button
                                key={oIdx}
                                onClick={() => setSelectedAnswers({ ...selectedAnswers, [qIdx]: opt })}
                                className={`p-3 rounded-xl text-left text-xs font-medium border transition-all ${
                                  isChosen
                                    ? isCorrect
                                      ? 'bg-[#CFEDE7] text-[#1A4B43] border-[#72C9BE]'
                                      : 'bg-rose-50 text-rose-700 border-rose-300'
                                    : 'bg-slate-50 border-slate-200 text-slate-700 hover:border-slate-300'
                                }`}
                              >
                                {String.fromCharCode(65 + oIdx)}. {opt}
                              </button>
                            );
                          })}
                        </div>

                        {chosen && (
                          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1">
                            <span className="font-semibold text-[#1A4B43] block">
                              Correct Answer: {q.correct_answer}
                            </span>
                            {q.explanation && (
                              <p className="text-slate-600 text-[11px] leading-relaxed">
                                <b>Explanation:</b> {q.explanation}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Type 3: Summary / Notes */}
              {(selectedResource.resource_type === 'summary' ||
                selectedResource.resource_type === 'revision_sheet' ||
                selectedResource.resource_type === 'study_notes') && (
                <div className="space-y-4">
                  <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200 text-sm text-slate-700 leading-relaxed whitespace-pre-line">
                    {selectedResource.content_json?.summary ||
                     selectedResource.content_json?.notes ||
                     JSON.stringify(selectedResource.content_json, null, 2)}
                  </div>

                  {selectedResource.content_json?.key_points?.length > 0 && (
                    <div className="p-5 rounded-2xl bg-white border border-[#E7EAF0] shadow-card space-y-2">
                      <span className="font-bold text-[#1A4B43] text-xs uppercase tracking-wider block">
                        Key High-Yield Concepts:
                      </span>
                      <ul className="list-disc pl-5 space-y-1.5 text-xs text-slate-600">
                        {selectedResource.content_json.key_points.map((pt, idx) => (
                          <li key={idx}>{pt}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* Citations Footer */}
              {selectedResource.source_citations?.length > 0 && (
                <div className="pt-4 border-t border-[#E7EAF0] space-y-2">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                    Authoritative Medical Citations:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedResource.source_citations.map((c, i) => (
                      <span key={i} className="text-[11px] px-2.5 py-0.5 rounded-md bg-[#CFEDE7]/40 text-[#1A4B43] border border-[#72C9BE]/30">
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="p-16 text-center rounded-2xl bg-white border border-[#E7EAF0] shadow-card text-sm text-slate-500">
              Select a resource from the library or generate a new study resource.
            </div>
          )}
        </div>

      </div>

      {/* MODAL: Generate Resource */}
      {generateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="bg-white border border-[#E7EAF0] rounded-2xl max-w-md w-full p-6 space-y-4 shadow-float animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <h3 className="text-base font-bold text-slate-800 flex items-center gap-2">
                <span className="p-1.5 rounded-lg bg-[#CFEDE7] text-[#1A4B43]">
                  <Sparkles className="w-4 h-4" />
                </span>
                <span>Generate MBBS Study Resource</span>
              </h3>
              <button
                onClick={() => setGenerateModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleGenerate} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Subject</label>
                <select
                  value={genForm.subject_id}
                  onChange={(e) => setGenForm({ ...genForm, subject_id: e.target.value })}
                  className="w-full py-2.5 px-3.5 bg-slate-50 border border-[#E7EAF0] rounded-xl text-slate-800 text-sm focus:outline-none focus:bg-white focus:border-[#72C9BE]"
                >
                  <option value="">General Medical Concept</option>
                  {subjects.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">Topic Name</label>
                <input
                  type="text"
                  required
                  value={genForm.topic}
                  onChange={(e) => setGenForm({ ...genForm, topic: e.target.value })}
                  placeholder="e.g. Femoral Triangle Boundaries & Contents"
                  className="w-full py-2.5 px-3.5 bg-slate-50 border border-[#E7EAF0] rounded-xl text-slate-800 placeholder-slate-400 text-sm focus:outline-none focus:bg-white focus:border-[#72C9BE]"
                />
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">Resource Type</label>
                <select
                  value={genForm.resource_type}
                  onChange={(e) => setGenForm({ ...genForm, resource_type: e.target.value })}
                  className="w-full py-2.5 px-3.5 bg-slate-50 border border-[#E7EAF0] rounded-xl text-slate-800 text-sm focus:outline-none focus:bg-white focus:border-[#72C9BE]"
                >
                  <option value="summary">Conceptual High-Yield Summary</option>
                  <option value="revision_sheet">Quick Revision Sheet</option>
                  <option value="flashcards">Active-Recall Flashcards</option>
                  <option value="mcq_bank">Clinical MCQ Bank</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">Custom Notes / Exam Focus (Optional)</label>
                <input
                  type="text"
                  value={genForm.additional_instructions}
                  onChange={(e) => setGenForm({ ...genForm, additional_instructions: e.target.value })}
                  placeholder="e.g. Include clinical hernia correlations and viva spotters"
                  className="w-full py-2.5 px-3.5 bg-slate-50 border border-[#E7EAF0] rounded-xl text-slate-800 placeholder-slate-400 text-sm focus:outline-none focus:bg-white focus:border-[#72C9BE]"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-[#E7EAF0]">
                <button
                  type="button"
                  onClick={() => setGenerateModal(false)}
                  className="px-4 py-2 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-slate-100 font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={generating}
                  className="px-5 py-2 rounded-xl bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 font-semibold disabled:opacity-50 transition-colors shadow-xs"
                >
                  {generating ? 'Generating Resource...' : 'Generate Resource'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Share with Friend */}
      {shareModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="bg-white border border-[#E7EAF0] rounded-2xl max-w-md w-full p-6 space-y-4 shadow-float animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <h3 className="text-base font-bold text-slate-800 flex items-center gap-2">
                <span className="p-1.5 rounded-lg bg-[#CFEDE7] text-[#1A4B43]">
                  <Share2 className="w-4 h-4" />
                </span>
                <span>Share Privately With Friend</span>
              </h3>
              <button
                onClick={() => setShareModal(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-slate-600">
              Share <b>{shareModal.title}</b> directly with a classmate from your accepted friends list.
            </p>

            {friends.length === 0 ? (
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-500 text-center">
                You have not added any friends yet. Add friends on the Friends page to share resources privately!
              </div>
            ) : (
              <div className="space-y-2">
                {friends.map((f) => (
                  <div key={f.id} className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs">
                    <div>
                      <span className="font-semibold text-slate-800 block">{f.full_name}</span>
                      <span className="text-slate-500 text-[11px]">{f.email}</span>
                    </div>
                    <button
                      onClick={() => handleShare(f.id)}
                      className="px-3 py-1.5 rounded-lg bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 font-semibold text-xs transition-colors"
                    >
                      Share
                    </button>
                  </div>
                ))}
              </div>
            )}

            <button
              onClick={() => setShareModal(null)}
              className="w-full py-2 rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200 text-xs font-semibold transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
