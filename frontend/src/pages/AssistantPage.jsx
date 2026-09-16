import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Bot,
  Send,
  Sparkles,
  Clock,
  Play,
  RotateCcw,
  CheckCircle2,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Info,
  AlertCircle,
  X,
  Paperclip,
  FileText,
  Image as ImageIcon,
  Layers,
  Bookmark,
  ZoomIn,
  RefreshCw,
  Copy,
  Check,
  Code,
  MessageSquare,
  Plus,
  Trash2,
  PanelLeftClose,
  PanelLeftOpen,
  History
} from 'lucide-react';
import { apiRequest } from '../api/client';

const QUICK_PROMPTS = [
  "What should I study now?",
  "Explain upper limb briefly.",
  "Give me 3 good YouTube videos to study upper limb.",
  "Create a simple labelled brachial plexus diagram.",
  "Make 10 flashcards on upper limb."
];

// Helper: Lightweight zero-dependency inline markdown tokenizer
function formatInlineMarkdown(text) {
  if (!text) return null;

  const cleanText = text
    .replace(/\\\$/g, '$')
    .replace(/\$\\rightarrow\$/g, '→')
    .replace(/\$\\leftrightarrow\$/g, '↔')
    .replace(/\$K_m\$/g, 'Km')
    .replace(/\$NAD\^\+\$/g, 'NAD+');

  const parts = [];
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^\)]+\))/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(cleanText)) !== null) {
    if (match.index > lastIndex) {
      parts.push(cleanText.substring(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(
        <strong key={match.index} className="font-bold text-slate-900">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith('*') && token.endsWith('*')) {
      parts.push(
        <em key={match.index} className="italic text-slate-700">
          {token.slice(1, -1)}
        </em>
      );
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(
        <code key={match.index} className="px-1.5 py-0.5 rounded bg-slate-100 text-[#1E3A8A] font-mono text-[11px]">
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith('[') && token.includes('](')) {
      const linkMatch = token.match(/\[([^\]]+)\]\(([^\)]+)\)/);
      if (linkMatch) {
        parts.push(
          <a
            key={match.index}
            href={linkMatch[2]}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#0D9488] hover:underline font-semibold inline-flex items-center gap-0.5"
          >
            <span>{linkMatch[1]}</span>
            <ExternalLink className="w-2.5 h-2.5 inline" />
          </a>
        );
      }
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < cleanText.length) {
    parts.push(cleanText.substring(lastIndex));
  }

  return parts.length > 0 ? parts : cleanText;
}

// MarkdownView: Formats structured headings, lists, tables, alerts, and paragraphs
function MarkdownView({ content }) {
  if (!content) return null;

  const lines = content.split('\n');
  const elements = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i++;
      continue;
    }

    // Blockquote or Alert Callout
    if (trimmed.startsWith('>')) {
      const bqLines = [];
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        let bqLine = lines[i].trim().replace(/^>\s?/, '');
        if (bqLine.startsWith('[!NOTE]') || bqLine.startsWith('[!TIP]')) {
          bqLine = bqLine.replace(/^\[!(NOTE|TIP|IMPORTANT|WARNING)\]\s?/, '');
        }
        if (bqLine) bqLines.push(bqLine);
        i++;
      }
      elements.push(
        <div key={`bq-${i}`} className="my-2.5 p-3.5 rounded-xl bg-[#CFEDE7]/30 border-l-3 border-[#72C9BE] text-xs text-[#1A4B43] shadow-soft">
          {bqLines.map((l, li) => (
            <p key={li} className={li > 0 ? 'mt-1.5' : ''}>{formatInlineMarkdown(l)}</p>
          ))}
        </div>
      );
      continue;
    }

    // Table
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      const tableLines = [];
      while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
        tableLines.push(lines[i].trim());
        i++;
      }
      const rows = tableLines.filter((l) => !/^\|[\s\-:|]+\|$/.test(l));
      if (rows.length > 0) {
        const headerCells = rows[0].split('|').slice(1, -1).map((c) => c.trim());
        const bodyRows = rows.slice(1).map((r) => r.split('|').slice(1, -1).map((c) => c.trim()));

        elements.push(
          <div key={`table-${i}`} className="my-3 overflow-x-auto rounded-xl border border-[#E7EAF0] shadow-soft">
            <table className="min-w-full text-xs text-left divide-y divide-[#E7EAF0]">
              <thead className="bg-[#F8FAFC] font-semibold text-slate-800">
                <tr>
                  {headerCells.map((h, hi) => (
                    <th key={hi} className="px-3 py-2 border-r border-[#E7EAF0] last:border-r-0">
                      {formatInlineMarkdown(h)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E7EAF0] bg-white">
                {bodyRows.map((row, ri) => (
                  <tr key={ri} className="hover:bg-slate-50/50">
                    {row.map((cell, ci) => (
                      <td key={ci} className="px-3 py-2 border-r border-[#E7EAF0] last:border-r-0 text-slate-700">
                        {formatInlineMarkdown(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }
      continue;
    }

    // Headers
    if (trimmed.startsWith('#### ')) {
      elements.push(
        <h4 key={`h4-${i}`} className="text-xs font-bold text-[#1A4B43] mt-2.5 mb-1">
          {formatInlineMarkdown(trimmed.slice(5))}
        </h4>
      );
      i++;
      continue;
    }

    if (trimmed.startsWith('### ')) {
      elements.push(
        <h3 key={`h3-${i}`} className="text-sm font-bold text-slate-900 mt-3 mb-1 border-b border-[#E7EAF0] pb-1">
          {formatInlineMarkdown(trimmed.slice(4))}
        </h3>
      );
      i++;
      continue;
    }

    if (trimmed.startsWith('## ')) {
      elements.push(
        <h2 key={`h2-${i}`} className="text-sm font-bold text-[#1E3A8A] mt-3.5 mb-1.5">
          {formatInlineMarkdown(trimmed.slice(3))}
        </h2>
      );
      i++;
      continue;
    }

    if (trimmed.startsWith('# ')) {
      elements.push(
        <h1 key={`h1-${i}`} className="text-base font-bold text-slate-900 mt-4 mb-2">
          {formatInlineMarkdown(trimmed.slice(2))}
        </h1>
      );
      i++;
      continue;
    }

    // Bullet List Item
    if (/^[-*]\s/.test(trimmed)) {
      elements.push(
        <div key={`li-${i}`} className="flex items-start gap-2 my-1 text-xs text-slate-700 leading-relaxed pl-1">
          <span className="w-1.5 h-1.5 rounded-full bg-[#72C9BE] mt-1.5 shrink-0" />
          <div className="flex-1">{formatInlineMarkdown(trimmed.replace(/^[-*]\s+/, ''))}</div>
        </div>
      );
      i++;
      continue;
    }

    // Numbered List Item
    if (/^\d+\.\s/.test(trimmed)) {
      const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
      elements.push(
        <div key={`nli-${i}`} className="flex items-start gap-2 my-1 text-xs text-slate-700 leading-relaxed pl-1">
          <span className="text-[11px] font-bold text-[#1E3A8A] mt-0.5 shrink-0 w-4">{numMatch[1]}.</span>
          <div className="flex-1">{formatInlineMarkdown(numMatch[2])}</div>
        </div>
      );
      i++;
      continue;
    }

    // Paragraph
    elements.push(
      <p key={`p-${i}`} className="my-1.5 text-xs text-slate-700 leading-relaxed">
        {formatInlineMarkdown(trimmed)}
      </p>
    );
    i++;
  }

  return <div className="space-y-1">{elements}</div>;
}

// Interactive Flashcard Deck Component
function FlashcardDeckViewer({ cards = [], onSave, onRegenerate, onDifficultyChange }) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [saving, setSaving] = useState(false);

  if (!cards || cards.length === 0) return null;

  const currentCard = cards[currentIndex] || cards[0];

  const handlePrev = () => {
    setFlipped(false);
    setCurrentIndex((prev) => (prev > 0 ? prev - 1 : cards.length - 1));
  };

  const handleNext = () => {
    setFlipped(false);
    setCurrentIndex((prev) => (prev < cards.length - 1 ? prev + 1 : 0));
  };

  return (
    <div className="my-3 p-4 rounded-2xl bg-gradient-to-br from-[#F8FAFC] to-[#F1F5F9] border border-[#E7EAF0] shadow-soft space-y-3">
      {/* Deck Header */}
      <div className="flex items-center justify-between text-xs pb-2 border-b border-slate-200/80">
        <span className="font-bold text-slate-800 flex items-center gap-1.5">
          <Layers className="w-4 h-4 text-[#0D9488]" />
          <span>Flashcard Deck ({cards.length} Cards)</span>
        </span>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-white border border-slate-200 text-slate-600 font-semibold">
            {currentIndex + 1} / {cards.length}
          </span>
          <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${
            currentCard.difficulty === 'hard'
              ? 'bg-[#FDF2F4] text-[#C93B52] border border-[#EABFC5]'
              : currentCard.difficulty === 'easy'
              ? 'bg-[#CFEDE7]/50 text-[#1A4B43] border border-[#72C9BE]'
              : 'bg-[#B7D4F4]/40 text-[#1E3A8A] border border-[#B7D4F4]'
          }`}>
            {currentCard.difficulty || 'Medium'}
          </span>
        </div>
      </div>

      {/* The Interactive Card Face */}
      <div
        onClick={() => setFlipped(!flipped)}
        className="min-h-[140px] p-5 rounded-xl bg-white border border-[#E7EAF0] shadow-card flex flex-col justify-between cursor-pointer hover:border-[#72C9BE] transition-all select-none"
      >
        <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
          <span>{flipped ? 'Answer / High-Yield Explanation' : 'Question / Active Recall Prompt'}</span>
          <span className="text-slate-400 font-normal">Click card to {flipped ? 'see prompt' : 'reveal answer'}</span>
        </div>

        <div className="py-2.5 text-center">
          <p className="text-sm font-semibold text-slate-800 leading-relaxed">
            {flipped ? currentCard.back : currentCard.front}
          </p>
        </div>

        <div className="text-right">
          <span className="text-[10px] text-slate-400 italic">
            {currentCard.topic || 'Anatomy'}
          </span>
        </div>
      </div>

      {/* Navigation Controls */}
      <div className="flex items-center justify-between pt-1">
        <div className="flex items-center gap-1.5">
          <button
            onClick={handlePrev}
            className="p-1.5 rounded-lg bg-white hover:bg-slate-100 text-slate-700 border border-[#E7EAF0] text-xs font-semibold shadow-xs transition-colors cursor-pointer"
            title="Previous card"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            onClick={handleNext}
            className="p-1.5 rounded-lg bg-white hover:bg-slate-100 text-slate-700 border border-[#E7EAF0] text-xs font-semibold shadow-xs transition-colors cursor-pointer"
            title="Next card"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Action Controls: Save, Regenerate, Easier, Harder */}
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            onClick={async () => {
              setSaving(true);
              try {
                await onSave(cards);
              } finally {
                setSaving(false);
              }
            }}
            disabled={saving}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-[#0D9488] hover:bg-[#0B7A70] text-white text-xs font-semibold shadow-xs transition-colors cursor-pointer"
          >
            <Bookmark className="w-3.5 h-3.5" />
            <span>{saving ? 'Saving...' : 'Save to Library'}</span>
          </button>

          <button
            onClick={onRegenerate}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-[#E7EAF0] text-xs font-medium shadow-xs transition-colors cursor-pointer"
            title="Regenerate flashcards"
          >
            <RefreshCw className="w-3.5 h-3.5 text-slate-500" />
            <span>Regen</span>
          </button>

          <button
            onClick={() => onDifficultyChange('easy')}
            className="px-2.5 py-1.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-[#E7EAF0] text-xs font-medium shadow-xs transition-colors cursor-pointer"
          >
            Easier
          </button>

          <button
            onClick={() => onDifficultyChange('hard')}
            className="px-2.5 py-1.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-[#E7EAF0] text-xs font-medium shadow-xs transition-colors cursor-pointer"
          >
            Harder
          </button>
        </div>
      </div>
    </div>
  );
}

// Educational Diagram Viewer Component
function DiagramViewer({ image, onEnlarge }) {
  if (!image || !image.image_url) return null;
  const [activeTab, setActiveTab] = useState('svg'); // 'svg' | 'mermaid'
  const [copied, setCopied] = useState(false);

  const handleCopyMermaid = (e) => {
    e.stopPropagation();
    if (!image.mermaid_code) return;
    navigator.clipboard.writeText(image.mermaid_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 rounded-2xl bg-white border border-[#E7EAF0] overflow-hidden shadow-card">
      <div className="p-3 bg-[#F8FAFC] border-b border-[#E7EAF0] flex items-center justify-between">
        <span className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
          <ImageIcon className="w-3.5 h-3.5 text-[#0D9488]" />
          <span>{image.title || 'Educational Schematic Diagram'}</span>
        </span>
        <div className="flex items-center gap-2">
          {image.mermaid_code && (
            <div className="flex items-center bg-slate-200/70 p-0.5 rounded-lg text-[11px] font-medium text-slate-600">
              <button
                type="button"
                onClick={() => setActiveTab('svg')}
                className={`px-2 py-0.5 rounded-md transition-all cursor-pointer ${activeTab === 'svg' ? 'bg-white text-slate-800 shadow-xs font-semibold' : 'hover:text-slate-900'}`}
              >
                Schematic
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('mermaid')}
                className={`px-2 py-0.5 rounded-md transition-all cursor-pointer ${activeTab === 'mermaid' ? 'bg-white text-[#0D9488] shadow-xs font-semibold' : 'hover:text-slate-900'}`}
              >
                Mermaid
              </button>
            </div>
          )}
          {activeTab === 'svg' ? (
            <button
              onClick={() => onEnlarge(image)}
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#0D9488] hover:text-[#0B7A70] transition-colors cursor-pointer"
            >
              <ZoomIn className="w-3.5 h-3.5" />
              <span>Enlarge</span>
            </button>
          ) : (
            <button
              onClick={handleCopyMermaid}
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#0D9488] hover:text-[#0B7A70] transition-colors cursor-pointer"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied!' : 'Copy Code'}</span>
            </button>
          )}
        </div>
      </div>

      {activeTab === 'svg' ? (
        <div
          onClick={() => onEnlarge(image)}
          className="p-3 bg-[#F8FAFC]/50 flex items-center justify-center cursor-pointer max-h-[380px] overflow-hidden"
        >
          <img
            src={image.image_url}
            alt={image.title}
            className="max-h-[360px] w-auto object-contain rounded-lg shadow-xs hover:scale-[1.01] transition-transform"
          />
        </div>
      ) : (
        <div className="p-3 bg-slate-900 text-slate-100 font-mono text-xs overflow-x-auto max-h-[320px]">
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-700 text-slate-400 text-[10px]">
            <span>Mermaid.js Diagram Syntax (Structured & Free)</span>
            <button
              type="button"
              onClick={handleCopyMermaid}
              className="text-teal-400 hover:text-teal-300 flex items-center gap-1 cursor-pointer"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
          <pre className="whitespace-pre text-teal-300 leading-relaxed font-mono selection:bg-teal-700">{image.mermaid_code}</pre>
        </div>
      )}

      {image.caption && (
        <div className="p-3 bg-white text-xs text-slate-600 border-t border-[#E7EAF0] leading-relaxed">
          {image.caption}
        </div>
      )}
    </div>
  );
}

// Web Sources Card Component
function WebSourcesViewer({ sources = [] }) {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="my-2.5 space-y-2">
      <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">
        Verified Medical Learning Resources:
      </span>
      <div className="grid grid-cols-1 gap-2">
        {sources.map((src, idx) => (
          <a
            key={idx}
            href={src.url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-3 rounded-xl bg-[#F8FAFC] hover:bg-slate-100/80 border border-[#E7EAF0] flex items-start gap-2.5 transition-colors group shadow-xs"
          >
            <div className="p-1.5 rounded-lg bg-white border border-slate-200 text-[#0D9488] shrink-0 mt-0.5 group-hover:border-[#72C9BE]">
              <ExternalLink className="w-3.5 h-3.5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-900 group-hover:text-[#0D9488] truncate transition-colors">
                  {src.title}
                </span>
                <span className={`text-[9px] uppercase font-bold px-1.5 py-0.2 rounded ${
                  src.source_type === 'youtube'
                    ? 'bg-[#FDF2F4] text-[#C93B52]'
                    : 'bg-[#CFEDE7] text-[#1A4B43]'
                }`}>
                  {src.source_type}
                </span>
              </div>
              {src.snippet && (
                <p className="text-[11px] text-slate-500 line-clamp-2 mt-0.5 leading-relaxed">
                  {src.snippet}
                </p>
              )}
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}

const DEFAULT_WELCOME_MESSAGE = {
  role: 'assistant',
  content: "Hello! I am MedPilot, your Academic Companion for MBBS studies. I analyze your timetable, provide structured medical concept guides, and recommend your next focused study block.\n\nHow can I help your study workflow today?",
  source_type: 'student_data',
  citations: [
    "Gray's Anatomy for Students",
    "Guyton and Hall Textbook of Medical Physiology",
    "Robbins & Cotran Pathologic Basis of Disease"
  ],
  actions: []
};

export default function AssistantPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Conversation persistence state
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [loadingConversations, setLoadingConversations] = useState(false);

  const [messages, setMessages] = useState([DEFAULT_WELCOME_MESSAGE]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState('Thinking...');
  const [toast, setToast] = useState(null); // { message, type }

  // Attachment state
  const [attachedFile, setAttachedFile] = useState(null); // { file_id, filename, file_type, text_content, image_url }
  const [uploadingAttachment, setUploadingAttachment] = useState(false);
  const fileInputRef = useRef(null);

  // Enlarged Diagram Modal
  const [enlargedImage, setEnlargedImage] = useState(null);

  // Flexible Study Mode State
  const [studyModeModal, setStudyModeModal] = useState(false);
  const [studyDuration, setStudyDuration] = useState(60);
  const [studyTopic, setStudyTopic] = useState('');
  const [studyBreakdown, setStudyBreakdown] = useState(null);

  const messagesEndRef = useRef(null);

  const showToast = (message, type = 'success', duration = 3500) => {
    setToast({ message, type });
    if (duration) {
      setTimeout(() => {
        setToast((curr) => (curr?.message === message ? null : curr));
      }, duration);
    }
  };

  const loadConversation = async (convId) => {
    try {
      const data = await apiRequest(`/agent/conversations/${convId}`);
      const formatted = (data.messages || []).map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        agent_name: m.extra_data?.agent_name || (m.role === 'assistant' ? 'MedPilot Assistant' : undefined),
        source_type: m.extra_data?.source_type || (m.role === 'assistant' ? 'ai_generated' : undefined),
        citations: m.extra_data?.citations || [],
        web_sources: m.extra_data?.web_sources || [],
        generated_image: m.extra_data?.generated_image || null,
        flashcards: m.extra_data?.flashcards || [],
        actions: m.extra_data?.actions || [],
        file_attachment: m.extra_data?.file_attachment || null
      }));
      setMessages(formatted.length > 0 ? formatted : [DEFAULT_WELCOME_MESSAGE]);
      setActiveConversationId(convId);
      localStorage.setItem('medpilot_active_conv_id', convId);
    } catch (err) {
      showToast(`Failed to load conversation: ${err.message}`, 'error');
    }
  };

  const fetchConversationsAndRestore = async () => {
    setLoadingConversations(true);
    try {
      const list = await apiRequest('/agent/conversations');
      setConversations(list || []);

      if (list && list.length > 0) {
        const storedId = localStorage.getItem('medpilot_active_conv_id');
        const targetId = list.some((c) => c.id === storedId) ? storedId : list[0].id;
        await loadConversation(targetId);
      } else {
        setActiveConversationId(null);
        setMessages([DEFAULT_WELCOME_MESSAGE]);
      }
    } catch (err) {
      console.error('Failed to fetch conversations:', err);
    } finally {
      setLoadingConversations(false);
    }
  };

  useEffect(() => {
    fetchConversationsAndRestore();
  }, []);

  const handleSelectConversation = async (convId) => {
    if (convId === activeConversationId || loading) return;
    setLoading(true);
    try {
      await loadConversation(convId);
    } finally {
      setLoading(false);
    }
  };

  const handleNewChat = () => {
    setActiveConversationId(null);
    localStorage.removeItem('medpilot_active_conv_id');
    setMessages([DEFAULT_WELCOME_MESSAGE]);
    setInput('');
    setAttachedFile(null);
  };

  const handleDeleteConversation = async (e, convId) => {
    e.stopPropagation();
    try {
      await apiRequest(`/agent/conversations/${convId}`, { method: 'DELETE' });
      const updated = conversations.filter((c) => c.id !== convId);
      setConversations(updated);

      if (activeConversationId === convId) {
        if (updated.length > 0) {
          await loadConversation(updated[0].id);
        } else {
          handleNewChat();
        }
      }
      showToast('Conversation deleted', 'info');
    } catch (err) {
      showToast(`Failed to delete conversation: ${err.message}`, 'error');
    }
  };

  useEffect(() => {
    if (searchParams.get('prompt') === 'what_should_i_do_now') {
      triggerAgent('What should I study now?');
    }
    if (searchParams.get('study_mode') === 'true') {
      setStudyModeModal(true);
    }
  }, [searchParams]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Handle local file selection and upload
  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingAttachment(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/agent/upload', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`
        },
        body: formData
      });

      if (!res.ok) {
        throw new Error(`Upload failed with status ${res.status}`);
      }

      const uploadData = await res.json();
      setAttachedFile(uploadData);
      showToast(`Attached: ${uploadData.filename}`, 'success');
    } catch (err) {
      showToast(`File upload failed: ${err.message}`, 'error');
    } finally {
      setUploadingAttachment(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const triggerAgent = async (userText, overrideAttachment = null) => {
    if (loading) return;
    if (!userText.trim() && !attachedFile && !overrideAttachment) return;

    const attachmentToSend = overrideAttachment !== null ? overrideAttachment : attachedFile;
    const promptText = userText.trim() || (attachmentToSend ? `Review ${attachmentToSend.filename}` : '');

    // Set dynamic loading status based on query type
    const lower = promptText.toLowerCase();
    if (attachmentToSend?.file_type === 'pdf') {
      setLoadingStatus('Reading your PDF...');
    } else if (attachmentToSend?.file_type === 'image') {
      setLoadingStatus('Analyzing image...');
    } else if (lower.includes('diagram') || lower.includes('draw') || lower.includes('schematic')) {
      setLoadingStatus('Creating diagram...');
    } else if (lower.includes('flashcard')) {
      setLoadingStatus('Preparing flashcards...');
    } else if (lower.includes('youtube') || lower.includes('video') || lower.includes('search')) {
      setLoadingStatus('Searching the web...');
    } else {
      setLoadingStatus('Reasoning over medical curriculum...');
    }

    const newMessages = [
      ...messages,
      {
        role: 'user',
        content: promptText,
        file_attachment: attachmentToSend
      }
    ];

    setMessages(newMessages);
    setInput('');
    setAttachedFile(null);
    setLoading(true);

    try {
      // Gather conversation history (last 8 messages)
      const history = messages
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .slice(-8)
        .map((m) => ({
          role: m.role,
          content: m.content
        }));

      const res = await apiRequest('/agent/chat', {
        method: 'POST',
        body: JSON.stringify({
          message: promptText,
          conversation_id: activeConversationId || undefined,
          conversation_history: history,
          file_attachment: attachmentToSend
        })
      });

      setMessages([
        ...newMessages,
        {
          id: res.message_id,
          role: 'assistant',
          content: res.reply,
          agent_name: res.agent_name,
          source_type: res.source_type,
          citations: res.citations || [],
          web_sources: res.web_sources || [],
          generated_image: res.generated_image || null,
          flashcards: res.flashcards || [],
          actions: res.recommended_actions || []
        }
      ]);

      if (res.conversation_id) {
        setActiveConversationId(res.conversation_id);
        localStorage.setItem('medpilot_active_conv_id', res.conversation_id);
        const updatedList = await apiRequest('/agent/conversations');
        setConversations(updatedList || []);
      }
    } catch (err) {
      setMessages([
        ...newMessages,
        {
          role: 'assistant',
          content: `Sorry, I encountered an issue processing your request: ${err.message}`,
          source_type: 'error',
          citations: [],
          actions: []
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveFlashcards = async (cards) => {
    try {
      const res = await apiRequest('/agent/flashcards/save', {
        method: 'POST',
        body: JSON.stringify({
          title: `Flashcards (${cards.length} cards)`,
          cards: cards
        })
      });
      showToast(`Saved ${res.card_count} flashcards to your library!`, 'success');
    } catch (err) {
      showToast(`Failed to save flashcards: ${err.message}`, 'error');
    }
  };

  const handleStudyModeSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await apiRequest('/agent/study-mode', {
        method: 'POST',
        body: JSON.stringify({
          duration_minutes: parseInt(studyDuration),
          topic: studyTopic || 'High-Yield Medical Review'
        })
      });
      setStudyBreakdown(res);
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div className="flex h-[calc(100vh-5.5rem)] max-w-7xl mx-auto px-2 sm:px-4 py-3 gap-3">
      {/* CONVERSATION HISTORY SIDEBAR */}
      <div
        className={`${
          sidebarOpen ? 'w-64 sm:w-72' : 'w-0 -ml-3 opacity-0 pointer-events-none'
        } transition-all duration-200 flex flex-col bg-white border border-[#E7EAF0] rounded-2xl overflow-hidden shadow-card shrink-0`}
      >
        {/* Top Header of Sidebar */}
        <div className="p-3 border-b border-[#E7EAF0] flex items-center justify-between gap-2 bg-[#F8FAFC]">
          <button
            onClick={handleNewChat}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-[#CFEDE7] hover:bg-[#BDE7DF] text-[#1A4B43] border border-[#72C9BE]/50 text-xs font-semibold shadow-xs transition-all cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5 text-[#0D9488]" />
            <span>New Chat</span>
          </button>
          <button
            onClick={() => setSidebarOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
            title="Hide history"
          >
            <PanelLeftClose className="w-4 h-4" />
          </button>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Past Conversations
          </div>
          {loadingConversations ? (
            <div className="p-4 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-[#72C9BE] animate-spin" />
              <span>Loading chats...</span>
            </div>
          ) : conversations.length === 0 ? (
            <div className="p-4 text-center text-xs text-slate-400">
              No conversations yet. Ask a question to start!
            </div>
          ) : (
            conversations.map((c) => {
              const isActive = c.id === activeConversationId;
              return (
                <div
                  key={c.id}
                  onClick={() => handleSelectConversation(c.id)}
                  className={`group flex items-center justify-between p-2.5 rounded-xl text-xs cursor-pointer transition-all ${
                    isActive
                      ? 'bg-[#CFEDE7]/50 text-[#1A4B43] border border-[#72C9BE]/60 font-semibold shadow-xs'
                      : 'text-slate-700 hover:bg-slate-50 border border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <MessageSquare
                      className={`w-3.5 h-3.5 shrink-0 ${
                        isActive ? 'text-[#0D9488]' : 'text-slate-400'
                      }`}
                    />
                    <span className="truncate">{c.title || 'New Conversation'}</span>
                  </div>
                  <button
                    onClick={(e) => handleDeleteConversation(e, c.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:text-rose-600 text-slate-400 rounded transition-opacity"
                    title="Delete conversation"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* MAIN CHAT PANE */}
      <div className="flex-1 flex flex-col min-w-0 bg-transparent">
        {/* Header Banner */}
        <div className="pb-3 flex items-center justify-between border-b border-[#E7EAF0]">
          <div className="flex items-center gap-2.5">
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="p-2 rounded-xl border border-[#E7EAF0] bg-white hover:bg-slate-50 text-slate-600 text-xs flex items-center gap-1.5 shadow-xs cursor-pointer transition-colors"
                title="Open conversation history"
              >
                <PanelLeftOpen className="w-4 h-4 text-[#0D9488]" />
                <span className="hidden sm:inline font-medium">History</span>
              </button>
            )}
            <div>
              <h1 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                <span className="p-1 rounded-lg bg-[#CFEDE7] text-[#1A4B43]">
                  <Bot className="w-4 h-4" />
                </span>
                <span>AI Academic Companion</span>
              </h1>
              <p className="text-xs text-slate-500 hidden sm:block">
                Dynamic curriculum reasoning, real learning resources, diagrams, and flashcards.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleNewChat}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-[#E7EAF0] text-xs font-semibold shadow-xs transition-all cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5 text-[#0D9488]" />
              <span className="hidden sm:inline">New Chat</span>
            </button>

            <button
              onClick={() => { setStudyModeModal(true); setStudyBreakdown(null); }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-[#E7EAF0] text-xs font-semibold shadow-xs transition-all cursor-pointer"
            >
              <Clock className="w-3.5 h-3.5 text-[#72C9BE]" />
              <span className="hidden sm:inline">Flexible Study Mode</span>
              <span className="sm:hidden">Study Mode</span>
            </button>
          </div>
        </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto py-5 space-y-4 pr-1">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-2xl rounded-2xl p-4.5 shadow-card leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-[#CFEDE7] text-[#1A4B43] text-sm font-medium border border-[#72C9BE]/40'
                  : 'bg-white border border-[#E7EAF0] text-slate-700 text-sm space-y-3'
              }`}
            >
              {/* Header inside assistant message */}
              {msg.role === 'assistant' && (
                <div className="flex items-center justify-between text-[11px] pb-2 border-b border-slate-100">
                  <span className="font-semibold text-[#1A4B43] flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-[#72C9BE]" />
                    {msg.agent_name || 'MedPilot Academic Assistant'}
                  </span>
                  {msg.source_type && (
                    <span
                      className={`px-2 py-0.5 rounded-full uppercase font-mono text-[10px] ${
                        msg.source_type === 'ai_generated'
                          ? 'bg-[#CFEDE7] text-[#1A4B43] font-semibold'
                          : msg.source_type === 'unconfigured'
                          ? 'bg-[#F3DFAB]/50 text-[#6B4E17] font-semibold'
                          : msg.source_type === 'web_search'
                          ? 'bg-[#E0F2FE] text-[#0369A1] font-semibold'
                          : msg.source_type === 'diagram'
                          ? 'bg-[#EDE9FE] text-[#6D28D9] font-semibold'
                          : msg.source_type === 'flashcards'
                          ? 'bg-[#FEF3C7] text-[#92400E] font-semibold'
                          : msg.source_type === 'uploaded_file'
                          ? 'bg-[#F1F5F9] text-[#334155] font-semibold'
                          : 'bg-[#B7D4F4]/40 text-[#1E3A8A] font-semibold'
                      }`}
                    >
                      {msg.source_type === 'unconfigured'
                        ? 'Offline Reference'
                        : msg.source_type.replace('_', ' ')}
                    </span>
                  )}
                </div>
              )}

              {/* User Attached File Badge */}
              {msg.file_attachment && (
                <div className="mb-2 p-2 rounded-lg bg-white/60 border border-[#72C9BE]/50 flex items-center gap-2 text-xs text-[#1A4B43]">
                  {msg.file_attachment.file_type === 'image' ? (
                    <ImageIcon className="w-4 h-4 text-[#0D9488]" />
                  ) : (
                    <FileText className="w-4 h-4 text-[#0D9488]" />
                  )}
                  <span className="font-semibold truncate">{msg.file_attachment.filename}</span>
                </div>
              )}

              {/* Message Content */}
              {msg.role === 'assistant' ? (
                <MarkdownView content={msg.content} />
              ) : (
                <div className="whitespace-pre-line text-sm leading-relaxed">
                  {msg.content}
                </div>
              )}

              {/* Generated Image / Diagram Viewer */}
              {msg.generated_image && (
                <DiagramViewer
                  image={msg.generated_image}
                  onEnlarge={(img) => setEnlargedImage(img)}
                />
              )}

              {/* Interactive Flashcard Deck Viewer */}
              {msg.flashcards?.length > 0 && (
                <FlashcardDeckViewer
                  cards={msg.flashcards}
                  onSave={handleSaveFlashcards}
                  onRegenerate={() => triggerAgent('Regenerate these flashcards with fresh questions')}
                  onDifficultyChange={(diff) => triggerAgent(`Make these flashcards ${diff}`)}
                />
              )}

              {/* Web Sources Cards */}
              {msg.web_sources?.length > 0 && (
                <WebSourcesViewer sources={msg.web_sources} />
              )}

              {/* Recommended References Pill Tags */}
              {msg.citations?.length > 0 && (
                <div className="pt-2 border-t border-slate-100 space-y-1.5">
                  <span className="text-[10px] font-semibold text-slate-500 block uppercase tracking-wider">
                    Recommended references:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {msg.citations.map((cite, i) => (
                      <span key={i} className="text-[11px] px-2.5 py-0.5 rounded-md bg-[#CFEDE7]/40 text-[#1A4B43] border border-[#72C9BE]/30 font-medium">
                        {cite}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              {msg.actions?.length > 0 && (
                <div className="pt-2 flex flex-wrap gap-2">
                  {msg.actions.map((act, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        if (act.action_type === 'create_task') {
                          apiRequest('/planner/tasks', {
                            method: 'POST',
                            body: JSON.stringify({
                              title: act.payload.title,
                              priority: act.payload.priority || 'medium',
                              estimated_minutes: act.payload.estimated_minutes || 30,
                              scheduled_date: new Date().toISOString().split('T')[0]
                            })
                          })
                            .then(() => showToast(`Added task: ${act.payload.title}`, 'success'))
                            .catch((err) => showToast(`Error adding task: ${err.message}`, 'error'));
                        } else if (act.action_type === 'save_flashcards') {
                          handleSaveFlashcards(act.payload.cards || msg.flashcards || []);
                        } else if (act.action_type === 'log_attendance' || act.action_type === 'navigate') {
                          navigate(act.payload.route || '/attendance');
                        }
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-[#E7EAF0] text-xs font-semibold shadow-xs transition-colors cursor-pointer"
                    >
                      <Play className="w-3 h-3 text-[#72C9BE]" />
                      <span>{act.label}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Dynamic Subtle Loading Indicator */}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-[#E7EAF0] rounded-2xl p-4 flex items-center gap-3 shadow-card">
              <Sparkles className="w-4 h-4 text-[#72C9BE] animate-spin" />
              <span className="text-xs text-slate-600 font-medium">
                {loadingStatus}
              </span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick Prompts Chips */}
      <div className="py-2.5 overflow-x-auto flex items-center gap-2">
        {QUICK_PROMPTS.map((qp, i) => (
          <button
            key={i}
            onClick={() => !loading && triggerAgent(qp)}
            disabled={loading}
            className="shrink-0 text-xs px-3.5 py-1.5 rounded-full bg-white hover:bg-slate-50 text-slate-600 hover:text-slate-900 border border-[#E7EAF0] transition-colors cursor-pointer shadow-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {qp}
          </button>
        ))}
      </div>

      {/* Attached File Preview Chip */}
      {attachedFile && (
        <div className="mb-2 p-2.5 rounded-xl bg-[#CFEDE7]/40 border border-[#72C9BE] flex items-center justify-between text-xs text-[#1A4B43] shadow-soft">
          <div className="flex items-center gap-2 truncate">
            {attachedFile.file_type === 'image' ? (
              <ImageIcon className="w-4 h-4 text-[#0D9488] shrink-0" />
            ) : (
              <FileText className="w-4 h-4 text-[#0D9488] shrink-0" />
            )}
            <span className="font-semibold truncate">{attachedFile.filename}</span>
            <span className="text-[10px] text-slate-500 italic shrink-0">({attachedFile.file_type.toUpperCase()})</span>
          </div>
          <button
            onClick={() => !loading && setAttachedFile(null)}
            disabled={loading}
            className="p-1 rounded-md hover:bg-black/5 text-slate-500 hover:text-slate-800 transition-colors disabled:opacity-50"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Input Box with Attachment & Send Buttons */}
      <div className="pt-2">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!loading && (input.trim() || attachedFile)) {
              triggerAgent(input);
            }
          }}
          className="relative flex items-center"
        >
          {/* Hidden File Input */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".pdf,image/*,.txt,.md"
            className="hidden"
          />

          {/* Attachment Button */}
          <button
            type="button"
            onClick={() => !loading && fileInputRef.current?.click()}
            disabled={uploadingAttachment || loading}
            title="Attach study document, notes, or anatomical image"
            className="absolute left-2.5 p-2 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Paperclip className="w-4 h-4" />
          </button>

          <input
            type="text"
            value={input}
            disabled={loading}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!loading && (input.trim() || attachedFile)) {
                  triggerAgent(input);
                }
              }
            }}
            placeholder={loading ? 'Generating response...' : "Ask medical concepts, request diagrams, flashcards, or 'What should I study now?'..."}
            className="w-full pl-11 pr-14 py-3.5 bg-white border border-[#E7EAF0] rounded-2xl text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:border-[#72C9BE] shadow-card transition-all disabled:bg-slate-50 disabled:text-slate-400 disabled:cursor-not-allowed"
          />

          <button
            type="submit"
            disabled={(!input.trim() && !attachedFile) || loading}
            className="absolute right-2.5 p-2 rounded-xl bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 disabled:opacity-40 transition-all cursor-pointer shadow-xs disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>

        <div className="mt-2 text-center">
          <p className="text-[11px] text-slate-400">
            MedPilot is an educational study support companion. Powered by OpenAI with real source verification.
          </p>
        </div>
      </div>
    </div>

      {/* ENLARGED DIAGRAM MODAL */}
      {enlargedImage && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white border border-[#E7EAF0] rounded-2xl max-w-4xl w-full p-5 space-y-3 shadow-float animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-2">
              <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                <ImageIcon className="w-4 h-4 text-[#0D9488]" />
                <span>{enlargedImage.title || 'Educational Schematic'}</span>
              </h3>
              <button
                onClick={() => setEnlargedImage(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="max-h-[70vh] overflow-auto flex items-center justify-center p-2 bg-[#F8FAFC] rounded-xl border border-slate-200">
              <img
                src={enlargedImage.image_url}
                alt={enlargedImage.title}
                className="max-h-[65vh] w-auto object-contain"
              />
            </div>
            {enlargedImage.caption && (
              <p className="text-xs text-slate-600 leading-relaxed">
                {enlargedImage.caption}
              </p>
            )}
          </div>
        </div>
      )}

      {/* MODAL: Flexible Study Mode */}
      {studyModeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="bg-white border border-[#E7EAF0] rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-float animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-[#E7EAF0] pb-3">
              <h3 className="text-base font-bold text-slate-800 flex items-center gap-2">
                <span className="p-1.5 rounded-lg bg-[#CFEDE7] text-[#1A4B43]">
                  <Clock className="w-4 h-4" />
                </span>
                <span>Flexible Study Mode</span>
              </h3>
              <button onClick={() => setStudyModeModal(false)} className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100">
                <X className="w-4 h-4" />
              </button>
            </div>

            {!studyBreakdown ? (
              <form onSubmit={handleStudyModeSubmit} className="space-y-4 text-xs">
                <p className="text-slate-600 leading-relaxed">
                  Select your available time window. MedPilot will design an active-recall study session structured for maximum retention.
                </p>

                <div>
                  <label className="block text-slate-700 font-semibold mb-1.5">Session Duration</label>
                  <div className="grid grid-cols-3 gap-2">
                    {[30, 60, 120].map((dur) => (
                      <button
                        key={dur}
                        type="button"
                        onClick={() => setStudyDuration(dur)}
                        className={`py-2 rounded-xl font-semibold border transition-all ${
                          studyDuration === dur
                            ? 'bg-[#72C9BE] text-slate-900 border-[#72C9BE] shadow-xs'
                            : 'bg-slate-50 text-slate-600 border-slate-200 hover:border-slate-300'
                        }`}
                      >
                        {dur === 30 ? '30 Mins' : dur === 60 ? '1 Hour' : '2 Hours'}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Study Topic / Focus Area</label>
                  <input
                    type="text"
                    value={studyTopic}
                    onChange={(e) => setStudyTopic(e.target.value)}
                    placeholder="e.g. Cranial Nerves Anatomy & Lesions"
                    className="w-full py-2.5 px-3.5 bg-slate-50 border border-[#E7EAF0] rounded-xl text-slate-800 placeholder-slate-400 text-sm focus:outline-none focus:bg-white focus:border-[#72C9BE]"
                  />
                </div>

                <div className="flex justify-end gap-2 pt-2 border-t border-[#E7EAF0]">
                  <button
                    type="button"
                    onClick={() => setStudyModeModal(false)}
                    className="px-4 py-2 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-slate-100 font-medium transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-5 py-2.5 rounded-xl bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 font-semibold transition-colors shadow-xs"
                  >
                    Generate Session Structure
                  </button>
                </div>
              </form>
            ) : (
              <div className="space-y-4">
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-800 text-sm">
                      {studyDuration}-Minute Active Recall Protocol
                    </span>
                    <span className="text-xs font-mono text-[#1A4B43] font-bold">
                      {studyBreakdown.total_minutes} Total Mins
                    </span>
                  </div>

                  <div className="space-y-2">
                    {studyBreakdown.segments?.map((seg, i) => (
                      <div key={i} className="p-3 rounded-lg bg-white border border-[#E7EAF0] space-y-1 shadow-xs">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold text-[#1A4B43]">{seg.phase}</span>
                          <span className="font-mono text-slate-400">{seg.duration_minutes} mins</span>
                        </div>
                        <p className="text-xs text-slate-600">{seg.activity}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex justify-end gap-2 border-t border-[#E7EAF0] pt-3">
                  <button
                    onClick={() => setStudyBreakdown(null)}
                    className="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200 text-xs font-medium transition-colors"
                  >
                    Change Duration
                  </button>
                  <button
                    onClick={() => {
                      setStudyModeModal(false);
                      triggerAgent(`Let's start the ${studyDuration}-minute study session on: ${studyTopic || 'High-Yield Medical Review'}`);
                    }}
                    className="px-4 py-2 rounded-xl bg-[#72C9BE] hover:bg-[#5bb8ac] text-slate-900 text-xs font-semibold transition-colors shadow-xs"
                  >
                    Start Session Now
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 max-w-md w-[calc(100vw-3rem)] animate-in fade-in slide-in-from-bottom-2 duration-200">
          <div
            className={`p-4 rounded-2xl border shadow-float flex items-start gap-3 ${
              toast.type === 'error'
                ? 'bg-[#FDF2F4] border-[#EABFC5] text-[#69242E]'
                : toast.type === 'info'
                ? 'bg-[#F0F7FD] border-[#B7D4F4] text-[#1E3A8A]'
                : 'bg-[#F0FAF7] border-[#CFEDE7] text-[#1A4B43]'
            }`}
          >
            <div className="shrink-0 mt-0.5">
              {toast.type === 'error' ? (
                <AlertCircle className="w-4 h-4 text-[#C93B52]" />
              ) : toast.type === 'info' ? (
                <Info className="w-4 h-4 text-[#2563EB]" />
              ) : (
                <CheckCircle2 className="w-4 h-4 text-[#0D9488]" />
              )}
            </div>
            <div className="flex-1 text-xs font-medium leading-relaxed">
              {toast.message}
            </div>
            <button
              onClick={() => setToast(null)}
              className="shrink-0 p-1 rounded-lg hover:bg-black/5 transition-colors opacity-70 hover:opacity-100 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
