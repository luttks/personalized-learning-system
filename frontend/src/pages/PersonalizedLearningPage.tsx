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
  Eye,
  ExternalLink,
  FileText,
  Flag,
  Layers,
  Lightbulb,
  Loader2,
  Lock,
  Plus,
  PlaySquare,
  ShieldAlert,
  Link2,
  Target,
  Trash2,
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
  analyzeCompetencyEvidence,
  analyzeDocument,
  generateQuiz,
  submitExam,
  parseExamDocument,
  listSubjects,
  listAnalysesBySubject,
  getExamAnalysis,
  deleteSubject,
  deleteExamAnalysis,
  discardTempFile,
  getExamAnalysisFileBlob,
  suggestGoals,
  type CompetencyEvidenceResult,
  type DocumentAnalysisResult,
  type ExamAnalysisDetail,
  type ExamAnalysisSummary,
  type ExamRecommendation,
  type ExamResources,
  type InlineRoadmap,
  type PhaseResources,
  type QuizQuestion,
  type ParseExamResponse,
  type ReadingTimeEstimate,
  type RoadmapPhase,
  type StudyDepthMode,
  type SubjectSummary,
} from "../api/exam";
import {
  applyPersonalizedRoadmap,
  getPhaseAssessments,
  unlockPhaseAssessmentEarly,
  type PhaseAssessmentStatusResponse,
} from "../api/personalized_roadmap";
import { getStudentProfile } from "../api/student";
import { Button } from "../components/ui";
import { PhaseAssessmentModal } from "../components/PhaseAssessmentModal";
import { FinalExamModal } from "../components/FinalExamModal";
import { DocumentChatWidget } from "../components/DocumentChatWidget";

// 4 mức độ học tập — khớp 1:1 với STUDY_DEPTH_MODE_LABELS ở backend (exam_service.py). Trùng lặp
// nội dung có chủ đích vì Python/TS không chia sẻ được code — nếu đổi nhãn/mô tả, sửa cả 2 nơi.
const STUDY_DEPTH_MODE_OPTIONS: { key: StudyDepthMode; label: string; description: string; paceVerb: string }[] = [
  { key: "skim", label: "Đọc hiểu lướt (Skim & Scan)", description: "Chỉ cần nắm ý chính, lướt nhanh để có cái nhìn tổng quan.", paceVerb: "đọc lướt" },
  { key: "comprehension", label: "Đọc hiểu căn bản (Comprehension)", description: "Đọc hiểu đầy đủ nội dung, nắm ý nghĩa và mối liên hệ giữa các phần.", paceVerb: "đọc hiểu căn bản" },
  { key: "exam_mcq", label: "Học để thi trắc nghiệm (Nhớ chi tiết)", description: "Cần nhớ chi tiết, chính xác để làm tốt bài thi trắc nghiệm.", paceVerb: "học để thi trắc nghiệm" },
  { key: "deep_essay", label: "Học sâu để thi tự luận / Vấn đáp", description: "Gồm tóm tắt, sơ đồ hóa kiến thức, và ôn tập lại ít nhất 2 lần.", paceVerb: "học sâu (tóm tắt, sơ đồ hóa, ôn 2 lần)" },
];

function readingRangeFor(rt: ReadingTimeEstimate, mode: StudyDepthMode): { min: number; max: number } {
  switch (mode) {
    case "skim": return { min: rt.skim_minutes_min, max: rt.skim_minutes_max };
    case "comprehension": return { min: rt.comprehension_minutes_min, max: rt.comprehension_minutes_max };
    case "exam_mcq": return { min: rt.exam_mcq_minutes_min, max: rt.exam_mcq_minutes_max };
    case "deep_essay": return { min: rt.deep_essay_minutes_min, max: rt.deep_essay_minutes_max };
  }
}

// Lưu tạm tiến trình đang làm dở của luồng "Lộ trình học" — để khi người dùng chuyển sang
// trang khác rồi quay lại, các thao tác đã điền không bị mất. File gốc (đối tượng File) không
// thể serialize được nên không lưu; nếu cần, người dùng phải chọn lại file khi quay lại.
const ONBOARDING_DRAFT_KEY = "onboarding_draft_v1";

interface OnboardingDraft {
  screen?: OnboardingScreen;
  analysis?: DocumentAnalysisResult | null;
  fileNames?: string[];
  tempFileId?: string | null;
  selectedGoal?: string;
  customGoal?: string;
  quiz?: QuizQuestion[];
  topicSummary?: string;
  answers?: Record<number, string>;
  quizSubmitted?: boolean;
  quizAnswers?: QuizAnswer[];
  isCurrentlyStudying?: boolean | null;
  curriculumTopic?: string | null;
  onTrack?: boolean | null;
  evidenceResult?: CompetencyEvidenceResult | null;
  evidenceScore?: string;
  evidenceMaxScore?: string;
  deadline?: string;
  startDate?: string;
  schedulePattern?: "consecutive" | "interleaved";
  studyDepthMode?: StudyDepthMode | null;
  suggestedGoals?: string[];
}

