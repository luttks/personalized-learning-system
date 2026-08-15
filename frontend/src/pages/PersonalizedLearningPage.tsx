import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  BrainCircuit,
  Calendar,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Code,
  ExternalLink,
  FileText,
  Flag,
  Layers,
  Lightbulb,
  Loader2,
  Mail,
  Plus,
  PlaySquare,
  ShieldAlert,
  Link2,
  Target,
  Trophy,
  Upload,
  X,
  Zap,
  History,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

import { getApiErrorMessage } from "../api/client";
import {
  analyzeDocument,
  generateQuiz,
  submitExam,
  parseExamDocument,
  listSubjects,
  listAnalysesBySubject,
  getExamAnalysis,
  type DocumentAnalysisResult,
  type ExamAnalysisDetail,
  type ExamAnalysisSummary,
  type ExamRecommendation,
  type ExamResources,
  type InlineRoadmap,
  type PhaseResources,
  type QuizQuestion,
  type ParseExamResponse,
  type SubjectSummary,
  type LearningDocumentContent,
  type LearningDocumentHighlight,
} from "../api/exam";
import { Button } from "../components/ui";

// ──────────────────────────────────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────────────────────────────────
type OnboardingScreen = "subject_list" | "upload_and_info" | "goal_selection" | "quiz" | "result";
type PostExamScreen = "exam_list" | "upload" | "select_and_score" | "result";

interface QuizAnswer {
  questionId: number;
  selectedOption: string;
  correct: boolean;
  topic: string;
  difficulty: string;
}

