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
  GraduationCap,
  Layers,
  Loader2,
  Mail,
  PlaySquare,
  Target,
  Trophy,
  Upload,
  X,
} from "lucide-react";
import { useCallback, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

import { getApiErrorMessage } from "../api/client";
import {
  analyzeDocument,
  generateQuiz,
  submitExam,
  type DocumentAnalysisResult,
  type ExamAnalysisDetail,
  type ExamRecommendation,
  type InlineRoadmap,
  type PhaseResources,
  type QuizQuestion,
} from "../api/exam";
import { Button, PageHeader } from "../components/ui";

// ──────────────────────────────────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────────────────────────────────
type Flow = "choose" | "onboarding" | "post_exam";
type OnboardingStep = "upload_and_info" | "goal_selection" | "quiz" | "result";
type PostExamStep = "upload" | "form" | "result";

interface QuizAnswer {
  questionId: number;
  selectedOption: string;
  correct: boolean;
  topic: string;
  difficulty: string;
}

// ──────────────────────────────────────────────────────────────────────────
// Shared Helper Components
// ──────────────────────────────────────────────────────────────────────────

function StepIndicator({ steps, current }: { steps: string[]; current: number }) {
  return (
    <div className="flex items-center mb-8 mx-auto max-w-2xl">
      {steps.map((label, i) => (
        <div key={label} className="flex items-center flex-1 last:flex-none">
          <div className="flex flex-col items-center">
            <div
              className={`size-8 rounded-full flex items-center justify-center text-sm font-bold transition-all
                ${i < current ? "bg-emerald-500 text-white" : i === current ? "bg-indigo-600 text-white ring-4 ring-indigo-100" : "bg-slate-200 text-slate-500"}`}
            >
              {i < current ? <CheckCircle2 className="size-4" /> : i + 1}
            </div>
            <span className={`mt-1 text-xs font-medium whitespace-nowrap ${i === current ? "text-indigo-700" : "text-slate-500"}`}>
              {label}
            </span>
          </div>
          {i < steps.length - 1 && (
            <div className={`h-0.5 flex-1 mx-2 mb-4 ${i < current ? "bg-emerald-400" : "bg-slate-200"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

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
  const color = accent === "indigo" ? "indigo" : "emerald";

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
                  <div key={q.id_cau} className="bg-white rounded-lg p-3 text-xs border border-white/60">
                    <p className="font-medium text-slate-800">{q.id_cau} — {q.kien_thuc_can_hoc}</p>
                    <p className="text-slate-600 mt-0.5">{q.loi_khuyen_ngan}</p>
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
// Inline Roadmap Panel
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

  // Build mailto email body
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

  // Build Google Calendar link for each phase
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
      {/* Header */}
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

        {/* Action buttons */}
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

      {/* Phases */}
      <div className="space-y-3">
        {roadmap.phases.map((phase, i) => {
          const c = phaseColors[i % phaseColors.length];
          const phaseKey = `phase_${phase.phase_number}`;
          const phaseRes = phaseResources[phaseKey];
          const isOpen = expandedPhase === i;

          return (
            <div key={phase.phase_number} className={`rounded-2xl border-2 ${c.border} ${c.bg} overflow-hidden transition-all`}>
              {/* Phase header */}
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

              {/* Phase detail */}
              {isOpen && (
                <div className="px-4 pb-4 space-y-4 border-t border-white/40 pt-3">
                  <div className="rounded-xl bg-white/70 p-3 text-sm">
                    <p className="font-semibold text-slate-800 mb-1 flex items-center gap-2">
                      <Target className="size-3.5 text-indigo-500" /> Mục tiêu
                    </p>
                    <p className="text-slate-700">{phase.goal}</p>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1.5">
                      <Layers className="size-3.5" /> Chủ đề cần học
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {phase.topics.map((t) => (
                        <span key={t} className="rounded-full bg-white border border-slate-200 px-2.5 py-0.5 text-xs font-medium text-slate-700">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-xl bg-white/70 p-3 text-sm">
                    <p className="font-semibold text-slate-800 mb-1">📅 Kế hoạch hàng ngày</p>
                    <p className="text-slate-700">{phase.daily_plan}</p>
                  </div>

                  <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3 text-sm">
                    <p className="font-semibold text-emerald-800 mb-0.5">🏁 Cột mốc</p>
                    <p className="text-emerald-700">{phase.milestone}</p>
                  </div>

                  {/* Per-phase resources */}
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
// Result Panel (wraps AI rec + roadmap)
// ──────────────────────────────────────────────────────────────────────────
function ResultPanel({ result }: { result: ExamAnalysisDetail }) {
  const [tab, setTab] = useState<"roadmap" | "rec">("roadmap");
  const hasRec = Object.keys(result.ai_recommendation).filter((k) => !k.startsWith("_")).length > 0;
  const hasRoadmap = result.roadmap && result.roadmap.phases?.length > 0;
  const subject = result.ai_recommendation?.["_goal"] ? result.filename.replace(/\.[^.]+$/, "") : "Học tập";
  const goal = (result.ai_recommendation?.["_goal"] as string) || "Nắm vững kiến thức";

  return (
    <div className="space-y-5 max-w-3xl mx-auto">
      {/* Score summary */}
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
            <p className="text-2xl font-black text-indigo-700">
              {result.exam_score}/{result.exam_max_score}
            </p>
          </div>
        )}
      </div>

      {/* Tabs */}
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
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Main Page
// ──────────────────────────────────────────────────────────────────────────
export function PersonalizedLearningPage() {
  const [flow, setFlow] = useState<Flow>("choose");

  return (
    <div className="space-y-6">
      {flow === "choose" && (
        <>
          <PageHeader
            title="Học tập cá nhân hóa"
            description="Chọn hướng phù hợp. Hệ thống sẽ phân tích tài liệu và tạo lộ trình riêng cho bạn."
          />
          <div className="grid gap-5 sm:grid-cols-2 max-w-2xl mx-auto">
            <button
              onClick={() => setFlow("onboarding")}
              className="group flex flex-col gap-4 rounded-2xl border-2 border-slate-200 bg-white p-6 text-left hover:border-indigo-400 hover:shadow-lg transition-all"
            >
              <div className="size-12 rounded-xl bg-indigo-100 flex items-center justify-center group-hover:bg-indigo-200 transition-colors">
                <GraduationCap className="size-6 text-indigo-600" />
              </div>
              <div>
                <h3 className="font-bold text-slate-900 text-lg">Bắt đầu học mới</h3>
                <p className="text-sm text-slate-500 mt-1">
                  Upload tài liệu. Hệ thống tự nhận diện môn học, gợi ý mục tiêu, kiểm tra năng lực và tạo lộ trình phù hợp.
                </p>
              </div>
              <span className="flex items-center gap-1 text-sm font-semibold text-indigo-600 mt-auto">
                Bắt đầu <ArrowRight className="size-4" />
              </span>
            </button>

            <button
              onClick={() => setFlow("post_exam")}
              className="group flex flex-col gap-4 rounded-2xl border-2 border-slate-200 bg-white p-6 text-left hover:border-emerald-400 hover:shadow-lg transition-all"
            >
              <div className="size-12 rounded-xl bg-emerald-100 flex items-center justify-center group-hover:bg-emerald-200 transition-colors">
                <Trophy className="size-6 text-emerald-600" />
              </div>
              <div>
                <h3 className="font-bold text-slate-900 text-lg">Cải thiện sau kỳ thi</h3>
                <p className="text-sm text-slate-500 mt-1">
                  Upload đề thi và điền điểm số. AI phân tích điểm yếu và đề xuất lộ trình cải thiện cụ thể.
                </p>
              </div>
              <span className="flex items-center gap-1 text-sm font-semibold text-emerald-600 mt-auto">
                Bắt đầu <ArrowRight className="size-4" />
              </span>
            </button>
          </div>
        </>
      )}
      {flow === "onboarding" && <OnboardingFlow onBack={() => setFlow("choose")} />}
      {flow === "post_exam" && <PostExamFlow onBack={() => setFlow("choose")} />}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Flow 1: Onboarding (4 bước gọn)
// ──────────────────────────────────────────────────────────────────────────
function OnboardingFlow({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<OnboardingStep>("upload_and_info");

  const [file, setFile] = useState<File | null>(null);

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

  const steps = ["Upload & Thông tin", "Chọn mục tiêu", "Bài kiểm tra nhanh", "Kết quả & Lộ trình"];
  const stepIndex = { upload_and_info: 0, goal_selection: 1, quiz: 2, result: 3 }[step];

  const effectiveGoal = customGoal.trim() || selectedGoal;

  async function handleAnalyzeDocument() {
    if (!file) { setError("Vui lòng chọn file tài liệu."); return; }
    setError("");
    setLoading(true);
    setLoadingMsg("Đang đọc và phân tích tài liệu...");
    try {
      const result = await analyzeDocument(file);
      if (!result.is_learning_doc) {
        setError(result.not_learning_message || "Tài liệu này không phải tài liệu học tập. Hãy thử file khác.");
        return;
      }
      setAnalysis(result);
      if (result.level_gap === "exceeds_user") {
        setShowLevelWarning(true);
      } else {
        setStep("goal_selection");
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
      setStep("quiz");
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
      setLoadingMsg("");
    }
  }

  async function handleSubmitQuiz() {
    if (!file || !analysis) return;
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
      const data = await submitExam(file, {
        mode: "onboarding",
        selectedGoal: effectiveGoal,
        subject: analysis.subject,
        quickQuizResults: quizResultsJson,
        rawTextForCrawl: analysis.raw_text.slice(0, 800),
        isCodeRelated: analysis.is_code_related,
      });
      setFinalResult(data);
      setStep("result");
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

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-slate-500 hover:text-slate-800 transition-colors p-1">
          <X className="size-5" />
        </button>
        <div>
          <h2 className="font-bold text-slate-900 text-xl">Bắt đầu học mới</h2>
          <p className="text-sm text-slate-500">Hệ thống sẽ phân tích tài liệu và cá nhân hóa lộ trình cho bạn.</p>
        </div>
      </div>

      <StepIndicator steps={steps} current={stepIndex} />

      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 max-w-2xl mx-auto">
          <AlertCircle className="size-4 shrink-0 mt-0.5 text-red-500" />
          <p>{error}</p>
          <button onClick={() => setError("")} className="ml-auto shrink-0 text-red-400 hover:text-red-700">
            <X className="size-4" />
          </button>
        </div>
      )}

      {/* Step 1: Upload + Info */}
      {step === "upload_and_info" && (
        <div className="max-w-xl mx-auto space-y-5">
          <DropZone file={file} onFile={(f) => { setFile(f); setError(""); }} onClear={() => setFile(null)} />

          <Button className="w-full" onClick={handleAnalyzeDocument} isLoading={loading} disabled={!file}>
            {loading ? loadingMsg : <><BrainCircuit className="size-4" /> Phân tích tài liệu</>}
          </Button>
          {!file && <p className="text-xs text-slate-400 text-center">Chọn file tài liệu học trước khi tiếp tục</p>}
        </div>
      )}

      {/* Warning Modal */}
      {showLevelWarning && analysis && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm px-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl animate-in zoom-in-95 fade-in">
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
              <Button
                variant="outline"
                onClick={() => {
                  setShowLevelWarning(false);
                  setFile(null); // Cancel and clear file
                }}
              >
                Hủy bỏ
              </Button>
              <Button
                onClick={() => {
                  setShowLevelWarning(false);
                  setStep("goal_selection"); // Proceed
                }}
              >
                Vẫn tiếp tục
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Step 2: Goal selection */}
      {step === "goal_selection" && analysis && (
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
                  <button key={goal} onClick={() => { if (!isDisabled) setSelectedGoal(goal); }}
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
            <Button variant="secondary" onClick={() => setStep("upload_and_info")}>Quay lại</Button>
            <Button onClick={handleGenerateQuiz} isLoading={loading} className="flex-1" disabled={!effectiveGoal}>
              {loading ? loadingMsg : <><BrainCircuit className="size-4" /> Tạo bài kiểm tra nhanh</>}
            </Button>
          </div>
          {!effectiveGoal && <p className="text-xs text-slate-400 text-center">Chọn hoặc nhập mục tiêu để tiếp tục</p>}
        </div>
      )}

      {/* Step 3: Quiz */}
      {step === "quiz" && (
        <div className="max-w-2xl mx-auto space-y-4">
          {topicSummary && (
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 text-sm text-slate-700">
              <span className="font-semibold text-slate-800">📚 Phạm vi kiểm tra: </span>{topicSummary}
            </div>
          )}
          <p className="text-sm text-slate-500">
            Hãy trả lời {quiz.length} câu hỏi dưới đây (bám sát nội dung tài liệu đã tải lên).
          </p>

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
                      <button key={key} onClick={() => setAnswers((prev) => ({ ...prev, [q.id]: key }))}
                        className={`text-left rounded-lg border px-3 py-2.5 text-sm transition-all
                          ${answers[q.id] === key ? "border-indigo-400 bg-indigo-50 text-indigo-800 font-medium" : "border-slate-200 hover:border-indigo-200"}`}>
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
                <p className="text-emerald-800 font-semibold mt-1">
                  {quizAnswers.filter((a) => a.correct).length}/{quiz.length} câu đúng
                </p>
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
      {step === "result" && finalResult && <ResultPanel result={finalResult} />}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Flow 2: Post-Exam
// ──────────────────────────────────────────────────────────────────────────
function PostExamFlow({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<PostExamStep>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [hasTaken, setHasTaken] = useState<"yes" | "no" | "">("");
  const [score, setScore] = useState("");
  const [maxScore, setMaxScore] = useState("10");
  const [weakAreas, setWeakAreas] = useState("");
  const [result, setResult] = useState<ExamAnalysisDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const steps = ["Upload đề thi", "Thông tin kết quả", "Phân tích & Lộ trình"];
  const stepIndex = { upload: 0, form: 1, result: 2 }[step];

  async function handleAnalyze() {
    if (!file) { setError("Vui lòng chọn file đề thi."); return; }
    if (!hasTaken) { setError("Vui lòng cho biết bạn đã thi chưa."); return; }
    setLoading(true);
    setError("");
    try {
      const data = await submitExam(file, {
        mode: "post_exam",
        examScore: hasTaken === "yes" && score ? score : undefined,
        examMaxScore: hasTaken === "yes" && maxScore ? maxScore : undefined,
        selfAssessedWeakAreas: weakAreas || undefined,
      });
      setResult(data);
      setStep("result");
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-slate-500 hover:text-slate-800 transition-colors p-1">
          <X className="size-5" />
        </button>
        <div>
          <h2 className="font-bold text-slate-900 text-xl">Cải thiện sau kỳ thi</h2>
          <p className="text-sm text-slate-500">Phân tích điểm yếu từ bài thi và xây dựng lộ trình ôn luyện.</p>
        </div>
      </div>

      <StepIndicator steps={steps} current={stepIndex} />

      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 max-w-2xl mx-auto">
          <AlertCircle className="size-4 shrink-0 mt-0.5 text-red-500" />
          <p>{error}</p>
          <button onClick={() => setError("")} className="ml-auto shrink-0 text-red-400 hover:text-red-700">
            <X className="size-4" />
          </button>
        </div>
      )}

      {step === "upload" && (
        <div className="max-w-xl mx-auto space-y-4">
          <p className="text-slate-600 text-sm">Upload file đề thi hoặc bài kiểm tra bạn đã làm (ảnh scan, PDF, DOCX...).</p>
          <DropZone file={file} onFile={setFile} onClear={() => setFile(null)} accent="emerald" />
          <Button className="w-full" onClick={() => setStep("form")} disabled={!file}>
            Tiếp theo <ChevronRight className="size-4" />
          </Button>
        </div>
      )}

      {step === "form" && (
        <div className="max-w-xl mx-auto space-y-5">
          <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
            <div>
              <p className="text-sm font-semibold text-slate-700 mb-2">Bạn đã thi xong chưa? <span className="text-red-500">*</span></p>
              <div className="flex gap-3">
                {[
                  { val: "yes", label: "✅ Đã thi xong" },
                  { val: "no", label: "📚 Chưa, đang ôn" },
                ].map(({ val, label }) => (
                  <button key={val} onClick={() => setHasTaken(val as "yes" | "no")}
                    className={`flex-1 rounded-xl border-2 p-3 text-sm font-medium transition-all
                      ${hasTaken === val ? "border-emerald-500 bg-emerald-50 text-emerald-800" : "border-slate-200 hover:border-emerald-200"}`}>
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {hasTaken === "yes" && (
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
            )}

            <label className="block">
              <span className="text-sm font-semibold text-slate-700">Bạn thấy mình yếu phần nào?</span>
              <textarea
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 min-h-[70px]"
                placeholder="VD: Không làm được phần tích phân, hay nhầm dấu... (để trống nếu không biết)"
                value={weakAreas} onChange={(e) => setWeakAreas(e.target.value)} />
            </label>
          </div>

          <div className="flex gap-3">
            <Button variant="secondary" onClick={() => setStep("upload")}>Quay lại</Button>
            <Button onClick={handleAnalyze} isLoading={loading} className="flex-1" disabled={!hasTaken}>
              {loading ? "Đang phân tích và sinh lộ trình..." : <><BrainCircuit className="size-4" /> Phân tích AI</>}
            </Button>
          </div>
        </div>
      )}

      {step === "result" && result && <ResultPanel result={result} />}
    </div>
  );
}