function loadOnboardingDraft(): OnboardingDraft {
  try {
    const raw = sessionStorage.getItem(ONBOARDING_DRAFT_KEY);
    return raw ? (JSON.parse(raw) as OnboardingDraft) : {};
  } catch {
    return {};
  }
}

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
const LARGE_FILE_WARNING_BYTES = 20 * 1024 * 1024; // 20MB

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
  const hasLargeFile = files.some((f) => f.size > LARGE_FILE_WARNING_BYTES);

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

      {hasLargeFile && (
        <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
          <AlertCircle className="size-4 shrink-0 mt-0.5 text-amber-500" />
          <span>File này khá lớn, hệ thống cần thời gian đọc và phân tích kỹ hơn — vui lòng chờ trong vài phút sau khi bấm phân tích, đừng tắt hoặc rời trang.</span>
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
      <p className="text-xs text-slate-500 mt-1">PDF, DOCX, TXT, JPG, PNG — tối đa 100MB</p>
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
// Xem trước tài liệu gốc — dùng chung giữa lịch sử môn học và lộ trình học
// ──────────────────────────────────────────────────────────────────────────
function useDocumentPreview() {
  const [isOpen, setIsOpen] = useState(false);
  const [url, setUrl] = useState<string | null>(null);
  const [page, setPage] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [loadedId, setLoadedId] = useState<string | null>(null);

  useEffect(() => {
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [url]);

  async function open(analysisId: string, targetPage?: number | null) {
    setIsOpen(true);
    setError("");
    setPage(targetPage ?? null);
    if (loadedId === analysisId && url) return; // đã tải sẵn đúng file này rồi, khỏi tải lại
    setUrl(null);
    setLoadedId(analysisId);
    setLoading(true);
    try {
      const blob = await getExamAnalysisFileBlob(analysisId);
      setUrl(URL.createObjectURL(blob));
    } catch (e) {
      setError(getApiErrorMessage(e, "Không tìm thấy file gốc (có thể đã bị xóa)."));
    } finally {
      setLoading(false);
    }
  }

  function close() {
    setIsOpen(false);
  }

  return { isOpen, url, page, loading, error, open, close };
}

function DocumentPreviewModal({
  filename,
  url,
  page,
  loading,
  error,
  onClose,
}: {
  filename: string;
  url: string | null;
  page?: number | null;
  loading: boolean;
  error: string;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-4xl h-[85vh] rounded-2xl bg-white shadow-2xl flex flex-col overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-5 py-3 shrink-0">
          <div className="min-w-0">
            <p className="text-xs text-slate-400">Bản xem trước</p>
            <p className="font-semibold text-slate-800 truncate">{filename}</p>
          </div>
          <button onClick={onClose} className="shrink-0 p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100">
            <X className="size-5" />
          </button>
        </div>
        <div className="flex-1 min-h-0 bg-slate-100 flex items-center justify-center overflow-auto">
          {loading && (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="size-4 animate-spin" /> Đang tải file...
            </div>
          )}
          {error && !loading && (
            <div className="flex flex-col items-center gap-2 text-sm text-slate-500 px-6 text-center">
              <AlertCircle className="size-6 text-red-400" />
              {error}
            </div>
          )}
          {url && !loading && !error && (() => {
            const ext = filename.split(".").pop()?.toLowerCase() ?? "";
            if (["jpg", "jpeg", "png", "webp"].includes(ext)) {
              return <img src={url} alt={filename} className="max-w-full max-h-full object-contain" />;
            }
            if (ext === "pdf") {
              const pdfSrc = page ? `${url}#page=${page}` : url;
              return <iframe key={pdfSrc} src={pdfSrc} title={filename} className="w-full h-full border-0" />;
            }
            return (
              <div className="flex flex-col items-center gap-3 text-sm text-slate-500 px-6 text-center">
                <FileText className="size-8 text-slate-300" />
                <p>Định dạng này không xem trước trực tiếp được trong trình duyệt.</p>
                <a
                  href={url}
                  download={filename}
                  className="inline-flex items-center gap-1.5 text-indigo-600 hover:text-indigo-700 font-medium"
                >
                  Tải xuống để xem
                </a>
              </div>
            );
          })()}
        </div>
      </div>
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
  goal: _goal,
  analysisId,
  sourceFilename,
  roadmapId,
  appliedAt,
}: {
  roadmap: InlineRoadmap;
  phaseResources: Record<string, PhaseResources>;
  subject: string;
  goal: string;
  analysisId?: string;
  sourceFilename?: string;
  roadmapId?: string;
  appliedAt?: string | null;
}) {
  const [expandedPhase, setExpandedPhase] = useState<number | null>(0);
  const [applied, setApplied] = useState(Boolean(appliedAt));
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState("");
  const [phaseStatuses, setPhaseStatuses] = useState<PhaseAssessmentStatusResponse[]>([]);
  const [activeAssessmentPhase, setActiveAssessmentPhase] = useState<{ number: number; title: string } | null>(null);
  const [showFinalExam, setShowFinalExam] = useState(false);
  const preview = useDocumentPreview();

  async function refreshPhaseStatuses() {
    if (!roadmapId) return;
    try {
      const data = await getPhaseAssessments(roadmapId);
      setPhaseStatuses(data);
    } catch {
      // Bảng trạng thái bài kiểm tra là tính năng bổ sung — lỗi tải không nên chặn xem lộ trình.
    }
  }

  useEffect(() => {
    void refreshPhaseStatuses();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roadmapId]);

  async function handleApply() {
    if (!roadmapId || applying) return;
    setApplying(true);
    setApplyError("");
    try {
      await applyPersonalizedRoadmap(roadmapId);
      setApplied(true);
    } catch (err) {
      setApplyError(getApiErrorMessage(err, "Áp dụng lộ trình thất bại. Vui lòng thử lại."));
    } finally {
      setApplying(false);
    }
  }

  async function handleUnlockEarly(phaseNumber: number) {
    if (!roadmapId) return;
    const previousStatus = phaseStatuses.find((p) => p.phase_number === phaseNumber - 1)?.status;
    if (previousStatus === "not_passed") {
      const confirmed = window.confirm(
        "Giai đoạn trước đó bạn CHƯA ĐẠT bài kiểm tra — bỏ qua thời gian học lại có thể khiến bạn " +
          "bị hổng kiến thức nghiêm trọng và ảnh hưởng chất lượng đầu ra của cả lộ trình.\n\n" +
          "Nếu bạn vẫn tiếp tục và giai đoạn này CŨNG không đạt, hệ thống sẽ khóa giai đoạn tiếp " +
          "theo lại và bắt bạn học lại giai đoạn này trước khi được làm bài kiểm tra lần nữa.\n\n" +
          "Bạn có chắc chắn muốn mở khóa sớm không?"
      );
      if (!confirmed) return;
    }
    try {
      await unlockPhaseAssessmentEarly(roadmapId, phaseNumber);
      await refreshPhaseStatuses();
    } catch (err) {
      setApplyError(getApiErrorMessage(err, "Không thể mở khóa sớm giai đoạn này."));
    }
  }

  const totalDays = roadmap.total_days ?? roadmap.phases.reduce((s, p) => s + p.days.length, 0);
  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("vi-VN", { weekday: "short", day: "2-digit", month: "2-digit" });

  function gcalLink(phase: RoadmapPhase) {
    if (!phase.days.length) return "#";
    const start = new Date(phase.days[0].date);
    const end = new Date(phase.days[phase.days.length - 1].date);
    end.setDate(end.getDate() + 1); // Google Calendar: ngày kết thúc không bao gồm
    const fmt = (d: Date) => d.toISOString().replace(/[-:]/g, "").slice(0, 8);
    const allTopics = Array.from(new Set(phase.days.flatMap((d) => d.topics.map((t) => t.title))));
    const title = encodeURIComponent(`[${subject}] Giai đoạn ${phase.phase_number}: ${phase.title}`);
    const details = encodeURIComponent(`${phase.why ?? ""}\n\nChủ đề: ${allTopics.join(", ")}\n\nCột mốc: ${phase.milestone}`);
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
            <p className="text-2xl font-black">{totalDays}</p>
            <p className="text-xs text-indigo-200">ngày học</p>
          </div>
        </div>
        {roadmap.end_date && (
          <p className="text-indigo-200 text-xs mt-2">Dự kiến hoàn thành: {formatDate(roadmap.end_date)}</p>
        )}
        {!applied && (
          <div className="flex gap-2 mt-4">
            <button
              onClick={handleApply}
              disabled={applying || !roadmapId}
              title={!roadmapId ? "Lộ trình đang được lưu, vui lòng thử lại sau giây lát" : undefined}
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold transition-all border border-white/20 disabled:cursor-not-allowed bg-white text-indigo-700 hover:bg-indigo-50"
            >
              {applying ? (
                <><Loader2 className="size-3.5 animate-spin" /> Đang áp dụng...</>
              ) : (
                <><Flag className="size-3.5" /> Áp dụng lộ trình</>
              )}
            </button>
          </div>
        )}
        {applied && (
          <p className="flex items-center gap-1.5 mt-4 text-xs font-semibold text-emerald-200">
            <CheckCircle2 className="size-3.5" /> Đã áp dụng — nhận email nhắc học mỗi ngày
          </p>
        )}
        {applyError && <p className="mt-2 text-xs text-red-200">{applyError}</p>}
      </div>

      {roadmap.pacing_note && (
        <div className="flex items-start gap-3 rounded-xl border border-indigo-200 bg-indigo-50 p-4 text-sm text-indigo-800">
          <Lightbulb className="size-4 shrink-0 mt-0.5 text-indigo-600" />
          <p>{roadmap.pacing_note}</p>
        </div>
      )}

      {roadmap.feasible === false && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">
          <AlertCircle className="size-4 shrink-0 mt-0.5 text-amber-600" />
          <div>
            <p className="font-semibold mb-0.5">Lộ trình chưa khớp hoàn toàn với quỹ thời gian bạn đặt ra</p>
            <p>{roadmap.feasibility_note || "Nội dung cần học nhiều hơn quỹ thời gian cho phép."}</p>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {roadmap.phases.map((phase, i) => {
          const c = phaseColors[i % phaseColors.length];
          const phaseKey = `phase_${phase.phase_number}`;
          const phaseRes = phaseResources[phaseKey];
          const isOpen = expandedPhase === i;
          const phaseMinutes = phase.days.reduce((s, d) => s + d.total_minutes, 0);
          const phaseStatus = phaseStatuses.find((p) => p.phase_number === phase.phase_number);
          // Mặc định HIỆN nội dung khi chưa có phaseStatus (bản xem trước lộ trình mới tạo, chưa
          // lưu — chưa có roadmapId nên phaseStatuses luôn rỗng, không phá luồng xem trước hiện
          // có) — chỉ ẨN khi CHẮC CHẮN biết giai đoạn chưa tới (không phải giai đoạn hiện tại,
          // chưa đậu, chưa rớt).
          const isLockedFuture = !!phaseStatus && !phaseStatus.is_current_phase
            && phaseStatus.status !== "passed" && phaseStatus.status !== "not_passed";

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
                  <p className="text-slate-500 text-xs mt-0.5">
                    {phase.days.length} ngày · ~{Math.round(phaseMinutes / 60)} giờ
                    {phase.days[0] && ` · ${formatDate(phase.days[0].date)} → ${formatDate(phase.days[phase.days.length - 1].date)}`}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {phaseStatus?.status === "passed" && (
                    <span className="flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-700" title="Đã vượt qua bài kiểm tra cuối giai đoạn">
                      <Trophy className="size-3.5" /> <span className="hidden sm:inline">Đã đậu</span>
                    </span>
                  )}
                  {phaseStatus?.status === "not_passed" && (
                    <span className="flex items-center gap-1 rounded-full bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-700" title="Đã làm bài, chưa đạt — lộ trình phía sau đã/đang được điều chỉnh">
                      <AlertCircle className="size-3.5" /> <span className="hidden sm:inline">Chưa đạt</span>
                    </span>
                  )}
                  {phaseStatus?.status === "locked_for_retry" && (
                    <span className="flex items-center gap-1 rounded-full bg-red-100 px-2 py-1 text-xs font-semibold text-red-700" title="Đang khóa để học lại — bỏ qua giai đoạn trước rồi cũng không đạt giai đoạn này">
                      <Lock className="size-3.5" /> <span className="hidden sm:inline">Đang khóa để học lại</span>
                    </span>
                  )}
                  {phaseStatus && phaseStatus.status !== "passed" && phaseStatus.status !== "not_passed" && phaseStatus.status !== "locked_for_retry" && !phaseStatus.is_current_phase && (
                    <span className="flex items-center gap-1 rounded-full bg-slate-200 px-2 py-1 text-xs font-medium text-slate-500" title="Cần hoàn thành các giai đoạn trước">
                      <Lock className="size-3.5" />
                    </span>
                  )}
                  <a
                    href={gcalLink(phase)}
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
                  {isLockedFuture ? (
                    <div className="rounded-xl bg-white/70 p-4 text-sm text-slate-500 flex items-center gap-2">
                      <Lock className="size-4 shrink-0" />
                      <span>Nội dung giai đoạn này sẽ hiển thị khi bạn học đến đây.</span>
                    </div>
                  ) : (
                  <>
                  {phase.why && (
                    <div className="rounded-xl bg-white/70 p-3 text-sm">
                      <p className="font-semibold text-slate-800 mb-1 flex items-center gap-2"><Target className="size-3.5 text-indigo-500" /> Ý nghĩa giai đoạn này</p>
                      <p className="text-slate-700">{phase.why}</p>
                    </div>
                  )}
                  <div>
                    <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1.5"><Layers className="size-3.5" /> Lịch học từng ngày</p>
                    <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                      {phase.days.map((day) => {
                        const resourceIcon: Record<string, string> = { video: "🎬", exercise: "✏️", reading: "📖", mixed: "🔀" };
                        return (
                          <div key={day.date} className="rounded-xl bg-white/80 border border-slate-200 p-3">
                            <div className="flex items-center justify-between gap-2 mb-1">
                              <p className="text-xs font-semibold text-slate-600">Ngày {day.day_number} · {formatDate(day.date)}</p>
                              <span className="text-xs text-slate-400">{day.total_minutes} phút</span>
                            </div>
                            {day.note && <p className="text-xs text-indigo-600 italic mb-1.5">{day.note}</p>}
                            <div className="space-y-1.5">
                              {day.topics.map((t, ti) => (
                                <div key={ti} className="text-sm">
                                  <div className="flex items-start justify-between gap-2">
                                    <p className="font-medium text-slate-800">
                                      {t.title} <span className="text-xs text-slate-400 font-normal">({t.minutes} phút)</span>
                                      {t.resource_type && <span className="text-xs ml-1" title={t.resource_type}>{resourceIcon[t.resource_type] ?? ""}</span>}
                                    </p>
                                    {analysisId && (
                                      <button
                                        onClick={() => void preview.open(analysisId, t.location_page)}
                                        title="Xem tài liệu gốc"
                                        className="shrink-0 flex items-center gap-1 rounded-lg bg-slate-100 hover:bg-indigo-50 hover:text-indigo-600 px-1.5 py-0.5 text-xs text-slate-500 transition-colors"
                                      >
                                        <Eye className="size-3" />
                                      </button>
                                    )}
                                  </div>
                                  {t.why && <p className="text-xs text-slate-500 mt-0.5">💡 {t.why}</p>}
                                  {t.activities && <p className="text-xs text-slate-500 mt-0.5">📝 {t.activities}</p>}
                                </div>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3 text-sm">
                    <p className="font-semibold text-emerald-800 mb-0.5">🏁 Cột mốc</p>
                    <p className="text-emerald-700">{phase.milestone}</p>
                  </div>
                  {phaseRes && <PhaseResourcesPanel res={phaseRes} />}
                  </>
                  )}

                  {roadmapId && phaseStatus &&
                    // Bài kiểm tra là thông tin ẨN — chỉ hé lộ sự tồn tại của nó khi giai đoạn đã
                    // đến lúc kiểm tra (unlocked) hoặc đã hoàn thành, TUYỆT ĐỐI không lộ trạng thái
                    // "đang được AI sinh" ngay khi vừa tạo lộ trình (mất bất ngờ + gây lo lắng thừa
                    // cho người học trước khi họ kịp học gì).
                    !(phaseStatus.is_current_phase && (phaseStatus.status === "pending" || phaseStatus.status === "generating")) && (
                      <div className="rounded-xl border border-indigo-200 bg-indigo-50/60 p-3 text-sm">
                        <p className="font-semibold text-indigo-800 mb-1.5 flex items-center gap-1.5">
                          <ShieldAlert className="size-3.5" /> Bài kiểm tra cuối giai đoạn
                        </p>
                        {phaseStatus.status === "passed" ? (
                          <p className="text-emerald-700 flex items-center gap-1.5"><CheckCircle2 className="size-3.5" /> Bạn đã vượt qua bài kiểm tra này.</p>
                        ) : phaseStatus.status === "not_passed" ? (
                          <p className="text-amber-700 flex items-center gap-1.5">
                            <AlertCircle className="size-3.5 shrink-0" /> Bạn đã hoàn thành bài kiểm tra này (chưa đạt {Math.round(phaseStatus.pass_threshold * 100)}%
                            {phaseStatus.score_ratio !== null && <> — đạt {Math.round(phaseStatus.score_ratio * 100)}%</>}) · Lộ trình phía sau đã được điều chỉnh cho phù hợp.
                          </p>
                        ) : phaseStatus.status === "locked_for_retry" ? (
                          <p className="text-red-700 flex items-center gap-1.5">
                            <Lock className="size-3.5 shrink-0" /> Bạn đã bỏ qua giai đoạn trước khi còn hổng kiến thức và cũng chưa đạt giai
                            đoạn này — hệ thống tạm khóa lại để bạn học chắc trước khi làm bài kiểm tra tiếp.
                            {phaseStatus.retry_unlock_at && <> Bài kiểm tra sẽ mở lại vào {formatDate(`${phaseStatus.retry_unlock_at}T00:00:00`)}.</>}
                          </p>
                        ) : !phaseStatus.is_current_phase ? (
                          <p className="text-slate-500 flex items-center gap-1.5"><Lock className="size-3.5" /> Cần hoàn thành các giai đoạn trước đó.</p>
                        ) : phaseStatus.unlocked ? (
                          <div className="space-y-1.5">
                            {phaseStatus.attempts_count > 0 && phaseStatus.score_ratio !== null && (
                              <p className="text-xs text-amber-700">Lần gần nhất: {Math.round(phaseStatus.score_ratio * 100)}% (cần {Math.round(phaseStatus.pass_threshold * 100)}% để đậu)</p>
                            )}
                            <Button
                              onClick={() => setActiveAssessmentPhase({ number: phase.phase_number, title: phase.title })}
                              className="!py-1.5 !px-3 text-xs"
                            >
                              Làm bài kiểm tra
                            </Button>
                          </div>
                        ) : (
                          <div className="space-y-1.5">
                            <p className="text-slate-500">Giai đoạn chưa tới hạn theo lịch học.</p>
                            <Button variant="secondary" onClick={() => void handleUnlockEarly(phase.phase_number)} className="!py-1.5 !px-3 text-xs">
                              Tôi học xong sớm rồi, mở khóa ngay
                            </Button>
                          </div>
                        )}
                      </div>
                    )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {roadmapId && phaseStatuses.length > 0 &&
        phaseStatuses.every((p) => p.status === "passed" || p.status === "not_passed") && (
          <div className="rounded-2xl border-2 border-indigo-300 bg-gradient-to-br from-indigo-50 to-white p-5 text-center">
            <Trophy className="size-8 mx-auto text-indigo-500 mb-2" />
            <p className="font-bold text-indigo-900">Bạn đã hoàn thành toàn bộ lộ trình!</p>
            <p className="text-sm text-slate-600 mt-1">
              Làm bài thi chốt hạ để tổng kết lại toàn bộ kiến thức đã học qua các giai đoạn.
            </p>
            <Button onClick={() => setShowFinalExam(true)} className="mt-3">
              Làm bài thi chốt hạ
            </Button>
          </div>
        )}

      {preview.isOpen && (
        <DocumentPreviewModal
          filename={sourceFilename || "Tài liệu gốc"}
          url={preview.url}
          page={preview.page}
          loading={preview.loading}
          error={preview.error}
          onClose={preview.close}
        />
      )}

      {roadmapId && activeAssessmentPhase && (
        <PhaseAssessmentModal
          roadmapId={roadmapId}
          phaseNumber={activeAssessmentPhase.number}
          phaseTitle={activeAssessmentPhase.title}
          previousPhaseNotPassed={
            phaseStatuses.find((p) => p.phase_number === activeAssessmentPhase.number - 1)?.status === "not_passed"
          }
          onClose={() => setActiveAssessmentPhase(null)}
          onCompleted={() => void refreshPhaseStatuses()}
        />
      )}

      {roadmapId && showFinalExam && (
        <FinalExamModal roadmapId={roadmapId} onClose={() => setShowFinalExam(false)} />
      )}

      {roadmapId && analysisId && (
        <DocumentChatWidget roadmapId={roadmapId} subject={subject} />
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Result Panel (wraps AI rec + roadmap — luồng 1)
// ──────────────────────────────────────────────────────────────────────────
function ResultPanel({ result }: { result: ExamAnalysisDetail }) {
  const [tab, setTab] = useState<"roadmap" | "rec">("roadmap");
  const hasRec = Object.keys(result.ai_recommendation).filter((k) => !k.startsWith("_")).length > 0;
  const hasRoadmap = result.roadmap && result.roadmap.phases?.length > 0;
  const subject = result.subject || result.ai_recommendation?.["_goal"] ? (result.subject || result.filename.replace(/\.[^.]+$/, "")) : "Học tập";
  const goal = (result.ai_recommendation?.["_goal"] as string) || "Nắm vững kiến thức";

  const curriculumPosition = result.ai_recommendation?.["_curriculum_position"] as
    | { topic: string; on_track: boolean }
    | null
    | undefined;
  const providedDeadline = result.ai_recommendation?.["_deadline"] as string | null | undefined;
  const providedMinutesPerDay = result.ai_recommendation?.["_minutes_per_day"] as number | null | undefined;
  const providedEvidenceType = result.ai_recommendation?.["_evidence_type"] as string | null | undefined;
  const quizSummary = result.ai_recommendation?.["_quiz_summary"] as
    | { correct: number; total: number }
    | null
    | undefined;
  const evidenceTypeLabel: Record<string, string> = {
    transcript: "Bảng điểm",
    certificate: "Chứng chỉ",
    exam: "Bài kiểm tra đã làm",
    other: "Minh chứng khác",
  };
  const hasProvidedInfo = Boolean(
    goal || providedDeadline || providedMinutesPerDay || curriculumPosition || providedEvidenceType || quizSummary
  );

  return (
    <div className="space-y-5 max-w-4xl mx-auto">
      {result.roadmap_error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <AlertCircle className="size-4 shrink-0 mt-0.5 text-red-500" />
          <p>{result.roadmap_error}</p>
        </div>
      )}
      {result.exam_score !== null && (
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-500 mb-1">Điểm số</p>
            <p className="text-2xl font-black text-indigo-700">{result.exam_score}/{result.exam_max_score}</p>
          </div>
        </div>
      )}

      {/* Xem lại các bước đã điền — chỉ đọc, không cho sửa */}
      {hasProvidedInfo && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Thông tin bạn đã cung cấp</p>
          <dl className="grid gap-3 sm:grid-cols-2 text-sm">
            <div>
              <dt className="text-xs text-slate-400">Mục tiêu</dt>
              <dd className="text-slate-800 mt-0.5">{goal}</dd>
            </div>
            {providedDeadline && (
              <div>
                <dt className="text-xs text-slate-400">Hạn mục tiêu</dt>
                <dd className="text-slate-800 mt-0.5">{new Date(providedDeadline).toLocaleDateString("vi-VN")}</dd>
              </div>
            )}
            {providedMinutesPerDay ? (
              <div>
                <dt className="text-xs text-slate-400">Thời gian học mỗi ngày</dt>
                <dd className="text-slate-800 mt-0.5">{providedMinutesPerDay} phút</dd>
              </div>
            ) : null}
            {curriculumPosition && (
              <div>
                <dt className="text-xs text-slate-400">Vị trí trong chương trình</dt>
                <dd className="text-slate-800 mt-0.5">
                  {curriculumPosition.topic} — {curriculumPosition.on_track ? "Đã học vững" : "Bị hổng / mất gốc"}
                </dd>
              </div>
            )}
            {providedEvidenceType && (
              <div>
                <dt className="text-xs text-slate-400">Minh chứng năng lực</dt>
                <dd className="text-slate-800 mt-0.5">{evidenceTypeLabel[providedEvidenceType] ?? providedEvidenceType}</dd>
              </div>
            )}
            {quizSummary && (
              <div>
                <dt className="text-xs text-slate-400">Kết quả kiểm tra nhanh</dt>
                <dd className="text-slate-800 mt-0.5">{quizSummary.correct}/{quizSummary.total} câu đúng</dd>
              </div>
            )}
          </dl>
        </div>
      )}

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
          analysisId={result.id}
          sourceFilename={result.filename}
          roadmapId={result.roadmap_id ?? undefined}
        />
      )}
      {tab === "rec" && hasRec && <RecommendationPanel rec={result.ai_recommendation} />}

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
                analysisId={result.id}
                sourceFilename={result.filename}
                roadmapId={result.roadmap_id ?? undefined}
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
  const [deletingSubject, setDeletingSubject] = useState<string | null>(null);

  const color = mode === "onboarding" ? "indigo" : "emerald";

  function refresh() {
    setLoading(true);
    listSubjects(mode)
      .then(setSubjects)
      .catch(() => setSubjects([]))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, [mode]);

  async function handleDeleteSubject(subject: string) {
    if (!window.confirm(`Xóa toàn bộ dữ liệu môn "${subject}"? Hành động này không thể hoàn tác.`)) return;
    setDeletingSubject(subject);
    try {
      await deleteSubject(subject);
      setSubjects((prev) => prev.filter((s) => s.subject !== subject));
    } catch {
      window.alert("Xóa thất bại, vui lòng thử lại.");
    } finally {
      setDeletingSubject(null);
    }
  }

  const title = mode === "onboarding" ? "Lộ trình học" : "Cải thiện sau thi";
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
            <div
              key={s.subject}
              className="w-full flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-2 pl-4 hover:border-indigo-300 hover:shadow-md transition-all group"
            >
              <button
                onClick={() => onViewSubject(s.subject)}
                className="flex-1 min-w-0 flex items-center gap-4 text-left py-2"
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
              <button
                onClick={() => handleDeleteSubject(s.subject)}
                disabled={deletingSubject === s.subject}
                title="Xóa môn học này"
                className="shrink-0 p-2 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-40"
              >
                {deletingSubject === s.subject ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
              </button>
            </div>
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
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const color = mode === "onboarding" ? "indigo" : "emerald";

  const preview = useDocumentPreview();
  const [previewFilename, setPreviewFilename] = useState("");

  useEffect(() => {
    setLoading(true);
    listAnalysesBySubject(subject)
      .then(setAnalyses)
      .catch(() => setAnalyses([]))
      .finally(() => setLoading(false));
  }, [subject]);

  async function handleDeleteAnalysis(a: ExamAnalysisSummary) {
    if (!window.confirm(`Xóa tài liệu "${a.filename}"? Hành động này không thể hoàn tác.`)) return;
    setDeletingId(a.id);
    try {
      await deleteExamAnalysis(a.id);
      setAnalyses((prev) => prev.filter((x) => x.id !== a.id));
    } catch {
      window.alert("Xóa thất bại, vui lòng thử lại.");
    } finally {
      setDeletingId(null);
    }
  }

  function handlePreview(a: ExamAnalysisSummary) {
    setPreviewFilename(a.filename);
    void preview.open(a.id);
  }

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
            <div
              key={a.id}
              className="w-full flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-2 pl-4 hover:border-indigo-300 hover:shadow transition-all group"
            >
              <button
                onClick={() => onViewAnalysis(a)}
                className="flex-1 min-w-0 flex items-center gap-4 text-left py-2"
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
              <button
                onClick={() => handlePreview(a)}
                title="Xem lại tài liệu gốc"
                className="shrink-0 p-2 text-slate-300 hover:text-indigo-500 hover:bg-indigo-50 rounded-lg transition-colors"
              >
                <Eye className="size-4" />
              </button>
              <button
                onClick={() => handleDeleteAnalysis(a)}
                disabled={deletingId === a.id}
                title="Xóa tài liệu này"
                className="shrink-0 p-2 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-40"
              >
                {deletingId === a.id ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
              </button>
            </div>
          ))}
        </div>
      )}

      {preview.isOpen && (
        <DocumentPreviewModal
          filename={previewFilename}
          url={preview.url}
          page={preview.page}
          loading={preview.loading}
          error={preview.error}
          onClose={preview.close}
        />
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
  const draftOnMount = useRef(loadOnboardingDraft()).current;

  const [screen, setScreen] = useState<OnboardingScreen>(draftOnMount.screen ?? "subject_list");
  const [viewingSubject, setViewingSubject] = useState<string | null>(null);

  // File gốc không thể lưu lại qua sessionStorage — nhưng ngay khi phân tích tài liệu, file đã
  // được lưu tạm ở backend (temp_file_id, một chuỗi ngắn lưu được bình thường), nên khi quay lại
  // giữa chừng vẫn dùng lại được file đó mà không cần chọn lại. Chỉ khi thiếu temp_file_id (VD
  // nháp cũ từ trước khi có tính năng này) mới cần yêu cầu chọn lại.
  const [files, setFiles] = useState<File[]>([]);
  const [tempFileId, setTempFileId] = useState<string | null>(draftOnMount.tempFileId ?? null);
  const [needsFileReattach, setNeedsFileReattach] = useState(
    Boolean(
      !draftOnMount.tempFileId && draftOnMount.analysis && draftOnMount.screen &&
      draftOnMount.screen !== "subject_list" && draftOnMount.screen !== "upload_and_info"
    )
  );
  const previouslyAttachedFileNames = draftOnMount.fileNames ?? [];

  const [analysis, setAnalysis] = useState<DocumentAnalysisResult | null>(draftOnMount.analysis ?? null);
  const [selectedGoal, setSelectedGoal] = useState<string>(draftOnMount.selectedGoal ?? "");
  const [customGoal, setCustomGoal] = useState<string>(draftOnMount.customGoal ?? "");
  const [quiz, setQuiz] = useState<QuizQuestion[]>(draftOnMount.quiz ?? []);
  const [topicSummary, setTopicSummary] = useState(draftOnMount.topicSummary ?? "");
  const [answers, setAnswers] = useState<Record<number, string>>(draftOnMount.answers ?? {});
  const [quizSubmitted, setQuizSubmitted] = useState(draftOnMount.quizSubmitted ?? false);
  const [quizAnswers, setQuizAnswers] = useState<QuizAnswer[]>(draftOnMount.quizAnswers ?? []);
  const [finalResult, setFinalResult] = useState<ExamAnalysisDetail | null>(null);

  // Vị trí hiện tại trong chương trình (mục lục — tick 1 điểm mốc + có bị hổng hay không) — chỉ
  // hỏi cụ thể nếu người dùng xác nhận đang học tài liệu này theo lớp/chương trình nào đó.
  const [isCurrentlyStudying, setIsCurrentlyStudying] = useState<boolean | null>(draftOnMount.isCurrentlyStudying ?? null);
  const [curriculumTopic, setCurriculumTopic] = useState<string | null>(draftOnMount.curriculumTopic ?? null);
  const [onTrack, setOnTrack] = useState<boolean | null>(draftOnMount.onTrack ?? null);

  // Minh chứng năng lực (bảng điểm / chứng chỉ / bài kiểm tra đã làm) — file cũng không lưu lại được
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null);
  const [evidenceChecking, setEvidenceChecking] = useState(false);
  const [evidenceResult, setEvidenceResult] = useState<CompetencyEvidenceResult | null>(draftOnMount.evidenceResult ?? null);
  const [evidenceError, setEvidenceError] = useState("");
  const [evidenceScore, setEvidenceScore] = useState(draftOnMount.evidenceScore ?? "");
  const [evidenceMaxScore, setEvidenceMaxScore] = useState(draftOnMount.evidenceMaxScore ?? "");

  // Mức độ học tập — bắt buộc chọn, quyết định mốc tốc độ đọc dùng làm tham chiếu VÀ độ sâu hoạt
  // động trong lộ trình sinh ra. Không còn field nào từ Bước 1 nữa nên gợi ý mục tiêu phải đợi
  // chọn xong mức độ này rồi mới sinh (xem refreshSuggestedGoals).
  const [studyDepthMode, setStudyDepthMode] = useState<StudyDepthMode | null>(draftOnMount.studyDepthMode ?? null);

  // Gợi ý mục tiêu — CHỈ sinh qua suggest-goals SAU KHI đã chọn mức độ học tập (và biết thêm vị
  // trí chương trình/minh chứng năng lực nếu có), không còn nguồn nào khác (đã bỏ suggested_goals
  // tính sớm ở Bước 1 và FIXED_GOAL_OPTIONS tĩnh).
  const [suggestedGoals, setSuggestedGoals] = useState<string[]>(draftOnMount.suggestedGoals ?? []);
  const goalRefreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const goalRefreshSeq = useRef(0);
  const [refreshingGoals, setRefreshingGoals] = useState(false);

  // Quỹ thời gian cho lộ trình — số phút/ngày lấy từ Hồ sơ học sinh, không hỏi lại
  const [deadline, setDeadline] = useState(draftOnMount.deadline ?? "");
  const [startDate, setStartDate] = useState(draftOnMount.startDate ?? "");
  const [minutesPerDay, setMinutesPerDay] = useState(60);
  const [daysPerWeek, setDaysPerWeek] = useState(7);
  const [schedulePattern, setSchedulePattern] = useState<"consecutive" | "interleaved">(draftOnMount.schedulePattern ?? "consecutive");

  useEffect(() => {
    getStudentProfile()
      .then((profile) => {
        setMinutesPerDay(profile.study_minutes_per_day);
        setDaysPerWeek(profile.study_days_per_week);
      })
      .catch(() => { });
  }, []);

  // Lưu lại tiến trình đang làm dở mỗi khi có thay đổi, để không mất khi chuyển sang trang khác
  useEffect(() => {
    if (screen === "subject_list" || screen === "result") {
      sessionStorage.removeItem(ONBOARDING_DRAFT_KEY);
      return;
    }
    const draft: OnboardingDraft = {
      screen, analysis, selectedGoal, customGoal, quiz, topicSummary, answers, quizSubmitted, quizAnswers,
      isCurrentlyStudying, curriculumTopic, onTrack, evidenceResult, evidenceScore, evidenceMaxScore, deadline, startDate, schedulePattern, tempFileId,
      studyDepthMode, suggestedGoals,
      fileNames: files.length > 0 ? files.map((f) => f.name) : previouslyAttachedFileNames,
    };
    try { sessionStorage.setItem(ONBOARDING_DRAFT_KEY, JSON.stringify(draft)); } catch { /* ignore */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screen, analysis, selectedGoal, customGoal, quiz, topicSummary, answers, quizSubmitted, quizAnswers,
    isCurrentlyStudying, curriculumTopic, onTrack, evidenceResult, evidenceScore, evidenceMaxScore, deadline, startDate, schedulePattern, tempFileId, files,
    studyDepthMode, suggestedGoals]);

  function resetOnboardingState() {
    sessionStorage.removeItem(ONBOARDING_DRAFT_KEY);
    if (tempFileId) void discardTempFile(tempFileId).catch(() => { });
    setFiles([]);
    setTempFileId(null);
    setNeedsFileReattach(false);
    setAnalysis(null);
    setSelectedGoal("");
    setCustomGoal("");
    setQuiz([]);
    setTopicSummary("");
    setAnswers({});
    setQuizSubmitted(false);
    setQuizAnswers([]);
    setIsCurrentlyStudying(null);
    setCurriculumTopic(null);
    setOnTrack(null);
    setEvidenceFile(null);
    setEvidenceResult(null);
    setEvidenceError("");
    setEvidenceScore("");
    setEvidenceMaxScore("");
    setDeadline("");
    setStartDate("");
    setSchedulePattern("consecutive");
    setStudyDepthMode(null);
    setSuggestedGoals([]);
  }

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
      if (!result.has_clear_structure) {
        setError(
          result.structure_reason
            ? `Không thể tạo lộ trình với tài liệu này: ${result.structure_reason}`
            : "Tài liệu này không có chương/mục rõ ràng nên không thể tạo lộ trình học. Hãy thử tài liệu có chia chương/phần cụ thể."
        );
        return;
      }
      setAnalysis(result);
      setTempFileId(result.temp_file_id);
      setNeedsFileReattach(false);
      setCurriculumTopic(null);
      setOnTrack(null);
      // Tài liệu mới = môn học có thể đã đổi — minh chứng năng lực đã xác thực cho tài liệu CŨ
      // không còn ý nghĩa với môn mới, phải dọn theo (trước đây chỉ rò rỉ 1 chữ evidence_type vô
      // hại, giờ có cả subject_relationship nên nếu sót sẽ gây hiểu nhầm nghiêm trọng hơn).
      setEvidenceFile(null);
      setEvidenceResult(null);
      setEvidenceError("");
      setEvidenceScore("");
      setEvidenceMaxScore("");
      // Gợi ý mục tiêu cũ (nếu có, từ tài liệu trước) không còn khớp tài liệu mới — xóa, chờ
      // người dùng chọn lại mức độ học tập để sinh gợi ý mới đúng ngữ cảnh.
      setSuggestedGoals([]);

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

  async function handleEvidenceFile(file: File) {
    setEvidenceFile(file);
    setEvidenceResult(null);
    setEvidenceError("");
    setEvidenceScore("");
    setEvidenceMaxScore("");
    setEvidenceChecking(true);
    try {
      const result = await analyzeCompetencyEvidence(file, analysis?.subject, analysis?.topics);
      setEvidenceResult(result);
      if (!result.is_competency_evidence) {
        setEvidenceError(
          result.reason || "File này không phải bảng điểm/chứng chỉ/bài kiểm tra hợp lệ."
        );
      } else {
        refreshSuggestedGoals({ evidenceResult: result });
      }
    } catch (e) {
      setEvidenceError(getApiErrorMessage(e));
    } finally {
      setEvidenceChecking(false);
    }
  }

  /**
   * Sinh/làm mới suggested_goals — CHỈ chạy sau khi đã chọn Mức độ học tập (bắt buộc), và có thể
   * chạy lại mỗi khi vị trí chương trình/minh chứng năng lực đổi sau đó. Đây là nguồn gợi ý mục
   * tiêu DUY NHẤT (không còn suggested_goals tính sớm ở Bước 1 hay FIXED_GOAL_OPTIONS tĩnh nữa).
   * Debounce 500ms + sequence-guard để tránh phản hồi cũ ghi đè phản hồi mới khi người dùng thao
   * tác nhanh (VD tick vị trí rồi upload minh chứng liên tiếp).
   */
  function refreshSuggestedGoals(overrides: {
    curriculumTopic?: string | null;
    onTrack?: boolean | null;
    evidenceResult?: CompetencyEvidenceResult | null;
    studyDepthMode?: StudyDepthMode | null;
  } = {}) {
    if (!analysis) return;
    const effTopic = overrides.curriculumTopic !== undefined ? overrides.curriculumTopic : curriculumTopic;
    const effOnTrack = overrides.onTrack !== undefined ? overrides.onTrack : onTrack;
    const effEvidence = overrides.evidenceResult !== undefined ? overrides.evidenceResult : evidenceResult;
    const effMode = overrides.studyDepthMode !== undefined ? overrides.studyDepthMode : studyDepthMode;
    if (!effMode) return; // Chưa chọn mức độ học tập — chưa đủ điều kiện để gợi ý mục tiêu.
    if (goalRefreshTimer.current) clearTimeout(goalRefreshTimer.current);
    const seq = ++goalRefreshSeq.current;
    goalRefreshTimer.current = setTimeout(async () => {
      setRefreshingGoals(true);
      try {
        const result = await suggestGoals({
          subject: analysis.subject,
          topics: analysis.topics,
          content_summary: analysis.content_summary,
          study_depth_mode: effMode,
          curriculum_position: effTopic ? { topic: effTopic, on_track: effOnTrack ?? true } : undefined,
          evidence_context: effEvidence?.is_competency_evidence
            ? {
              evidence_type: effEvidence.evidence_type,
              evidence_subject: effEvidence.evidence_subject,
              score_summary: effEvidence.score_summary,
              subject_relationship: effEvidence.subject_relationship,
              relationship_reason: effEvidence.relationship_reason,
            }
            : undefined,
        });
        if (seq === goalRefreshSeq.current && result.suggested_goals?.length) {
          setSuggestedGoals(result.suggested_goals);
        }
      } catch {
        // Chỉ là cải thiện UX, không quan trọng bằng luồng chính — lỗi thì giữ nguyên gợi ý cũ.
      } finally {
        if (seq === goalRefreshSeq.current) setRefreshingGoals(false);
      }
    }, 500);
  }

  function handleSelectStudyDepthMode(mode: StudyDepthMode) {
    setStudyDepthMode(mode);
    refreshSuggestedGoals({ studyDepthMode: mode });
  }

  function handleContinueFromGoalStep() {
    if (quiz.length > 0) {
      // Đã có bài kiểm tra rồi — không tạo lại, chỉ điều hướng tới để xem/tiếp tục
      setScreen("quiz");
      return;
    }
    void handleGenerateQuiz();
  }

  async function handleGenerateQuiz() {
    if (!studyDepthMode) { setError("Vui lòng chọn mức độ học tập."); return; }
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

  function handleFinishQuiz() {
    // Chỉ chấm điểm + hiện kết quả tại chỗ — KHÔNG gọi API tạo lộ trình ngay, để người
    // dùng có thể quay lại chỉnh thông tin mà không mất bài kiểm tra đã làm.
    const computed: QuizAnswer[] = quiz.map((q) => ({
      questionId: q.id,
      selectedOption: answers[q.id] ?? "",
      correct: (answers[q.id] ?? "") === q.correct,
      topic: q.topic,
      difficulty: q.difficulty,
    }));
    setQuizAnswers(computed);
    setQuizSubmitted(true);
  }

  async function handleGenerateRoadmap() {
    if (!analysis) return;
    if (!studyDepthMode) {
      // Phòng trường hợp draft dở dang phục hồi từ sessionStorage (tạo trước khi có field này)
      // thiếu mức độ học tập — đưa về Bước 2 kèm thông báo, không để lộ lỗi 422 thô từ backend.
      setScreen("goal_selection");
      setError("Vui lòng chọn mức độ học tập trước khi tạo lộ trình.");
      return;
    }
    if (!files.length && !tempFileId) {
      setNeedsFileReattach(true);
      setError("Vui lòng chọn lại file tài liệu (ở banner phía trên) trước khi tạo lộ trình.");
      return;
    }
    setError("");
    setLoading(true);
    setLoadingMsg("Đang phân tích kết quả và sinh lộ trình học tập...");
    try {
      const quizResultsJson = JSON.stringify(
        quizAnswers.map((a) => ({ topic: a.topic, correct: a.correct, difficulty: a.difficulty }))
      );
      const curriculumPositionJson = curriculumTopic
        ? JSON.stringify({ topic: curriculumTopic, on_track: onTrack ?? true })
        : undefined;
      // Ưu tiên dùng file đã lưu tạm ở backend (temp_file_id) — không cần upload lại toàn bộ file
      const data = await submitExam(files.length ? files[0] : null, {
        mode: "onboarding",
        selectedGoal: effectiveGoal,
        subject: analysis.subject,
        quickQuizResults: quizResultsJson,
        rawTextForCrawl: analysis.raw_text.slice(0, 800),
        isCodeRelated: analysis.is_code_related,
        curriculumPosition: curriculumPositionJson,
        topics: analysis.topics.length ? JSON.stringify(analysis.topics) : undefined,
        deadline: deadline || undefined,
        startDate: startDate || undefined,
        minutesPerDay,
        daysPerWeek,
        schedulePattern,
        studyDepthMode,
        readingTimeHint: analysis.reading_time ? JSON.stringify(analysis.reading_time) : undefined,
        examScore: evidenceResult?.evidence_type === "exam" && evidenceScore ? evidenceScore : undefined,
        examMaxScore: evidenceResult?.evidence_type === "exam" && evidenceMaxScore ? evidenceMaxScore : undefined,
        evidenceType: evidenceResult?.is_competency_evidence ? evidenceResult.evidence_type : undefined,
        evidenceContext: evidenceResult?.is_competency_evidence
          ? JSON.stringify({
            evidence_subject: evidenceResult.evidence_subject,
            score_summary: evidenceResult.score_summary,
            subject_relationship: evidenceResult.subject_relationship,
            relationship_reason: evidenceResult.relationship_reason,
          })
          : undefined,
        tempFileId: !files.length && tempFileId ? tempFileId : undefined,
      });
      setTempFileId(null);
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
        onNew={() => { resetOnboardingState(); setScreen("upload_and_info"); }}
        onBack={() => { }}
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
            else if (screen === "goal_selection") {
              // Một khi đã tạo bài kiểm tra nhanh, không cho quay lại tải tài liệu mới nữa
              if (quiz.length === 0) setScreen("upload_and_info");
            }
            else if (screen === "quiz") setScreen("goal_selection");
            else if (screen === "result") setScreen("subject_list");
          }}
          disabled={screen === "goal_selection" && quiz.length > 0}
          className="text-slate-500 hover:text-slate-800 transition-colors p-1 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:text-slate-500"
        >
          <X className="size-5" />
        </button>
        <div>
          <h2 className="font-bold text-slate-900 text-xl">Lộ trình học</h2>
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

      {needsFileReattach && files.length === 0 && screen !== "upload_and_info" && screen !== "subject_list" && (
        <div className="flex flex-col gap-2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 max-w-2xl mx-auto sm:flex-row sm:items-center">
          <AlertCircle className="size-4 shrink-0 text-amber-500" />
          <p className="flex-1">
            Do vừa chuyển trang, vui lòng chọn lại file tài liệu để tiếp tục
            {previouslyAttachedFileNames.length > 0 && (
              <> (trước đó: <span className="font-medium">{previouslyAttachedFileNames.join(", ")}</span>)</>
            )}
            . Toàn bộ thông tin bạn đã điền vẫn được giữ nguyên.
          </p>
          <label className="shrink-0 inline-flex items-center gap-1.5 rounded-lg bg-amber-600 text-white px-3 py-1.5 text-xs font-semibold cursor-pointer hover:bg-amber-700 transition-colors">
            <Upload className="size-3.5" /> Chọn lại file
            <input
              type="file"
              multiple
              className="hidden"
              accept=".pdf,.docx,.txt,.jpg,.jpeg,.png"
              onChange={(e) => {
                const picked = Array.from(e.target.files ?? []);
                if (picked.length) {
                  setFiles(picked);
                  setNeedsFileReattach(false);
                }
              }}
            />
          </label>
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
        <div className="max-w-5xl mx-auto space-y-5">
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
            {analysis.reading_time && (
              <p className="text-xs text-indigo-600 mt-2">
                📖 Tài liệu này có khoảng ~{analysis.reading_time.word_count.toLocaleString("vi-VN")} từ — chọn "Mức độ học tập" bên dưới để xem ước lượng thời gian phù hợp.
              </p>
            )}
          </div>

          <div className="grid gap-5 lg:grid-cols-2 items-start">
            <div className="space-y-5">
              {/* Tiến độ hiện tại — mục lục, tick 1 điểm mốc + phát hiện học lệch */}
              {analysis.topics.length > 0 && (
                <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-3">
                  <div className="flex items-center gap-2">
                    <Layers className="size-4 text-indigo-600" />
                    <h3 className="font-semibold text-slate-800">Tình trạng hiện tại</h3>
                  </div>
                  <p className="text-xs text-slate-400">
                    Bạn có đang học tài liệu này không?
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setIsCurrentlyStudying(true)}
                      className={`text-xs rounded-full px-3 py-1.5 border font-medium transition-all
                    ${isCurrentlyStudying === true ? "border-indigo-500 bg-indigo-500 text-white" : "border-slate-300 text-slate-600 hover:bg-slate-50"}`}
                    >
                      Có
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setIsCurrentlyStudying(false);
                        if (curriculumTopic !== null) {
                          setCurriculumTopic(null); setOnTrack(null);
                          refreshSuggestedGoals({ curriculumTopic: null, onTrack: null });
                        }
                      }}
                      className={`text-xs rounded-full px-3 py-1.5 border font-medium transition-all
                    ${isCurrentlyStudying === false ? "border-slate-500 bg-slate-500 text-white" : "border-slate-300 text-slate-600 hover:bg-slate-50"}`}
                    >
                      Không
                    </button>
                  </div>
                  {isCurrentlyStudying && (
                    <>
                      <p className="text-xs text-slate-400">
                        Chọn phần mà bạn đang học, để hệ thống biết bạn có đang bị học lệch hay không.
                      </p>
                      <div className="space-y-1.5">
                        {analysis.topics.map((topic) => {
                          const isSelected = curriculumTopic === topic;
                          const dimmed = curriculumTopic !== null && !isSelected;
                          return (
                            <div key={topic}>
                              <button
                                type="button"
                                onClick={() => {
                                  if (isSelected) {
                                    setCurriculumTopic(null); setOnTrack(null);
                                    refreshSuggestedGoals({ curriculumTopic: null, onTrack: null });
                                  } else {
                                    setCurriculumTopic(topic); setOnTrack(null);
                                    // Chưa refresh ở đây — "on_track" (đã vững/bị hổng) mới là tín hiệu
                                    // thật sự có ý nghĩa, sẽ refresh khi người dùng bấm 1 trong 2 nút bên dưới.
                                  }
                                }}
                                className={`w-full flex items-center gap-2.5 text-left rounded-lg border px-3 py-2.5 text-sm transition-all
                          ${isSelected ? "border-indigo-500 bg-indigo-50" : "border-slate-200 hover:border-indigo-200"}
                          ${dimmed ? "opacity-35" : ""}`}
                              >
                                <span className={`inline-flex size-4 shrink-0 items-center justify-center rounded border-2
                          ${isSelected ? "border-indigo-500 bg-indigo-500" : "border-slate-300"}`}>
                                  {isSelected && <CheckCircle2 className="size-3 text-white" />}
                                </span>
                                <span className={isSelected ? "font-medium text-indigo-900" : "text-slate-700"}>{topic}</span>
                              </button>
                              {isSelected && (
                                <div className="mt-1.5 ml-1 flex flex-wrap items-center gap-2 rounded-lg bg-indigo-50/60 border border-indigo-100 px-3 py-2">
                                  <span className="text-xs text-indigo-700">Chương trình đã học đến đây — còn bạn thì sao?</span>
                                  <div className="flex gap-2 ml-auto">
                                    <button
                                      type="button"
                                      onClick={() => { setOnTrack(true); refreshSuggestedGoals({ onTrack: true }); }}
                                      className={`text-xs rounded-full px-3 py-1 border font-medium transition-all
                                ${onTrack === true ? "border-emerald-500 bg-emerald-500 text-white" : "border-emerald-300 text-emerald-700 hover:bg-emerald-50"}`}
                                    >
                                      Tôi đã học xong
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => { setOnTrack(false); refreshSuggestedGoals({ onTrack: false }); }}
                                      className={`text-xs rounded-full px-3 py-1 border font-medium transition-all
                                ${onTrack === false ? "border-amber-500 bg-amber-500 text-white" : "border-amber-300 text-amber-700 hover:bg-amber-50"}`}
                                    >
                                      Tôi bị mất gốc các phần trước đó
                                    </button>
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>
              )}
              {/* Minh chứng năng lực */}
              <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <FileText className="size-4 text-indigo-600" />
                  <h3 className="font-semibold text-slate-800">Minh chứng năng lực (không bắt buộc)</h3>
                </div>
                <p className="text-xs text-slate-400">Bảng điểm, chứng chỉ, hoặc bài kiểm tra bạn đã làm — giúp hệ thống đánh giá đúng năng lực hiện tại.</p>
                {!evidenceFile && !evidenceResult ? (
                  <label className="flex items-center justify-center gap-2 rounded-lg border-2 border-dashed border-slate-300 px-4 py-4 text-sm text-slate-500 cursor-pointer hover:border-indigo-300 hover:bg-slate-50 transition-all">
                    <Upload className="size-4" /> Chọn file minh chứng
                    <input
                      type="file"
                      className="hidden"
                      accept=".pdf,.docx,.txt,.jpg,.jpeg,.png"
                      onChange={(e) => { const f = e.target.files?.[0]; if (f) void handleEvidenceFile(f); }}
                    />
                  </label>
                ) : (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm">
                      <FileText className="size-4 text-slate-400 shrink-0" />
                      <span className="truncate flex-1">{evidenceFile?.name ?? "Đã xác thực trước đó (chuyển trang nên không hiện lại tên file)"}</span>
                      <button
                        type="button"
                        onClick={() => { setEvidenceFile(null); setEvidenceResult(null); setEvidenceError(""); }}
                        className="text-slate-400 hover:text-red-500 shrink-0"
                      >
                        <X className="size-4" />
                      </button>
                    </div>
                    {evidenceChecking && <p className="text-xs text-slate-400">Đang xác thực tài liệu...</p>}
                    {evidenceError && <p className="text-xs text-red-600">{evidenceError}</p>}
                    {evidenceResult?.is_competency_evidence && (
                      <div className="space-y-2">
                        <p className="text-xs text-emerald-600">
                          ✓ Đã xác thực: {
                            evidenceResult.evidence_type === "transcript" ? "Bảng điểm" :
                              evidenceResult.evidence_type === "certificate" ? "Chứng chỉ" :
                                evidenceResult.evidence_type === "exam" ? "Bài kiểm tra đã làm" : "Minh chứng năng lực"
                          }
                          {evidenceResult.evidence_subject ? ` — môn "${evidenceResult.evidence_subject}"` : ""}
                          {evidenceResult.score_summary ? ` (${evidenceResult.score_summary})` : ""}
                        </p>
                        {evidenceResult.subject_relationship === "same_subject" && (
                          <p className="text-xs text-indigo-600 bg-indigo-50 border border-indigo-100 rounded-lg px-2.5 py-1.5">
                            💡 Đây là minh chứng cho CHÍNH môn bạn đang tải lên — hệ thống hiểu là bạn có thể
                            đang muốn cải thiện/ôn lại chỗ chưa vững, không phải học lại từ đầu.
                            {evidenceResult.relationship_reason ? ` ${evidenceResult.relationship_reason}` : ""}
                          </p>
                        )}
                        {evidenceResult.subject_relationship === "related_prerequisite" && (
                          <p className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg px-2.5 py-1.5">
                            ✓ Đây là môn liên quan/tiên quyết — hệ thống sẽ dùng để đánh giá nền tảng sẵn có của bạn.
                            {evidenceResult.relationship_reason ? ` ${evidenceResult.relationship_reason}` : ""}
                          </p>
                        )}
                        {evidenceResult.subject_relationship === "unclear" && (
                          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-2.5 py-1.5">
                            ⚠ Hệ thống chưa chắc chắn minh chứng này có liên quan đến môn bạn đang học hay
                            không.{evidenceResult.relationship_reason ? ` ${evidenceResult.relationship_reason}` : ""} Hãy
                            kiểm tra lại, hoặc chọn file khác nếu thực ra không liên quan.
                          </p>
                        )}
                        {evidenceResult.evidence_type === "exam" && (
                          <div className="flex items-center gap-2">
                            <input
                              type="number"
                              placeholder="Điểm đạt được"
                              value={evidenceScore}
                              onChange={(e) => setEvidenceScore(e.target.value)}
                              className="w-28 rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                            />
                            <span className="text-slate-400">/</span>
                            <input
                              type="number"
                              placeholder="Điểm tối đa"
                              value={evidenceMaxScore}
                              onChange={(e) => setEvidenceMaxScore(e.target.value)}
                              className="w-28 rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                            />
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-5">
              {/* Mức độ học tập — bắt buộc, quyết định mốc thời gian tham chiếu + độ sâu hoạt động */}
              <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <Zap className="size-4 text-indigo-600" />
                  <h3 className="font-semibold text-slate-800">Mức độ học tập bạn hướng tới là gì? <span className="text-red-500">*</span></h3>
                </div>
                <p className="text-xs text-slate-400">
                  Chọn đúng mức độ giúp hệ thống ước lượng thời gian và gợi ý hoạt động học phù hợp — tránh lộ trình
                  quá nặng hoặc quá nhẹ so với nhu cầu thật của bạn.
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {STUDY_DEPTH_MODE_OPTIONS.map((opt) => {
                    const isSelected = studyDepthMode === opt.key;
                    return (
                      <button
                        key={opt.key}
                        type="button"
                        onClick={() => handleSelectStudyDepthMode(opt.key)}
                        className={`text-left rounded-xl border-2 px-3 py-2.5 text-sm transition-all
                      ${isSelected ? "border-indigo-500 bg-indigo-50" : "border-slate-200 hover:border-indigo-300 hover:bg-slate-50"}`}
                      >
                        <span className="flex items-center gap-2">
                          <span className={`inline-block size-3.5 shrink-0 rounded-full border-2
                        ${isSelected ? "border-indigo-500 bg-indigo-500" : "border-slate-300"}`} />
                          <span className={isSelected ? "font-medium text-indigo-900" : "font-medium text-slate-700"}>{opt.label}</span>
                        </span>
                        <span className="block text-xs text-slate-400 mt-1 ml-5">{opt.description}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Quỹ thời gian */}
              <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <Calendar className="size-4 text-indigo-600" />
                  <h3 className="font-semibold text-slate-800">Quỹ thời gian cho lộ trình</h3>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">Ngày bắt đầu (không bắt buộc, mặc định ngày mai)</label>
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">Hạn mục tiêu (không bắt buộc)</label>
                    <input
                      type="date"
                      value={deadline}
                      onChange={(e) => setDeadline(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                    />
                  </div>
                </div>
                {daysPerWeek < 7 && (
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">Cách xếp ngày học trong tuần</label>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setSchedulePattern("consecutive")}
                        className={`text-xs rounded-full px-3 py-1.5 border font-medium transition-all
                      ${schedulePattern === "consecutive" ? "border-indigo-500 bg-indigo-500 text-white" : "border-slate-300 text-slate-600 hover:bg-slate-50"}`}
                      >
                        Liên tục
                      </button>
                      <button
                        type="button"
                        onClick={() => setSchedulePattern("interleaved")}
                        className={`text-xs rounded-full px-3 py-1.5 border font-medium transition-all
                      ${schedulePattern === "interleaved" ? "border-indigo-500 bg-indigo-500 text-white" : "border-slate-300 text-slate-600 hover:bg-slate-50"}`}
                      >
                        Xen kẽ
                      </button>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">
                      {schedulePattern === "consecutive"
                        ? `Liên tục: học liền ${daysPerWeek} ngày đầu tuần (Thứ 2${daysPerWeek > 1 ? `–${["", "Hai", "Ba", "Tư", "Năm", "Sáu", "Bảy"][daysPerWeek]}` : ""}), phần còn lại nghỉ.`
                        : "Xen kẽ: dàn đều các ngày học ra khắp tuần thay vì gộp liền nhau."}
                    </p>
                  </div>
                )}
                {deadline && (() => {
                  const days = Math.ceil((new Date(deadline).getTime() - Date.now()) / 86_400_000);
                  return days > 0 ? null : <p className="text-xs text-red-500">Ngày đã chọn ở trong quá khứ, vui lòng chọn lại.</p>;
                })()}
                {!studyDepthMode && analysis.reading_time && (
                  <p className="text-xs text-slate-400">Chọn "Mức độ học tập" ở trên để xem ước lượng thời gian phù hợp.</p>
                )}
                {studyDepthMode && (() => {
                  // Gắn ước lượng thời gian đọc (Layer 0, tính bằng code — xem estimate_reading_time
                  // ở backend) với ĐÚNG mức độ học tập + lựa chọn phút/ngày, số ngày/tuần và hạn mục
                  // tiêu hiện tại của người dùng, thay vì luôn dùng mức sâu nhất tách rời như trước.
                  // Dù kết quả là "căng" hay "chill", lộ trình vẫn luôn được tạo — chỉ đổi giọng điệu.
                  const rt = analysis.reading_time;
                  if (!rt) return null;
                  const { min: lo, max: hi } = readingRangeFor(rt, studyDepthMode);
                  if (!lo && !hi) return null;
                  const paceVerb = STUDY_DEPTH_MODE_OPTIONS.find((o) => o.key === studyDepthMode)!.paceVerb;

                  let tone: "neutral" | "chill" | "comfortable" | "tight" | "very_tight";
                  let text: string;

                  if (!deadline || new Date(deadline).getTime() <= Date.now()) {
                    const weeksMin = Math.max(1, Math.round(Math.ceil(lo / minutesPerDay) / daysPerWeek));
                    const weeksMax = Math.max(1, Math.round(Math.ceil(hi / minutesPerDay) / daysPerWeek));
                    tone = "neutral";
                    text = `Với nhịp hiện tại ${minutesPerDay} phút/ngày, ${daysPerWeek} ngày/tuần: ước tính khoảng ${weeksMin === weeksMax ? weeksMin : `${weeksMin}-${weeksMax}`} tuần để ${paceVerb} toàn bộ tài liệu.`;
                  } else {
                    // Công thức tính giống HỆT backend (generate_learning_roadmap) để số hiển thị ở
                    // đây luôn khớp với lộ trình thực tế sẽ được tạo. budgetMinutes/hi chính là tỉ lệ
                    // "time spent / time needed" của Carroll's Model of School Learning (Carroll, J.B.
                    // 1963, "A Model of School Learning", Teachers College Record 64(8)) — 4 mức
                    // chill/comfortable/tight/very_tight bên dưới chỉ là các bậc rời rạc hóa của đúng
                    // tỉ lệ này, không phải quy tắc tùy ý.
                    const daysAvailable = Math.max(1, Math.ceil((new Date(deadline).getTime() - Date.now()) / 86_400_000));
                    const fullWeeks = Math.floor(daysAvailable / 7);
                    const remainder = daysAvailable % 7;
                    const sessions = fullWeeks * daysPerWeek + Math.min(daysPerWeek, remainder);
                    const budgetMinutes = sessions * minutesPerDay;
                    const fmt = (n: number) => n.toLocaleString("vi-VN");

                    if (budgetMinutes >= hi * 1.4) {
                      tone = "chill";
                      text = `Bạn có khoảng ${fmt(budgetMinutes)} phút tới hạn — khá dư dả so với mức ${lo}-${hi} phút cần để ${paceVerb} tài liệu này. Nhịp học đang khá "chill", có thể dùng thời gian dư để đào sâu/luyện thêm.`;
                    } else if (budgetMinutes >= hi) {
                      tone = "comfortable";
                      text = `Bạn có khoảng ${fmt(budgetMinutes)} phút tới hạn — vừa đủ so với mức ${lo}-${hi} phút cần để ${paceVerb} tài liệu này.`;
                    } else if (budgetMinutes >= lo) {
                      tone = "tight";
                      text = `Bạn có khoảng ${fmt(budgetMinutes)} phút tới hạn, hơi ít so với mức ${lo}-${hi} phút — nhịp học đang hơi "căng", vẫn khả thi nhưng cần tập trung, ít trì hoãn.`;
                    } else {
                      tone = "very_tight";
                      text = `Bạn chỉ có khoảng ${fmt(budgetMinutes)} phút tới hạn, trong khi cần tối thiểu khoảng ${lo} phút — nhịp này khá "căng", có nguy cơ không kịp. Cân nhắc tăng phút/ngày, thêm ngày/tuần, hoặc dời hạn.`;
                    }
                  }

                  const toneClass: Record<typeof tone, string> = {
                    neutral: "text-indigo-600",
                    chill: "text-emerald-600",
                    comfortable: "text-indigo-600",
                    tight: "text-amber-600",
                    very_tight: "text-red-600",
                  };
                  return <p className={`text-xs ${toneClass[tone]}`}>{text}</p>;
                })()}
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
                <div className="flex items-center gap-2">
                  <Target className="size-4 text-indigo-600" />
                  <h3 className="font-semibold text-slate-800">Mục tiêu học tập của bạn là gì?</h3>
                  {refreshingGoals && (
                    <span className="ml-auto inline-flex items-center gap-1 text-xs text-indigo-500">
                      <Loader2 className="size-3 animate-spin" /> đang cập nhật gợi ý mục tiêu...
                    </span>
                  )}
                </div>

                {!studyDepthMode ? (
                  <div className="flex items-center gap-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-400">
                    <Lock className="size-4 shrink-0" />
                    Chọn "Mức độ học tập" ở trên để hệ thống gợi ý mục tiêu phù hợp với đúng nhu cầu của bạn.
                  </div>
                ) : (
                  <div className="grid gap-2 sm:grid-cols-2">
                    {(() => {
                      const merged = [...suggestedGoals];
                      // Gợi ý có thể đổi sau khi refresh — nếu goal đã chọn bị rớt khỏi danh sách mới,
                      // vẫn giữ hiển thị + highlight để không làm mất lựa chọn của người dùng.
                      if (selectedGoal && !merged.includes(selectedGoal)) merged.unshift(selectedGoal);
                      return merged;
                    })().map((goal) => {
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
                    {suggestedGoals.length === 0 && !refreshingGoals && (
                      <p className="text-xs text-slate-400 col-span-2">Chưa có gợi ý — hãy nhập mục tiêu của riêng bạn bên dưới.</p>
                    )}
                  </div>
                )}

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
            </div>
          </div>

          <div className="flex gap-3">
            {quiz.length === 0 && (
              <Button variant="secondary" onClick={() => setScreen("upload_and_info")}>Quay lại</Button>
            )}
            <Button onClick={handleContinueFromGoalStep} isLoading={loading} className="flex-1" disabled={!effectiveGoal || !studyDepthMode}>
              {loading
                ? loadingMsg
                : quiz.length > 0
                  ? <><ArrowRight className="size-4" /> Tiếp tục bài kiểm tra</>
                  : <><BrainCircuit className="size-4" /> Tạo bài kiểm tra nhanh</>}
            </Button>
          </div>
          {(!effectiveGoal || !studyDepthMode) && (
            <p className="text-xs text-slate-400 text-center">
              {!studyDepthMode ? "Chọn mức độ học tập để tiếp tục" : "Chọn hoặc nhập mục tiêu để tiếp tục"}
            </p>
          )}
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
              <Button onClick={handleFinishQuiz} className="w-full" disabled={Object.keys(answers).length < quiz.length}>
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
              {error && (
                <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                  <AlertCircle className="size-4 shrink-0 mt-0.5 text-red-500" />
                  <p>{error}</p>
                </div>
              )}
              <div className="flex gap-3">
                <Button variant="secondary" onClick={() => setScreen("goal_selection")} disabled={loading}>
                  Quay lại chỉnh thông tin
                </Button>
                <Button onClick={handleGenerateRoadmap} isLoading={loading} className="flex-1">
                  {loading ? loadingMsg : <><Flag className="size-4" /> Tạo lộ trình học</>}
                </Button>
              </div>
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
        onBack={() => { }}
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