// ──────────────────────────────────────────────────────────────────────────
// Progress Bar (thay StepIndicator)
// ──────────────────────────────────────────────────────────────────────────
function ProgressBar({ progress, label }: { progress: number; label?: string }) {
  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-2">
        {label && <span className="text-xs font-medium text-slate-500">{label}</span>}
        <span className="text-xs font-bold text-indigo-600 ml-auto">{Math.round(progress)}%</span>
      </div>
      <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{
            width: `${progress}%`,
            background: "linear-gradient(90deg, #6366f1 0%, #818cf8 60%, #a5b4fc 100%)",
          }}
        />
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Multi-file DropZone
// ──────────────────────────────────────────────────────────────────────────
function MultiDropZone({
  files,
  onFiles,
  onRemove,
  accent = "indigo",
}: {
  files: File[];
  onFiles: (f: File[]) => void;
  onRemove: (index: number) => void;
  accent?: "indigo" | "emerald";
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const color = accent;

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const dropped = Array.from(e.dataTransfer.files);
      if (dropped.length) onFiles(dropped);
    },
    [onFiles]
  );

  return (
    <div className="space-y-2">
      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((f, i) => (
            <div
              key={i}
              className={`flex items-center gap-3 rounded-xl border-2 border-${color}-200 bg-${color}-50 px-4 py-3`}
            >
              <FileText className={`size-5 text-${color}-600 shrink-0`} />
              <div className="min-w-0 flex-1">
                <p className={`text-sm font-semibold text-${color}-900 truncate`}>{f.name}</p>
                <p className="text-xs text-slate-500">{(f.size / 1024).toFixed(0)} KB</p>
              </div>
              <button
                onClick={() => onRemove(i)}
                className="shrink-0 text-slate-400 hover:text-red-500 transition-colors"
              >
                <X className="size-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      <div
        className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all
          ${dragging ? `border-${color}-400 bg-${color}-50` : "border-slate-300 hover:border-indigo-300 hover:bg-slate-50"}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <Upload className="size-8 mx-auto text-slate-400 mb-2" />
        <p className="font-semibold text-slate-700 text-sm">
          {files.length > 0 ? "Thêm file khác" : "Kéo thả file hoặc nhấn để chọn"}
        </p>
        <p className="text-xs text-slate-500 mt-1">PDF, DOCX, TXT, JPG, PNG — có thể chọn nhiều file cùng lúc</p>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          multiple
          accept=".pdf,.jpg,.jpeg,.png,.docx,.txt,.html"
          onChange={(e) => {
            const selected = Array.from(e.target.files || []);
            if (selected.length) onFiles(selected);
            e.target.value = "";
          }}
        />
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Single file DropZone (for post exam)
// ──────────────────────────────────────────────────────────────────────────
function DropZone({
  file,
  onFile,
  onClear,
  accent = "indigo",
}: {
  file: File | null;
  onFile: (f: File) => void;
  onClear: () => void;
  accent?: "indigo" | "emerald";
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const color = accent;

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const f = e.dataTransfer.files[0];
      if (f) onFile(f);
    },
    [onFile]
  );

  if (file) {
    return (
      <div className={`flex items-center gap-3 rounded-xl border-2 border-${color}-200 bg-${color}-50 px-4 py-3`}>
        <FileText className={`size-5 text-${color}-600 shrink-0`} />
        <div className="min-w-0 flex-1">
          <p className={`text-sm font-semibold text-${color}-900 truncate`}>{file.name}</p>
          <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(0)} KB</p>
        </div>
        <button onClick={onClear} className="shrink-0 text-slate-400 hover:text-red-500 transition-colors">
          <X className="size-4" />
        </button>
      </div>
    );
  }

  return (
    <div
      className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all
        ${dragging ? `border-${color}-400 bg-${color}-50` : "border-slate-300 hover:border-indigo-300 hover:bg-slate-50"}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <Upload className="size-8 mx-auto text-slate-400 mb-2" />
      <p className="font-semibold text-slate-700 text-sm">Kéo thả file hoặc nhấn để chọn</p>
      <p className="text-xs text-slate-500 mt-1">PDF, DOCX, TXT, JPG, PNG — tối đa 20MB</p>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept=".pdf,.jpg,.jpeg,.png,.docx,.txt,.html"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); }}
      />
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Recommendation Panel
// ──────────────────────────────────────────────────────────────────────────
function RecommendationPanel({ rec }: { rec: ExamRecommendation }) {
  const groups = [
    { key: "nhom_co_ban" as const, label: "Kiến thức cơ bản", color: "emerald" },
    { key: "nhom_van_dung" as const, label: "Vận dụng", color: "amber" },
    { key: "nhom_van_dung_cao" as const, label: "Nâng cao", color: "red" },
  ];

  return (
    <div className="space-y-4">
      {rec.tom_tat_tong_quat && (
        <div className="rounded-xl bg-indigo-50 border border-indigo-200 p-4 text-sm text-indigo-900">
          <p className="font-semibold mb-1">📊 Nhận xét tổng quát</p>
          <p>{rec.tom_tat_tong_quat}</p>
        </div>
      )}
      {groups.map(({ key, label, color }) => {
        const group = rec[key];
        if (!group) return null;
        return (
          <div key={key} className={`rounded-xl border border-${color}-200 bg-${color}-50 p-4`}>
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-slate-800 text-sm">{label}</span>
              <span className={`text-xs rounded-full px-2 py-0.5 font-medium bg-${color}-100 text-${color}-800`}>
                {group.chi_tiet_tung_cau.length} câu
              </span>
            </div>
            <p className="text-sm text-slate-700 mb-3">{group.loi_khuyen_chung}</p>
            {group.chi_tiet_tung_cau.length > 0 && (
              <div className="space-y-2">
                {group.chi_tiet_tung_cau.map((q) => (
                  <div key={q.id_cau} className="bg-white rounded-lg p-3 text-xs border border-white/60 space-y-2">
                    <div>
                      <p className="font-medium text-slate-800">{q.id_cau} — <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{q.kien_thuc_can_hoc}</Markdown></p>
                      <div className="text-slate-600 mt-0.5 prose prose-sm max-w-none">
                        <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{q.loi_khuyen_ngan}</Markdown>
                      </div>
                    </div>
                    {q.mini_test_and_roadmap && (
                      <div className="mt-2 p-3 bg-red-50 border border-red-100 rounded-md">
                        <p className="font-semibold text-red-800 mb-1 flex items-center gap-1.5"><AlertCircle className="size-3.5" /> Bổ sung nền tảng gấp</p>
                        <div className="prose prose-sm max-w-none text-slate-700">
                          <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{q.mini_test_and_roadmap}</Markdown>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Phase Resources Panel
// ──────────────────────────────────────────────────────────────────────────
const phaseColors = [
  { bg: "bg-indigo-50", border: "border-indigo-200", badge: "bg-indigo-600", text: "text-indigo-900", dot: "bg-indigo-500" },
  { bg: "bg-emerald-50", border: "border-emerald-200", badge: "bg-emerald-600", text: "text-emerald-900", dot: "bg-emerald-500" },
  { bg: "bg-amber-50", border: "border-amber-200", badge: "bg-amber-600", text: "text-amber-900", dot: "bg-amber-500" },
  { bg: "bg-purple-50", border: "border-purple-200", badge: "bg-purple-600", text: "text-purple-900", dot: "bg-purple-500" },
];

function PhaseResourcesPanel({ res }: { res: PhaseResources }) {
  if (!res.youtube_tutorials?.length && !res.web_exercises?.length) return null;
  return (
    <div className="mt-4 space-y-3">
      {res.youtube_tutorials.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1.5">
            <PlaySquare className="size-3.5 text-red-500" /> Video học tập
          </p>
          <div className="space-y-1.5">
            {res.youtube_tutorials.map((v) => (
              <a key={v.video_id} href={v.watch_url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2 rounded-lg bg-red-50 border border-red-100 px-3 py-2 text-xs text-red-800 hover:border-red-300 transition-all group">
                <PlaySquare className="size-3.5 shrink-0 text-red-500" />
                <span className="truncate font-medium group-hover:underline">{v.title}</span>
                <span className="text-red-400 text-xs shrink-0">{v.channel_title}</span>
                <ExternalLink className="size-3 shrink-0 ml-auto text-red-400" />
              </a>
            ))}
          </div>
        </div>
      )}
      {res.web_exercises.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1.5">
            <BookOpen className="size-3.5 text-amber-500" /> Tài liệu & Bài tập
          </p>
          <div className="space-y-1.5">
            {res.web_exercises.map((ex) => (
              <a key={ex.url} href={ex.url} target="_blank" rel="noopener noreferrer"
                className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-100 px-3 py-2 text-xs text-amber-900 hover:border-amber-300 transition-all group">
                <ExternalLink className="size-3.5 shrink-0 mt-0.5 text-amber-500" />
                <div className="min-w-0">
                  <p className="font-medium group-hover:underline truncate">{ex.title}</p>
                  {ex.snippet && <p className="text-amber-700 text-xs line-clamp-1 mt-0.5">{ex.snippet}</p>}
                </div>
              </a>
            ))}
          </div>
        </div>
      )}
      {res.github_repos?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1.5">
            <Code className="size-3.5 text-slate-600" /> GitHub
          </p>
          <div className="space-y-1.5">
            {res.github_repos.map((r) => (
              <a key={r.url} href={r.url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2 rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-700 hover:border-slate-400 transition-all">
                <Code className="size-3.5 shrink-0 text-slate-500" />
                <span className="truncate font-medium">{r.full_name}</span>
                <span className="ml-auto shrink-0 text-amber-600">★ {r.stars.toLocaleString()}</span>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Inline Roadmap Panel
// ──────────────────────────────────────────────────────────────────────────
export function GlobalResourcesPanel({ res }: { res: ExamResources }) {
  if (!res.youtube_tutorials?.length && !res.quiz_exercises?.length && !res.github_repos?.length) return null;
  return (
    <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 space-y-4">
      <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
        <Link2 className="size-4 text-indigo-500" /> Tài liệu tham khảo tự động
      </h3>
      {res.youtube_tutorials?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1.5">
            <PlaySquare className="size-3.5 text-red-500" /> Video học tập
          </p>
          <div className="grid sm:grid-cols-2 gap-2">
            {res.youtube_tutorials.map((v) => (
              <a key={v.video_id} href={v.watch_url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2 rounded-lg bg-red-50 border border-red-100 px-3 py-2 text-xs text-red-800 hover:border-red-300 transition-all group">
                <PlaySquare className="size-3.5 shrink-0 text-red-500" />
                <span className="truncate font-medium group-hover:underline">{v.title}</span>
                <span className="text-red-400 text-xs shrink-0 ml-auto">{v.channel_title}</span>
              </a>
            ))}
          </div>
        </div>
      )}
      {res.quiz_exercises?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1.5">
            <BookOpen className="size-3.5 text-amber-500" /> Bài tập & Web
          </p>
          <div className="grid sm:grid-cols-2 gap-2">
            {res.quiz_exercises.map((ex) => (
              <a key={ex.url} href={ex.url} target="_blank" rel="noopener noreferrer"
                className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-100 px-3 py-2 text-xs text-amber-900 hover:border-amber-300 transition-all group">
                <ExternalLink className="size-3.5 shrink-0 mt-0.5 text-amber-500" />
                <div className="min-w-0">
                  <p className="font-medium group-hover:underline truncate">{ex.title}</p>
                  {ex.snippet && <p className="text-amber-700 text-xs line-clamp-1 mt-0.5">{ex.snippet}</p>}
                </div>
              </a>
            ))}
          </div>
        </div>
      )}
      {res.github_repos?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1.5">
            <Code className="size-3.5 text-slate-600" /> GitHub
          </p>
          <div className="grid sm:grid-cols-2 gap-2">
            {res.github_repos.map((r) => (
              <a key={r.url} href={r.url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2 rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-700 hover:border-slate-400 transition-all">
                <Code className="size-3.5 shrink-0 text-slate-500" />
                <span className="truncate font-medium">{r.full_name}</span>
                <span className="ml-auto shrink-0 text-amber-600">★ {r.stars.toLocaleString()}</span>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Inline Roadmap Panel
// ──────────────────────────────────────────────────────────────────────────
export function RoadmapInlinePanel({
  roadmap,
  phaseResources,
  subject,
  goal,
}: {
  roadmap: InlineRoadmap;
  phaseResources: Record<string, PhaseResources>;
  subject: string;
  goal: string;
}) {
  const [expandedPhase, setExpandedPhase] = useState<number | null>(0);
  const [applied, setApplied] = useState(false);

  function handleEmail() {
    const lines = [
      `LỘ TRÌNH HỌC TẬP: ${subject}`,
      `Mục tiêu: ${goal}`,
      `Tổng thời gian: ${roadmap.total_weeks} tuần`,
      ``,
      roadmap.overview,
      ``,
      ...roadmap.phases.flatMap((p) => [
        `--- Giai đoạn ${p.phase_number}: ${p.title} (${p.duration_weeks} tuần) ---`,
        `Mục tiêu: ${p.goal}`,
        `Chủ đề: ${p.topics.join(", ")}`,
        `Kế hoạch: ${p.daily_plan}`,
        `Cột mốc: ${p.milestone}`,
        ``,
      ]),
    ];
    const body = encodeURIComponent(lines.join("\n"));
    const subject_enc = encodeURIComponent(`Lộ trình học tập: ${subject}`);
    window.open(`mailto:?subject=${subject_enc}&body=${body}`);
  }

  function gcalLink(phase: (typeof roadmap.phases)[0], index: number) {
    const startOffset = roadmap.phases.slice(0, index).reduce((s, p) => s + p.duration_weeks * 7, 0);
    const start = new Date();
    start.setDate(start.getDate() + startOffset);
    const end = new Date(start);
    end.setDate(end.getDate() + phase.duration_weeks * 7);
    const fmt = (d: Date) => d.toISOString().replace(/[-:]/g, "").slice(0, 8);
    const title = encodeURIComponent(`[${subject}] Giai đoạn ${phase.phase_number}: ${phase.title}`);
    const details = encodeURIComponent(`Mục tiêu: ${phase.goal}\n\nChủ đề: ${phase.topics.join(", ")}\n\n${phase.daily_plan}`);
    return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${title}&dates=${fmt(start)}/${fmt(end)}&details=${details}`;
  }

  return (
    <div className="space-y-5">
      <div className="rounded-2xl bg-gradient-to-br from-indigo-600 to-indigo-800 p-5 text-white">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-indigo-200 text-xs font-semibold uppercase tracking-wider mb-1">Lộ trình học tập AI</p>
            <h3 className="text-xl font-black">{subject}</h3>
            <p className="text-indigo-200 text-sm mt-1">{roadmap.overview}</p>
          </div>
          <div className="shrink-0 flex flex-col items-center bg-white/10 rounded-xl px-3 py-2 text-center">
            <Clock3 className="size-5 mb-1 text-indigo-200" />
            <p className="text-2xl font-black">{roadmap.total_weeks}</p>
            <p className="text-xs text-indigo-200">tuần</p>
          </div>
        </div>
        <div className="flex gap-2 mt-4">
          <button
            onClick={handleEmail}
            className="flex items-center gap-2 rounded-lg bg-white/10 hover:bg-white/20 px-3 py-2 text-xs font-semibold text-white transition-all border border-white/20"
          >
            <Mail className="size-3.5" /> Gửi qua Email
          </button>
          <button
            onClick={() => setApplied(true)}
            className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold transition-all border border-white/20
              ${applied ? "bg-emerald-500 text-white" : "bg-white text-indigo-700 hover:bg-indigo-50"}`}
          >
            {applied ? <><CheckCircle2 className="size-3.5" /> Đã áp dụng</> : <><Flag className="size-3.5" /> Áp dụng lộ trình</>}
          </button>
        </div>
      </div>

      <div className="space-y-3">
        {roadmap.phases.map((phase, i) => {
          const c = phaseColors[i % phaseColors.length];
          const phaseKey = `phase_${phase.phase_number}`;
          const phaseRes = phaseResources[phaseKey];
          const isOpen = expandedPhase === i;

          return (
            <div key={phase.phase_number} className={`rounded-2xl border-2 ${c.border} ${c.bg} overflow-hidden transition-all`}>
              <button
                className="w-full flex items-center gap-3 p-4 text-left"
                onClick={() => setExpandedPhase(isOpen ? null : i)}
              >
                <span className={`shrink-0 size-8 rounded-full ${c.badge} text-white text-sm font-black flex items-center justify-center`}>
                  {phase.phase_number}
                </span>
                <div className="flex-1 min-w-0">
                  <p className={`font-bold ${c.text} text-sm`}>{phase.title}</p>
                  <p className="text-slate-500 text-xs mt-0.5">{phase.duration_weeks} tuần · {phase.topics.slice(0, 2).join(", ")}{phase.topics.length > 2 ? "..." : ""}</p>
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href={gcalLink(phase, i)}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="flex items-center gap-1 rounded-lg bg-white/60 hover:bg-white px-2 py-1 text-xs font-medium text-slate-600 transition-all border border-slate-200"
                    title="Thêm vào Google Calendar"
                  >
                    <Calendar className="size-3.5 text-blue-500" />
                    <span className="hidden sm:inline">Lịch</span>
                  </a>
                  <ChevronRight className={`size-4 text-slate-400 transition-transform ${isOpen ? "rotate-90" : ""}`} />
                </div>
              </button>
              {isOpen && (
                <div className="px-4 pb-4 space-y-4 border-t border-white/40 pt-3">
                  <div className="rounded-xl bg-white/70 p-3 text-sm">
                    <p className="font-semibold text-slate-800 mb-1 flex items-center gap-2"><Target className="size-3.5 text-indigo-500" /> Mục tiêu</p>
                    <p className="text-slate-700">{phase.goal}</p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1.5"><Layers className="size-3.5" /> Chủ đề cần học</p>
                    <div className="flex flex-wrap gap-1.5">
                      {phase.topics.map((t) => (
                        <span key={t} className="rounded-full bg-white border border-slate-200 px-2.5 py-0.5 text-xs font-medium text-slate-700">{t}</span>
                      ))}
                    </div>
                  </div>
                  {phase.source_refs && phase.source_refs.length > 0 && (
                    <div className="rounded-xl bg-amber-50 border border-amber-200 p-3">
                      <p className="text-xs font-semibold text-amber-800 mb-2 flex items-center gap-1.5"><BookOpen className="size-3.5" /> Nguồn trọng tâm trong tài liệu</p>
                      <div className="flex flex-wrap gap-1.5">
                        {phase.source_refs.map((ref) => (
                          <span key={ref.highlight_id} className="rounded-full bg-amber-100 border border-amber-200 px-2 py-0.5 text-xs text-amber-900">{ref.concept}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="rounded-xl bg-white/70 p-3 text-sm">
                    <p className="font-semibold text-slate-800 mb-1">📅 Kế hoạch hàng ngày</p>
                    <p className="text-slate-700">{phase.daily_plan}</p>
                  </div>
                  <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3 text-sm">
                    <p className="font-semibold text-emerald-800 mb-0.5">🏁 Cột mốc</p>
                    <p className="text-emerald-700">{phase.milestone}</p>
                  </div>
                  {phaseRes && <PhaseResourcesPanel res={phaseRes} />}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Result Panel (wraps AI rec + roadmap — luồng 1)
// ──────────────────────────────────────────────────────────────────────────
function DocumentReader({ content, compact = false }: { content: LearningDocumentContent; compact?: boolean }) {
  const [filter, setFilter] = useState<"all" | "must_learn" | "should_learn" | "reference">("all");
  const [selected, setSelected] = useState<LearningDocumentHighlight | null>(null);
  const highlightsByBlock = new Map(
    content.highlights
      .filter((highlight) => filter === "all" || highlight.importance === filter)
      .flatMap((highlight) => highlight.evidence.map((evidence) => [evidence.block_id, highlight] as const)),
  );
  const visibleBlocks = compact ? content.blocks.slice(0, 80) : content.blocks;
  const filterClass = (value: "all" | "must_learn" | "should_learn" | "reference") => {
    if (filter !== value) return "bg-white border-slate-200 text-slate-500 hover:border-indigo-300";
    if (value === "must_learn") return "bg-amber-100 border-amber-300 text-amber-800";
    if (value === "should_learn") return "bg-blue-100 border-blue-300 text-blue-800";
    if (value === "reference") return "bg-slate-200 border-slate-300 text-slate-700";
    return "bg-indigo-100 border-indigo-300 text-indigo-800";
  };
  return (
    <section className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-slate-50 px-4 py-3">
        <div className="mr-auto min-w-0">
          <p className="text-sm font-semibold text-slate-800 flex items-center gap-2"><BookOpen className="size-4 text-indigo-600" /> Tài liệu trọng tâm</p>
          <p className="text-xs text-slate-500 truncate">{content.filename} · {content.source_characters.toLocaleString()} ký tự</p>
        </div>
        {(["must_learn", "should_learn", "reference", "all"] as const).map((value) => (
          <button key={value} type="button" onClick={() => setFilter(value)} className={"rounded-full px-2.5 py-1 text-xs font-medium border transition-colors " + filterClass(value)}>
            {value === "must_learn" ? "Cốt lõi" : value === "should_learn" ? "Hỗ trợ" : value === "reference" ? "Đối chiếu" : "Tất cả"}
          </button>
        ))}
      </div>
      <div className={(compact ? "max-h-72" : "max-h-[32rem]") + " overflow-y-auto px-4 py-3 space-y-1"}>
        {visibleBlocks.map((block) => {
          const highlight = highlightsByBlock.get(block.id);
          const blockClass = highlight
            ? highlight.importance === "must_learn" ? "bg-amber-100/90 hover:bg-amber-200"
              : highlight.importance === "should_learn" ? "bg-blue-100/70 hover:bg-blue-200"
                : "bg-slate-100 hover:bg-slate-200"
            : "hover:bg-slate-50";
          return (
            <button key={block.id} type="button" onClick={() => highlight && setSelected(highlight)}
              className={"w-full text-left rounded-md px-3 py-2 text-sm leading-6 transition-colors " + blockClass + " " + (block.type === "heading" ? "font-bold text-slate-900" : "text-slate-700")}>
              {block.type === "table_row" ? (
                <span className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {block.text.replace(/^\[BẢNG\]\s*/, "").split(" | ").map((cell, index) => <span key={index} className="rounded bg-white/70 px-2 py-1">{cell}</span>)}
                </span>
              ) : block.text}
              {highlight && <span className="ml-2 align-middle text-[10px] uppercase tracking-wide text-slate-500">{highlight.importance === "must_learn" ? "trọng tâm" : "nguồn"}</span>}
            </button>
          );
        })}
        {compact && content.blocks.length > visibleBlocks.length && <p className="px-3 py-2 text-xs text-slate-400">Mở kết quả để xem toàn bộ tài liệu.</p>}
      </div>
      {selected && (
        <div className="border-t border-slate-200 bg-indigo-50 px-4 py-3">
          <p className="text-xs font-semibold text-indigo-900">{selected.concept}</p>
          <p className="mt-1 text-xs text-indigo-800">{selected.reason}</p>
        </div>
      )}
    </section>
  );
}

function ResultPanel({ result }: { result: ExamAnalysisDetail }) {
  const [tab, setTab] = useState<"roadmap" | "rec" | "document">("roadmap");
  const hasRec = Object.keys(result.ai_recommendation).filter((k) => !k.startsWith("_")).length > 0;
  const hasRoadmap = result.roadmap && result.roadmap.phases?.length > 0;
  const subject = result.subject || result.ai_recommendation?.["_goal"] ? (result.subject || result.filename.replace(/\.[^.]+$/, "")) : "Học tập";
  const goal = (result.ai_recommendation?.["_goal"] as string) || "Nắm vững kiến thức";

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5">
      {result.roadmap_error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <AlertCircle className="size-4 shrink-0 mt-0.5 text-red-500" />
          <p>{result.roadmap_error}</p>
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs text-slate-500 mb-1">Câu hỏi phân tích</p>
          <p className="text-2xl font-black text-slate-900">{result.question_count}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs text-slate-500 mb-1">Mastery cập nhật</p>
          <p className="text-2xl font-black text-emerald-700">{result.mastery_updates.length}</p>
        </div>
        {result.exam_score !== null && (
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-500 mb-1">Điểm số</p>
            <p className="text-2xl font-black text-indigo-700">{result.exam_score}/{result.exam_max_score}</p>
          </div>
        )}
      </div>

      <div className="flex border-b border-slate-200 gap-1">
        {hasRoadmap && (
          <button
            onClick={() => setTab("roadmap")}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-all
              ${tab === "roadmap" ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500 hover:text-slate-700"}`}
          >
            <Flag className="size-4" /> Lộ trình học tập
          </button>
        )}
        {hasRec && (
          <button
            onClick={() => setTab("rec")}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-all
              ${tab === "rec" ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500 hover:text-slate-700"}`}
          >
            <BrainCircuit className="size-4" /> Phân tích AI
          </button>
        )}
        {result.document_content?.blocks?.length > 0 && (
          <button
            onClick={() => setTab("document")}
            className={"flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-all " +
              (tab === "document" ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500 hover:text-slate-700")}
          >
            <BookOpen className="size-4" /> Tài liệu
          </button>
        )}
      </div>

      {tab === "roadmap" && hasRoadmap && (
        <RoadmapInlinePanel
          roadmap={result.roadmap!}
          phaseResources={result.phase_resources ?? {}}
          subject={subject}
          goal={goal}
        />
      )}
      {tab === "rec" && hasRec && <RecommendationPanel rec={result.ai_recommendation} />}
      {tab === "document" && result.document_content?.blocks?.length > 0 && <DocumentReader content={result.document_content} />}

      {/* Crawled Resources (Global) */}
      {result.resources && <GlobalResourcesPanel res={result.resources} />}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Post-Exam Result Panel
// ──────────────────────────────────────────────────────────────────────────
function PostExamResultPanel({ result }: { result: ExamAnalysisDetail }) {
  const solutionResults = result.solution_results || [];
  const level1 = solutionResults.filter((s) => s.support_level === "Hiểu đề nhưng không biết bắt đầu từ đâu");
  const level2 = solutionResults.filter((s) => s.support_level === "Sắp làm được rồi nhưng vẫn còn thiếu một chút");
  const level3 = solutionResults.filter((s) => s.support_level === "Không biết làm");
  const hasRoadmap = result.roadmap && result.roadmap.phases?.length > 0;
  const subject = result.subject || "Học tập";

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {result.roadmap_error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <AlertCircle className="size-4 shrink-0 mt-0.5 text-red-500" />
          <p>{result.roadmap_error}</p>
        </div>
      )}
      {/* Score summary */}
      {result.exam_score !== null && (
        <div className="rounded-2xl bg-gradient-to-br from-emerald-500 to-emerald-700 p-5 text-white text-center">
          <p className="text-emerald-200 text-xs font-semibold uppercase tracking-wider mb-1">Điểm số bài thi</p>
          <p className="text-5xl font-black">{result.exam_score}</p>
          <p className="text-emerald-200 text-sm mt-1">/ {result.exam_max_score} điểm</p>
        </div>
      )}

      {/* Level 1: Hiểu đề nhưng không biết làm */}
      {level1.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <div className="size-8 rounded-full bg-amber-100 flex items-center justify-center">
              <Lightbulb className="size-4 text-amber-600" />
            </div>
            <h3 className="font-bold text-slate-800">Hiểu đề nhưng không biết bắt đầu từ đâu</h3>
            <span className="ml-auto text-xs bg-amber-100 text-amber-700 rounded-full px-2 py-0.5 font-medium">{level1.length} câu</span>
          </div>
          {level1.map((s) => (
            <div key={s.question_id} className="rounded-2xl border border-amber-200 bg-amber-50 p-4 space-y-3">
              <div className="text-sm font-bold text-amber-900">{s.question_id}</div>
              <div className="text-xs text-slate-600 prose prose-sm max-w-none">
                <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{s.question_content}</Markdown>
              </div>
              {s.hint && (
                <div className="rounded-xl bg-white border border-amber-200 p-3 space-y-1.5">
                  <p className="text-xs font-semibold text-amber-800 flex items-center gap-1.5"><Zap className="size-3.5" /> Hướng tiếp cận</p>
                  <div className="text-xs text-slate-700 prose prose-sm max-w-none">
                    <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{s.hint}</Markdown>
                  </div>
                </div>
              )}
              {s.tips && (
                <div className="rounded-xl bg-white border border-amber-200 p-3">
                  <p className="text-xs font-semibold text-amber-800 mb-1">💡 Lời khuyên</p>
                  <div className="text-xs text-slate-700 prose prose-sm max-w-none">
                    <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{s.tips}</Markdown>
                  </div>
                </div>
              )}
              {s.crawled_solutions.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 mb-1.5 flex items-center gap-1.5">
                    <ExternalLink className="size-3.5" /> Lời giải tham khảo
                  </p>
                  <div className="space-y-1.5">
                    {s.crawled_solutions.map((sol) => (
                      <a key={sol.url} href={sol.url} target="_blank" rel="noopener noreferrer"
                        className="flex items-start gap-2 rounded-lg bg-white border border-amber-200 px-3 py-2 text-xs hover:border-amber-400 transition-all group">
                        <ExternalLink className="size-3.5 shrink-0 mt-0.5 text-amber-500" />
                        <div className="min-w-0">
                          <p className="font-medium group-hover:underline truncate text-amber-900">{sol.title}</p>
                          {sol.snippet && <p className="text-slate-500 line-clamp-1 mt-0.5">{sol.snippet}</p>}
                        </div>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Level 2: Sắp làm được rồi */}
      {level2.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <div className="size-8 rounded-full bg-blue-100 flex items-center justify-center">
              <Target className="size-4 text-blue-600" />
            </div>
            <h3 className="font-bold text-slate-800">Sắp làm được rồi</h3>
            <span className="ml-auto text-xs bg-blue-100 text-blue-700 rounded-full px-2 py-0.5 font-medium">{level2.length} câu</span>
          </div>
          {level2.map((s) => (
            <div key={s.question_id} className="rounded-2xl border border-blue-200 bg-blue-50 p-4 space-y-3">
              <div className="text-sm font-bold text-blue-900">{s.question_id}</div>
              <div className="text-xs text-slate-600 prose prose-sm max-w-none">
                <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{s.question_content}</Markdown>
              </div>
              {s.hint && (
                <div className="rounded-xl bg-white border border-blue-200 p-3 space-y-1.5">
                  <p className="text-xs font-semibold text-blue-800 flex items-center gap-1.5"><Zap className="size-3.5" /> Hướng giải quyết</p>
                  <div className="text-xs text-slate-700 prose prose-sm max-w-none">
                    <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{s.hint}</Markdown>
                  </div>
                </div>
              )}
              {s.traps && (
                <div className="rounded-xl bg-red-50 border border-red-200 p-3">
                  <p className="text-xs font-semibold text-red-800 mb-1 flex items-center gap-1.5"><ShieldAlert className="size-3.5" /> Bẫy cần tránh</p>
                  <div className="text-xs text-red-700 prose prose-sm max-w-none">
                    <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{s.traps}</Markdown>
                  </div>
                </div>
              )}
              {s.tips && (
                <div className="rounded-xl bg-white border border-blue-200 p-3">
                  <p className="text-xs font-semibold text-blue-800 mb-1">💡 Mẹo giải nhanh</p>
                  <div className="text-xs text-slate-700 prose prose-sm max-w-none">
                    <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{s.tips}</Markdown>
                  </div>
                </div>
              )}
              {s.crawled_solutions.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 mb-1.5 flex items-center gap-1.5">
                    <ExternalLink className="size-3.5" /> Lời giải tham khảo
                  </p>
                  <div className="space-y-1.5">
                    {s.crawled_solutions.map((sol) => (
                      <a key={sol.url} href={sol.url} target="_blank" rel="noopener noreferrer"
                        className="flex items-start gap-2 rounded-lg bg-white border border-blue-200 px-3 py-2 text-xs hover:border-blue-400 transition-all group">
                        <ExternalLink className="size-3.5 shrink-0 mt-0.5 text-blue-500" />
                        <div className="min-w-0">
                          <p className="font-medium group-hover:underline truncate text-blue-900">{sol.title}</p>
                          {sol.snippet && <p className="text-slate-500 line-clamp-1 mt-0.5">{sol.snippet}</p>}
                        </div>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Level 3: Không biết làm → Lộ trình */}
      {level3.length > 0 && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
          <div className="flex items-center gap-2 mb-3">
            <div className="size-8 rounded-full bg-red-100 flex items-center justify-center">
              <AlertCircle className="size-4 text-red-600" />
            </div>
            <h3 className="font-bold text-slate-800">Không biết làm — Cần học lại</h3>
            <span className="ml-auto text-xs bg-red-100 text-red-700 rounded-full px-2 py-0.5 font-medium">{level3.length} câu</span>
          </div>
          <div className="space-y-2 mb-4">
            {level3.map((s) => (
              <div key={s.question_id} className="bg-white rounded-xl border border-red-200 p-3">
                <p className="text-xs font-bold text-red-800 mb-1">{s.question_id}</p>
                <div className="text-xs text-slate-600 prose prose-sm max-w-none">
                  <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{s.question_content}</Markdown>
                </div>
                {s.hint && (
                  <div className="mt-3 rounded-xl bg-red-50 border border-red-200 p-3">
                    <p className="text-xs font-semibold text-red-800 mb-1">💡 Lời khuyên & Đánh giá</p>
                    <div className="text-xs text-slate-700 prose prose-sm max-w-none">
                      <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{s.hint}</Markdown>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
          {hasRoadmap && (
            <div className="mt-4">
              <p className="text-sm font-semibold text-red-800 mb-3">📚 Lộ trình học lại được tạo riêng cho bạn:</p>
              <RoadmapInlinePanel
                roadmap={result.roadmap!}
                phaseResources={result.phase_resources ?? {}}
                subject={subject}
                goal="Nắm vững kiến thức còn yếu"
              />
            </div>
          )}
        </div>
      )}

      {/* Crawled Resources (Global) */}
      {result.resources && <GlobalResourcesPanel res={result.resources} />}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Subject List (màn đầu luồng 1)
// ──────────────────────────────────────────────────────────────────────────
function SubjectListScreen({
  mode,
  onNew,
  onBack,
  onViewSubject,
}: {
  mode: "onboarding" | "post_exam";
  onNew: () => void;
  onBack: () => void;
  onViewSubject: (subject: string) => void;
}) {
  const [subjects, setSubjects] = useState<SubjectSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const color = mode === "onboarding" ? "indigo" : "emerald";

  useEffect(() => {
    setLoading(true);
    listSubjects(mode)
      .then(setSubjects)
      .catch(() => setSubjects([]))
      .finally(() => setLoading(false));
  }, [mode]);

  const title = mode === "onboarding" ? "Bắt đầu học mới" : "Cải thiện sau thi";
  const emptyText = mode === "onboarding"
    ? "Bạn chưa có môn học nào. Hãy thêm môn mới để bắt đầu!"
    : "Bạn chưa có bài kiểm tra nào. Hãy thêm để bắt đầu phân tích!";
  const itemLabel = mode === "onboarding" ? "môn học" : "bài kiểm tra";
  const newLabel = mode === "onboarding" ? "+ Thêm môn học mới" : "+ Thêm bài kiểm tra mới";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-slate-500 hover:text-slate-800 transition-colors p-1">
          <X className="size-5" />
        </button>
        <div className="flex-1">
          <h2 className="font-bold text-slate-900 text-xl">{title}</h2>
          <p className="text-sm text-slate-500">
            {mode === "onboarding"
              ? "Xem lại các môn đã học hoặc bắt đầu môn mới."
              : "Xem lại bài kiểm tra cũ hoặc thêm bài mới để phân tích."}
          </p>
        </div>
      </div>

      <button
        onClick={onNew}
        className={`w-full flex items-center gap-3 rounded-2xl border-2 border-dashed border-${color}-300 bg-${color}-50 p-5 text-left hover:border-${color}-500 hover:bg-${color}-100 transition-all group`}
      >
        <div className={`size-10 rounded-xl bg-${color}-100 group-hover:bg-${color}-200 flex items-center justify-center transition-colors`}>
          <Plus className={`size-5 text-${color}-600`} />
        </div>
        <span className={`font-semibold text-${color}-700 text-sm`}>{newLabel}</span>
        <ArrowRight className={`size-4 text-${color}-500 ml-auto`} />
      </button>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-slate-400 justify-center py-8">
          <Loader2 className="size-4 animate-spin" /> Đang tải...
        </div>
      ) : subjects.length === 0 ? (
        <div className="text-center py-12">
          <History className="size-10 mx-auto text-slate-300 mb-3" />
          <p className="text-slate-500 text-sm">{emptyText}</p>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            {subjects.length} {itemLabel} đã lưu
          </p>
          {subjects.map((s) => (
            <button
              key={s.subject}
              onClick={() => onViewSubject(s.subject)}
              className="w-full flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 text-left hover:border-indigo-300 hover:shadow-md transition-all group"
            >
              <div className={`size-10 rounded-xl bg-${color}-50 flex items-center justify-center shrink-0`}>
                {mode === "onboarding" ? (
                  <BookOpen className={`size-5 text-${color}-600`} />
                ) : (
                  <Trophy className={`size-5 text-${color}-600`} />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-slate-800 truncate">{s.subject}</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {s.count} lần · {new Date(s.last_used).toLocaleDateString("vi-VN")}
                </p>
              </div>
              <ChevronRight className="size-4 text-slate-400 group-hover:text-indigo-500 transition-colors shrink-0" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Subject Detail (danh sách analyses của 1 môn)
// ──────────────────────────────────────────────────────────────────────────
function SubjectDetailScreen({
  subject,
  mode,
  onBack,
  onViewAnalysis,
}: {
  subject: string;
  mode: "onboarding" | "post_exam";
  onBack: () => void;
  onViewAnalysis: (a: ExamAnalysisSummary) => void;
}) {
  const [analyses, setAnalyses] = useState<ExamAnalysisSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const color = mode === "onboarding" ? "indigo" : "emerald";

  useEffect(() => {
    setLoading(true);
    listAnalysesBySubject(subject)
      .then(setAnalyses)
      .catch(() => setAnalyses([]))
      .finally(() => setLoading(false));
  }, [subject]);

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-slate-500 hover:text-slate-800 transition-colors p-1">
          <X className="size-5" />
        </button>
        <div>
          <h2 className="font-bold text-slate-900 text-xl">{subject}</h2>
          <p className="text-sm text-slate-500">Lịch sử phân tích</p>
        </div>
      </div>
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-slate-400 justify-center py-8">
          <Loader2 className="size-4 animate-spin" /> Đang tải...
        </div>
      ) : (
        <div className="space-y-3">
          {analyses.map((a) => (
            <button
              key={a.id}
              onClick={() => onViewAnalysis(a)}
              className="w-full flex items-center gap-4 rounded-xl border border-slate-200 bg-white p-4 text-left hover:border-indigo-300 hover:shadow transition-all group"
            >
              <FileText className={`size-5 text-${color}-500 shrink-0`} />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-slate-800 truncate text-sm">{a.filename}</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {new Date(a.created_at).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })}
                  {" · "}{a.mastery_updates_count} mastery cập nhật
                </p>
              </div>
              <ChevronRight className="size-4 text-slate-400 group-hover:text-indigo-500 shrink-0" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Main Page
// ──────────────────────────────────────────────────────────────────────────
export function PersonalizedLearningPage({ mode }: { mode: "onboarding" | "post_exam" }) {
  return (
    <div className="space-y-6">
      {mode === "onboarding" && <OnboardingFlow />}
      {mode === "post_exam" && <PostExamFlow />}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Flow 1: Onboarding (Bắt đầu học mới)
// ──────────────────────────────────────────────────────────────────────────
function OnboardingFlow() {
  const [screen, setScreen] = useState<OnboardingScreen>("subject_list");
  const [viewingSubject, setViewingSubject] = useState<string | null>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [analysis, setAnalysis] = useState<DocumentAnalysisResult | null>(null);
  const [selectedGoal, setSelectedGoal] = useState<string>("");
  const [customGoal, setCustomGoal] = useState<string>("");
  const [quiz, setQuiz] = useState<QuizQuestion[]>([]);
  const [topicSummary, setTopicSummary] = useState("");
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [quizAnswers, setQuizAnswers] = useState<QuizAnswer[]>([]);
  const [finalResult, setFinalResult] = useState<ExamAnalysisDetail | null>(null);

  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("");
  const [error, setError] = useState("");
  const [showLevelWarning, setShowLevelWarning] = useState(false);
  const [showMultiSubjectWarning, setShowMultiSubjectWarning] = useState(false);
  const [showMasteryWarning, setShowMasteryWarning] = useState(false);
  const [showDuplicateRoadmapWarning, setShowDuplicateRoadmapWarning] = useState(false);
  const [showDuplicateFileWarning, setShowDuplicateFileWarning] = useState(false);

  // Progress calculation
  const progressMap: Record<OnboardingScreen, number> = {
    subject_list: 0,
    upload_and_info: 20,
    goal_selection: 50,
    quiz: 75,
    result: 100,
  };
  const progress = progressMap[screen];

  const effectiveGoal = customGoal.trim() || selectedGoal;

  // ─── Handlers ───
  async function handleAnalyzeDocument() {
    if (files.length === 0) { setError("Vui lòng chọn ít nhất 1 file tài liệu."); return; }
    setError("");
    setLoading(true);
    setLoadingMsg("Đang đọc và phân tích tài liệu...");
    try {
      const result = await analyzeDocument(files.length === 1 ? files[0] : files);
      if (!result.is_learning_doc) {
        setError(result.not_learning_message || "Tài liệu này không phải tài liệu học tập.");
        return;
      }
      setAnalysis(result);

      // Kiểm tra thứ tự ưu tiên: duplicate_file > multi-subject > level warning > mastery > duplicate roadmap
      if (result.duplicate_file) {
        setShowDuplicateFileWarning(true);
      } else if (result.multi_subject_detected) {
        setShowMultiSubjectWarning(true);
      } else if (result.level_gap === "exceeds_user") {
        setShowLevelWarning(true);
      } else if (result.has_existing_mastery) {
        if (result.existing_roadmap_title) {
          setShowDuplicateRoadmapWarning(true);
        } else {
          setShowMasteryWarning(true);
        }
      } else {
        setScreen("goal_selection");
      }
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
      setLoadingMsg("");
    }
  }

  async function handleGenerateQuiz() {
    if (!effectiveGoal) { setError("Vui lòng chọn hoặc nhập mục tiêu học tập."); return; }
    if (!analysis) return;
    setError("");
    setLoading(true);
    setLoadingMsg("Đang sinh câu hỏi kiểm tra từ nội dung tài liệu...");
    try {
      const result = await generateQuiz({
        subject: analysis.subject,
        document_text: analysis.raw_text,
        selected_goal: effectiveGoal,
        num_questions: 7,
      });
      setQuiz(result.quiz);
      setTopicSummary(result.topic_summary);
      setScreen("quiz");
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
      setLoadingMsg("");
    }
  }

  async function handleSubmitQuiz() {
    if (!files.length || !analysis) return;
    const computed: QuizAnswer[] = quiz.map((q) => ({
      questionId: q.id,
      selectedOption: answers[q.id] ?? "",
      correct: (answers[q.id] ?? "") === q.correct,
      topic: q.topic,
      difficulty: q.difficulty,
    }));
    setQuizAnswers(computed);
    setQuizSubmitted(true);
    setLoading(true);
    setLoadingMsg("Đang phân tích kết quả và sinh lộ trình học tập...");
    try {
      const quizResultsJson = JSON.stringify(
        computed.map((a) => ({ topic: a.topic, correct: a.correct, difficulty: a.difficulty }))
      );
      const data = await submitExam(files[0], {
        mode: "onboarding",
        selectedGoal: effectiveGoal,
        subject: analysis.subject,
        quickQuizResults: quizResultsJson,
        rawTextForCrawl: analysis.raw_text.slice(0, 800),
        isCodeRelated: analysis.is_code_related,
        documentContent: analysis.document_content,
      });
      setFinalResult(data);
      setScreen("result");
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
      setLoadingMsg("");
    }
  }

  const quizScore = quizAnswers.length > 0
    ? Math.round((quizAnswers.filter((a) => a.correct).length / quizAnswers.length) * 100)
    : 0;

  async function handleViewAnalysis(id: string) {
    setLoading(true);
    setLoadingMsg("Đang tải dữ liệu lịch sử...");
    setError("");
    try {
      const detail = await getExamAnalysis(id);
      setFinalResult(detail);
      setScreen("result");
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
      setLoadingMsg("");
    }
  }

  // ─── Screens ───
  if (screen === "subject_list") {
    if (viewingSubject) {
      return (
        <SubjectDetailScreen
          subject={viewingSubject}
          mode="onboarding"
          onBack={() => setViewingSubject(null)}
          onViewAnalysis={(a) => handleViewAnalysis(a.id)}
        />
      );
    }
    return (
      <SubjectListScreen
        mode="onboarding"
        onNew={() => setScreen("upload_and_info")}
        onBack={() => {}}
        onViewSubject={(s) => setViewingSubject(s)}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => {
            if (screen === "upload_and_info") setScreen("subject_list");
            else if (screen === "goal_selection") setScreen("upload_and_info");
            else if (screen === "quiz") setScreen("goal_selection");
            else if (screen === "result") setScreen("subject_list");
          }}
          className="text-slate-500 hover:text-slate-800 transition-colors p-1"
        >
          <X className="size-5" />
        </button>
        <div>
          <h2 className="font-bold text-slate-900 text-xl">Bắt đầu học mới</h2>
          <p className="text-sm text-slate-500">Hệ thống sẽ phân tích tài liệu và cá nhân hóa lộ trình cho bạn.</p>
        </div>
      </div>

      <ProgressBar progress={progress} label="Tiến độ tạo lộ trình" />

      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 max-w-2xl mx-auto">
          <AlertCircle className="size-4 shrink-0 mt-0.5 text-red-500" />
          <p>{error}</p>
          <button onClick={() => setError("")} className="ml-auto shrink-0 text-red-400 hover:text-red-700">
            <X className="size-4" />
          </button>
        </div>
      )}

      {/* Step 1: Upload */}
      {screen === "upload_and_info" && (
        <div className="max-w-xl mx-auto space-y-5">
          <MultiDropZone
            files={files}
            onFiles={(newFiles) => { setFiles((prev) => [...prev, ...newFiles]); setError(""); }}
            onRemove={(i) => setFiles((prev) => prev.filter((_, idx) => idx !== i))}
          />
          <Button className="w-full" onClick={handleAnalyzeDocument} isLoading={loading} disabled={files.length === 0}>
            {loading ? loadingMsg : <><BrainCircuit className="size-4" /> Phân tích tài liệu</>}
          </Button>
          {files.length === 0 && <p className="text-xs text-slate-400 text-center">Chọn file tài liệu học trước khi tiếp tục</p>}
        </div>
      )}

      {/* Modal: Duplicate file warning */}
      {showDuplicateFileWarning && analysis && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm px-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-4 flex items-center gap-3 text-indigo-600">
              <div className="flex size-10 items-center justify-center rounded-full bg-indigo-100">
                <FileText className="size-5" />
              </div>
              <h3 className="font-bold text-lg text-slate-900">Tài liệu đã tồn tại</h3>
            </div>
            <p className="text-slate-600 text-sm mb-6 leading-relaxed">
              Bạn đã từng tải tài liệu này lên hệ thống (môn <strong>{analysis.duplicate_subject}</strong> lúc {analysis.duplicate_created_at ? new Date(analysis.duplicate_created_at).toLocaleDateString("vi-VN") : "trước đây"}). 
              Bạn có muốn xem lại phân tích cũ để tránh tốn bộ nhớ vô ích, hay muốn phân tích lại từ đầu?
            </p>
            <div className="flex gap-3 justify-end">
              <Button variant="secondary" onClick={() => { 
                setShowDuplicateFileWarning(false); 
                if (analysis.existing_analysis_id) {
                  handleViewAnalysis(analysis.existing_analysis_id);
                } else {
                  setScreen("subject_list");
                }
              }}>
                Xem phân tích cũ
              </Button>
              <Button onClick={() => { setShowDuplicateFileWarning(false); setScreen("goal_selection"); }}>
                Phân tích lại
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Multi-subject warning */}
      {showMultiSubjectWarning && analysis && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm px-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-4 flex items-center gap-3 text-indigo-600">
              <div className="flex size-10 items-center justify-center rounded-full bg-indigo-100">
                <BrainCircuit className="size-5" />
              </div>
              <h3 className="font-bold text-lg text-slate-900">Phát hiện nhiều môn học</h3>
            </div>
            <p className="text-slate-600 text-sm mb-2 leading-relaxed">
              Hệ thống phát hiện các file bạn upload thuộc <strong>{analysis.subjects.length} môn khác nhau</strong>:
            </p>
            <div className="flex flex-wrap gap-2 mb-4">
              {analysis.subjects.map((s) => (
                <span key={s} className="text-xs bg-indigo-50 text-indigo-700 rounded-full px-3 py-1 font-medium border border-indigo-200">{s}</span>
              ))}
            </div>
            <p className="text-slate-600 text-sm mb-6">Bạn có muốn học tất cả các môn này cùng lúc không?</p>
            <div className="flex gap-3 justify-end">
              <Button variant="secondary" onClick={() => { setShowMultiSubjectWarning(false); setFiles([]); setAnalysis(null); }}>
                Không — Upload lại
              </Button>
              <Button onClick={() => { setShowMultiSubjectWarning(false); setScreen("goal_selection"); }}>
                Có, học cả {analysis.subjects.length} môn
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Level warning */}
      {showLevelWarning && analysis && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm px-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-4 flex items-center gap-3 text-amber-600">
              <div className="flex size-10 items-center justify-center rounded-full bg-amber-100">
                <AlertCircle className="size-5" />
              </div>
              <h3 className="font-bold text-lg text-slate-900">Cảnh báo Trình độ</h3>
            </div>
            <p className="text-slate-600 text-sm mb-6 leading-relaxed">
              {analysis.warning_message || "Tài liệu này có vẻ vượt quá trình độ hiện tại của bạn. Bạn có muốn thử thách bản thân và tiếp tục không?"}
            </p>
            <div className="flex gap-3 justify-end">
              <Button variant="secondary" onClick={() => { setShowLevelWarning(false); setFiles([]); }}>Hủy bỏ</Button>
              <Button onClick={() => { setShowLevelWarning(false); setScreen("goal_selection"); }}>Vẫn tiếp tục</Button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Existing mastery */}
      {showMasteryWarning && analysis && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm px-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-4 flex items-center gap-3 text-indigo-600">
              <div className="flex size-10 items-center justify-center rounded-full bg-indigo-100">
                <BookOpen className="size-5" />
              </div>
              <h3 className="font-bold text-lg text-slate-900">Môn này bạn đã từng học</h3>
            </div>
            <p className="text-slate-600 text-sm mb-2 leading-relaxed">
              Bạn đang tải một <strong>tài liệu mới</strong> thuộc môn <strong>{analysis.subject}</strong> — một môn bạn đã từng học và có dữ liệu năng lực.
            </p>
            <p className="text-slate-500 text-xs mb-6 leading-relaxed bg-indigo-50 border border-indigo-100 rounded-lg p-3">
              💡 Lưu ý: Tài liệu mới này có nội dung khác với tài liệu cũ. Nếu tiếp tục, hệ thống sẽ tạo thêm một bản phân tích mới cho cùng môn này dựa trên nội dung tài liệu mới.
            </p>
            <div className="flex gap-3 justify-end">
              <Button variant="secondary" onClick={() => { setShowMasteryWarning(false); setScreen("subject_list"); }}>
                Xem lại lịch sử cũ
              </Button>
              <Button onClick={() => { setShowMasteryWarning(false); setScreen("goal_selection"); }}>
                Tiếp tục với tài liệu mới
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Duplicate roadmap warning */}
      {showDuplicateRoadmapWarning && analysis && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm px-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-4 flex items-center gap-3 text-amber-600">
              <div className="flex size-10 items-center justify-center rounded-full bg-amber-100">
                <AlertCircle className="size-5" />
              </div>
              <h3 className="font-bold text-lg text-slate-900">Bạn đang có lộ trình dang dở</h3>
            </div>
            <p className="text-slate-600 text-sm mb-2 leading-relaxed">
              Bạn đang tải một <strong>tài liệu mới</strong> thuộc môn <strong>{analysis.subject}</strong>, nhưng bạn đang có lộ trình học chưa hoàn thành: <strong>"{analysis.existing_roadmap_title}"</strong>.
            </p>
            <p className="text-slate-500 text-xs mb-6 leading-relaxed bg-amber-50 border border-amber-100 rounded-lg p-3">
              ⚠️ Nếu tạo lộ trình mới từ tài liệu này, lộ trình cũ vẫn được giữ nguyên trong lịch sử nhưng bạn sẽ phải quản lý hai lộ trình song song cho cùng một môn.
            </p>
            <div className="flex gap-3 justify-end">
              <Button variant="secondary" onClick={() => { setShowDuplicateRoadmapWarning(false); setScreen("subject_list"); }}>
                Quay lại — Tiếp tục lộ trình cũ
              </Button>
              <Button onClick={() => { setShowDuplicateRoadmapWarning(false); setScreen("goal_selection"); }}>
                Tạo lộ trình mới từ tài liệu này
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Step 2: Goal selection */}
      {screen === "goal_selection" && analysis && (
        <div className="max-w-xl mx-auto space-y-5">
          <div className="rounded-xl bg-indigo-50 border border-indigo-200 p-4">
            <div className="flex items-center gap-2 mb-1">
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold bg-indigo-600 text-white rounded-full px-2.5 py-1">
                <CheckCircle2 className="size-3" /> Đã nhận diện
              </span>
              <span className="text-sm font-bold text-indigo-900">{analysis.subject}</span>
            </div>
            {analysis.content_summary && <p className="text-sm text-indigo-700 mt-1">{analysis.content_summary}</p>}
            {analysis.topics.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {analysis.topics.slice(0, 5).map((t) => (
                  <span key={t} className="text-xs rounded-full bg-indigo-100 text-indigo-700 px-2 py-0.5">{t}</span>
                ))}
              </div>
            )}
          </div>

          {analysis.document_content?.blocks?.length > 0 && (
            <DocumentReader content={analysis.document_content} compact />
          )}

          <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
            <div className="flex items-center gap-2">
              <Target className="size-4 text-indigo-600" />
              <h3 className="font-semibold text-slate-800">Mục tiêu học tập của bạn là gì?</h3>
            </div>

            <div className="grid gap-2 sm:grid-cols-2">
              {analysis.suggested_goals.map((goal) => {
                const isDisabled = customGoal.trim().length > 0;
                const isSelected = selectedGoal === goal && !isDisabled;
                return (
                  <button
                    key={goal}
                    onClick={() => { if (!isDisabled) setSelectedGoal(goal); }}
                    disabled={isDisabled}
                    className={`text-left rounded-xl border-2 px-3 py-2.5 text-sm transition-all
                      ${isSelected ? "border-indigo-500 bg-indigo-50 text-indigo-800 font-medium" : ""}
                      ${isDisabled ? "opacity-40 cursor-not-allowed border-slate-200" : "border-slate-200 hover:border-indigo-300 hover:bg-slate-50"}`}
                  >
                    <span className={`inline-block size-3.5 rounded-full border-2 mr-2 align-middle
                      ${isSelected ? "border-indigo-500 bg-indigo-500" : "border-slate-300"}`} />
                    {goal}
                  </button>
                );
              })}
            </div>

            <div className="relative">
              <div className="flex items-center gap-2 mb-1.5">
                <div className="h-px flex-1 bg-slate-200" />
                <span className="text-xs text-slate-400 shrink-0">hoặc nhập mục tiêu khác</span>
                <div className="h-px flex-1 bg-slate-200" />
              </div>
              <input
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 transition-all"
                placeholder="VD: Ôn lại toàn bộ để bảo vệ luận văn..."
                value={customGoal}
                onChange={(e) => { setCustomGoal(e.target.value); if (e.target.value) setSelectedGoal(""); }}
              />
              {customGoal && <p className="text-xs text-indigo-600 mt-1">✓ Đang dùng mục tiêu tùy chỉnh</p>}
            </div>
          </div>

          <div className="flex gap-3">
            <Button variant="secondary" onClick={() => setScreen("upload_and_info")}>Quay lại</Button>
            <Button onClick={handleGenerateQuiz} isLoading={loading} className="flex-1" disabled={!effectiveGoal}>
              {loading ? loadingMsg : <><BrainCircuit className="size-4" /> Tạo bài kiểm tra nhanh</>}
            </Button>
          </div>
          {!effectiveGoal && <p className="text-xs text-slate-400 text-center">Chọn hoặc nhập mục tiêu để tiếp tục</p>}
        </div>
      )}

      {/* Step 3: Quiz */}
      {screen === "quiz" && (
        <div className="max-w-2xl mx-auto space-y-4">
          {topicSummary && (
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 text-sm text-slate-700">
              <span className="font-semibold text-slate-800">📚 Phạm vi kiểm tra: </span>{topicSummary}
            </div>
          )}
          <p className="text-sm text-slate-500">Hãy trả lời {quiz.length} câu hỏi dưới đây (bám sát nội dung tài liệu đã tải lên).</p>

          {!quizSubmitted ? (
            <div className="space-y-4">
              {quiz.map((q, i) => (
                <div key={q.id} className="rounded-xl border border-slate-200 bg-white p-5">
                  <div className="font-semibold text-slate-800 mb-3 text-sm flex gap-2">
                    <span className="inline-flex size-6 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold items-center justify-center shrink-0">{i + 1}</span>
                    <div className="mt-0.5"><Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{q.question}</Markdown></div>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {(["A", "B", "C", "D"] as const).map((key) => (
                      <button
                        key={key}
                        onClick={() => setAnswers((prev) => ({ ...prev, [q.id]: key }))}
                        className={`text-left rounded-lg border px-3 py-2.5 text-sm transition-all
                          ${answers[q.id] === key ? "border-indigo-400 bg-indigo-50 text-indigo-800 font-medium" : "border-slate-200 hover:border-indigo-200"}`}
                      >
                        <span className="font-semibold mr-1 shrink-0">{key}.</span>
                        <div className="inline-block align-top break-words">
                          <Markdown components={{ p: 'span' }} remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{q.options[key]}</Markdown>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
              <Button onClick={handleSubmitQuiz} className="w-full" disabled={Object.keys(answers).length < quiz.length}>
                <Trophy className="size-4" /> Nộp bài
              </Button>
              {Object.keys(answers).length < quiz.length && (
                <p className="text-xs text-slate-400 text-center">
                  Còn {quiz.length - Object.keys(answers).length} câu chưa chọn đáp án
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5 text-center">
                <p className="text-4xl font-black text-emerald-700">{quizScore}%</p>
                <p className="text-emerald-800 font-semibold mt-1">{quizAnswers.filter((a) => a.correct).length}/{quiz.length} câu đúng</p>
                <p className="text-sm text-emerald-600 mt-1">
                  {quizScore >= 70 ? "Bạn có nền tảng tốt!" : quizScore >= 40 ? "Cần ôn lại một số phần." : "Hệ thống sẽ tạo lộ trình từ đầu cho bạn."}
                </p>
              </div>
              {quiz.map((q, i) => {
                const ans = quizAnswers[i];
                return (
                  <div key={q.id} className={`rounded-xl border p-4 text-sm ${ans?.correct ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50"}`}>
                    <div className="font-semibold text-slate-800 flex gap-1">
                      <span>{i + 1}.</span>
                      <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{q.question}</Markdown>
                    </div>
                    <div className={`mt-1 font-medium ${ans?.correct ? "text-emerald-700" : "text-red-700"}`}>
                      {ans?.correct ? "✓ Đúng" : (
                        <div className="flex gap-1">
                          <span>✗ Sai — Đáp án: {q.correct}.</span>
                          <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{q.options[q.correct as keyof typeof q.options]}</Markdown>
                        </div>
                      )}
                    </div>
                    {!ans?.correct && (
                      <div className="text-slate-600 mt-0.5 text-xs italic">
                        <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{q.explanation}</Markdown>
                      </div>
                    )}
                  </div>
                );
              })}
              {loading && (
                <div className="flex items-center gap-2 text-sm text-slate-500 justify-center">
                  <Loader2 className="size-4 animate-spin" /> {loadingMsg}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Step 4: Result */}
      {screen === "result" && finalResult && <ResultPanel result={finalResult} />}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Flow 2: Post-Exam (Cải thiện sau thi)
// ──────────────────────────────────────────────────────────────────────────
function PostExamFlow() {
  const [screen, setScreen] = useState<PostExamScreen>("exam_list");
  const [viewingSubject, setViewingSubject] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [score, setScore] = useState("");
  const [maxScore, setMaxScore] = useState("10");
  const [parsedExam, setParsedExam] = useState<ParseExamResponse | null>(null);
  const [selectedQuestions, setSelectedQuestions] = useState<string[]>([]);
  const [supportLevels, setSupportLevels] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ExamAnalysisDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Progress
  const progressMap: Record<PostExamScreen, number> = {
    exam_list: 0,
    upload: 20,
    select_and_score: 60,
    result: 100,
  };
  const progress = progressMap[screen];

  const supportOptions = [
    "Không biết làm",
    "Hiểu đề nhưng không biết bắt đầu từ đâu",
    "Sắp làm được rồi nhưng vẫn còn thiếu một chút",
  ];

  async function handleParse() {
    if (!file) { setError("Vui lòng chọn file đề thi."); return; }
    setLoading(true);
    setError("");
    try {
      const data = await parseExamDocument(file);
      setParsedExam(data);
      setScreen("select_and_score");
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleAnalyze() {
    if (!parsedExam) return;
    if (selectedQuestions.some((q) => !supportLevels[q])) {
      setError("Vui lòng chọn mức độ hỗ trợ cho tất cả các câu đã chọn.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const questionsPayload = selectedQuestions.map((qId) => {
        const qData = parsedExam.questions.find((q) => q.id === qId);
        return {
          id: qId,
          content: qData?.content || "",
          level: supportLevels[qId] || "Không biết làm",
        };
      });

      const data = await submitExam(file!, {
        mode: "post_exam",
        examScore: score || undefined,
        examMaxScore: maxScore || undefined,
        selectedQuestions: JSON.stringify(questionsPayload),
        rawText: parsedExam.raw_markdown,
      });
      setResult(data);
      setScreen("result");
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  const toggleQuestion = (id: string) => {
    setSelectedQuestions((prev) =>
      prev.includes(id) ? prev.filter((q) => q !== id) : [...prev, id]
    );
  };

  async function handleViewAnalysis(id: string) {
    setLoading(true);
    setError("");
    try {
      const detail = await getExamAnalysis(id);
      setResult(detail);
      setScreen("result");
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  // ─── Screens ───
  if (screen === "exam_list") {
    if (viewingSubject) {
      return (
        <SubjectDetailScreen
          subject={viewingSubject}
          mode="post_exam"
          onBack={() => setViewingSubject(null)}
          onViewAnalysis={(a) => handleViewAnalysis(a.id)}
        />
      );
    }
    return (
      <SubjectListScreen
        mode="post_exam"
        onNew={() => setScreen("upload")}
        onBack={() => {}}
        onViewSubject={(s) => setViewingSubject(s)}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => {
            if (screen === "upload") setScreen("exam_list");
            else if (screen === "select_and_score") setScreen("upload");
            else if (screen === "result") setScreen("exam_list");
          }}
          className="text-slate-500 hover:text-slate-800 transition-colors p-1"
        >
          <X className="size-5" />
        </button>
        <div>
          <h2 className="font-bold text-slate-900 text-xl">Cải thiện sau thi</h2>
          <p className="text-sm text-slate-500">Phân tích điểm yếu từ bài thi và xây dựng lộ trình ôn luyện.</p>
        </div>
      </div>

      <ProgressBar progress={progress} label="Tiến độ phân tích bài thi" />

      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 max-w-2xl mx-auto">
          <AlertCircle className="size-4 shrink-0 mt-0.5 text-red-500" />
          <p>{error}</p>
          <button onClick={() => setError("")} className="ml-auto shrink-0 text-red-400 hover:text-red-700">
            <X className="size-4" />
          </button>
        </div>
      )}

      {/* Step 1: Upload */}
      {screen === "upload" && (
        <div className="max-w-xl mx-auto space-y-4">
          <p className="text-slate-600 text-sm">Upload file đề thi hoặc bài kiểm tra bạn đã làm (ảnh scan, PDF, DOCX...).</p>
          <DropZone file={file} onFile={setFile} onClear={() => setFile(null)} accent="emerald" />
          <Button className="w-full" onClick={handleParse} isLoading={loading} disabled={!file}>
            {loading ? "Đang xử lý tài liệu..." : <><ChevronRight className="size-4" /> Tiếp theo</>}
          </Button>
        </div>
      )}

      {/* Step 2: Chọn câu hỏi + mức độ + điểm số (gộp) */}
      {screen === "select_and_score" && parsedExam && (
        <div className="max-w-3xl mx-auto space-y-6">
          {/* Điểm số — ở đầu trang */}
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5">
            <h3 className="font-bold text-slate-800 text-base mb-4 flex items-center gap-2">
              <Trophy className="size-4 text-emerald-600" /> Điểm số bài làm
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="text-sm font-semibold text-slate-700">Điểm của bạn</span>
                <input type="number" min="0" step="0.5"
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                  placeholder="VD: 6.5" value={score} onChange={(e) => setScore(e.target.value)} />
              </label>
              <label className="block">
                <span className="text-sm font-semibold text-slate-700">Thang điểm</span>
                <input type="number" min="1"
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                  placeholder="VD: 10" value={maxScore} onChange={(e) => setMaxScore(e.target.value)} />
              </label>
            </div>
          </div>

          {/* Câu hỏi */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
            <h3 className="font-bold text-slate-800 text-lg">Chọn câu hỏi cần hỗ trợ</h3>
            <p className="text-sm text-slate-500">
              Hãy chọn những câu bạn làm sai hoặc không chắc chắn, rồi cho biết bạn đang gặp khó khăn ở mức độ nào.
            </p>

            {parsedExam.header && parsedExam.header.trim().length > 0 && (
              <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 text-sm mb-4">
                <p className="font-semibold text-slate-700 mb-2">Đoạn văn / Dữ kiện chung:</p>
                <div className="prose prose-sm max-w-none text-slate-600">
                  <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{parsedExam.header}</Markdown>
                </div>
              </div>
            )}

            <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-2">
              {parsedExam.questions.map((q) => {
                const isSelected = selectedQuestions.includes(q.id);
                return (
                  <div key={q.id} className={`rounded-xl border transition-colors ${isSelected ? "border-emerald-400 bg-emerald-50" : "border-slate-200 bg-white"}`}>
                    {/* Câu hỏi header */}
                    <div
                      className="flex items-start gap-3 p-4 cursor-pointer"
                      onClick={() => toggleQuestion(q.id)}
                    >
                      <div className="mt-1 flex-shrink-0">
                        <div className={`w-5 h-5 rounded border flex items-center justify-center transition-colors ${isSelected ? "bg-emerald-500 border-emerald-500" : "border-slate-300"}`}>
                          {isSelected && <CheckCircle2 className="w-3.5 h-3.5 text-white" />}
                        </div>
                      </div>
                      <div className="flex-1 min-w-0 prose prose-sm max-w-none text-slate-800">
                        <p className="font-bold mb-1">{q.id}</p>
                        <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{q.content}</Markdown>
                      </div>
                    </div>

                    {/* Mức độ hỗ trợ — chỉ hiện khi chọn */}
                    {isSelected && (
                      <div className="px-4 pb-4 pt-0 border-t border-emerald-200">
                        <p className="text-xs font-semibold text-emerald-700 mb-2 mt-3">Bạn đang gặp khó khăn ở mức nào?</p>
                        <div className="space-y-1.5">
                          {supportOptions.map((opt) => (
                            <label
                              key={opt}
                              className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${supportLevels[q.id] === opt ? "border-emerald-500 bg-white shadow-sm ring-1 ring-emerald-500" : "border-slate-200 bg-white/50 hover:bg-white"}`}
                            >
                              <input
                                type="radio"
                                name={`level-${q.id}`}
                                className="text-emerald-600 focus:ring-emerald-500"
                                checked={supportLevels[q.id] === opt}
                                onChange={() => setSupportLevels((prev) => ({ ...prev, [q.id]: opt }))}
                              />
                              <span className="text-sm font-medium text-slate-700">{opt}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="flex gap-3">
            <Button variant="secondary" onClick={() => setScreen("upload")}>Quay lại</Button>
            <Button
              className="flex-1"
              onClick={handleAnalyze}
              isLoading={loading}
              disabled={selectedQuestions.length === 0 || selectedQuestions.some((q) => !supportLevels[q])}
            >
              {loading ? "Đang phân tích và sinh kết quả..." : <><BrainCircuit className="size-4" /> Phân tích AI</>}
            </Button>
          </div>
          {selectedQuestions.length === 0 && (
            <p className="text-xs text-slate-400 text-center">Chọn ít nhất 1 câu để tiếp tục</p>
          )}
        </div>
      )}

      {/* Step 3: Result */}
      {screen === "result" && result && <PostExamResultPanel result={result} />}
    </div>
  );
}
