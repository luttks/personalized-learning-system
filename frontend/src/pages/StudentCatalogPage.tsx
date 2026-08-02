import axios from "axios";
import {
  BookOpen,
  ClipboardCheck,
  CalendarDays,
  ChevronDown,
  Clock3,
  FileText,
  Layers3,
  Network,
  Save,
  Target,
  Route,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import {
  getLearnerCourseProfile,
  getPublishedCourse,
  getPublishedCourses,
  saveLearnerCourseProfile,
  startCourseDiagnostic,
  submitCourseDiagnostic,
  createCourseLearningPath,
  getLatestCourseLearningPath,
} from "../api/catalog";
import { Button, EmptyState, Field, Input, LoadingState, Notice, PageHeader, Textarea } from "../components/ui";
import type {
  LearnerCourseProfile,
  LearnerCourseProfilePayload,
  DiagnosticAttempt,
  DiagnosticResult,
  CourseLearningPath,
  PublishedCourseDetail,
  PublishedCourseSummary,
} from "../types/course";

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return error.response?.data?.detail ?? "Không thể tải catalog khóa học.";
  }
  return "Không thể tải catalog khóa học.";
}

function Count({ value, label }: { value: number; label: string }) {
  return (
    <div className="min-w-0">
      <p className="text-lg font-bold text-slate-950">{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}

function sameContent(left: string, right: string): boolean {
  const normalize = (value: string) => value.trim().toLocaleLowerCase("vi-VN").replace(/\s+/g, " ");
  return normalize(left) === normalize(right);
}

function isoDate(offsetDays = 0): string {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  return value.toISOString().slice(0, 10);
}

const initialOnboarding: LearnerCourseProfilePayload = {
  learning_goal: "",
  start_date: isoDate(),
  deadline: isoDate(90),
  minutes_per_day: 45,
  days_per_week: 4,
  available_periods: ["evening"],
  content_formats: ["reading"],
};

export function StudentCatalogPage() {
  const [courses, setCourses] = useState<PublishedCourseSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<PublishedCourseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const rows = await getPublishedCourses();
        setCourses(rows);
        setSelectedId(rows[0]?.id ?? null);
      } catch (requestError) {
        setError(errorMessage(requestError));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let active = true;
    setDetailLoading(true);
    setError(null);
    void getPublishedCourse(selectedId)
      .then((row) => active && setDetail(row))
      .catch((requestError) => active && setError(errorMessage(requestError)))
      .finally(() => active && setDetailLoading(false));
    return () => {
      active = false;
    };
  }, [selectedId]);

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Catalog khóa học"
        description="Các khóa học đã được quản trị viên kiểm duyệt và publish."
      />
      {error && <Notice>{error}</Notice>}
      {courses.length === 0 ? (
        <EmptyState>Chưa có khóa học nào được publish.</EmptyState>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
          <aside className="border-r border-slate-200 pr-0 lg:pr-5">
            <p className="mb-3 text-xs font-semibold uppercase text-slate-500">Khóa học khả dụng</p>
            <div className="space-y-2">
              {courses.map((course) => (
                <button
                  key={course.id}
                  type="button"
                  onClick={() => setSelectedId(course.id)}
                  className={`w-full rounded-lg border p-3 text-left transition ${
                    selectedId === course.id
                      ? "border-emerald-600 bg-emerald-50"
                      : "border-slate-200 bg-white hover:border-slate-300"
                  }`}
                >
                  <p className="break-words text-sm font-semibold text-slate-900">{course.title}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {course.subject} · Lớp {course.grade_level}
                  </p>
                  <p className="mt-2 text-xs font-medium text-emerald-700">
                    Publication {course.publication_revision}
                  </p>
                </button>
              ))}
            </div>
          </aside>

          <section className="min-w-0">
            {detailLoading ? <LoadingState /> : detail ? <CourseDetail detail={detail} /> : null}
          </section>
        </div>
      )}
    </div>
  );
}

function CourseDetail({ detail }: { detail: PublishedCourseDetail }) {
  const [onboarding, setOnboarding] = useState<LearnerCourseProfilePayload>(initialOnboarding);
  const [savedProfile, setSavedProfile] = useState<LearnerCourseProfile | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [profileSuccess, setProfileSuccess] = useState("");

  useEffect(() => {
    setSavedProfile(null);
    setOnboarding(initialOnboarding);
    setProfileError("");
    void getLearnerCourseProfile(detail.id)
      .then((profile) => {
        setSavedProfile(profile);
        setOnboarding(profile);
      })
      .catch((requestError) => {
        if (!axios.isAxiosError(requestError) || requestError.response?.status !== 404) {
          setProfileError(errorMessage(requestError));
        }
      });
  }, [detail.id]);

  function toggleChoice(field: "available_periods" | "content_formats", value: string) {
    setOnboarding((current) => ({
      ...current,
      [field]: current[field].includes(value)
        ? current[field].filter((item) => item !== value)
        : [...current[field], value],
    }));
  }

  async function handleOnboardingSubmit(event: FormEvent) {
    event.preventDefault();
    setProfileError("");
    setProfileSuccess("");
    if (onboarding.deadline < onboarding.start_date) {
      setProfileError("Deadline không được trước ngày bắt đầu.");
      return;
    }
    if (!onboarding.available_periods.length || !onboarding.content_formats.length) {
      setProfileError("Hãy chọn ít nhất một khung giờ và một định dạng học.");
      return;
    }
    setSaving(true);
    try {
      const profile = await saveLearnerCourseProfile(detail.id, onboarding);
      setSavedProfile(profile);
      setOnboarding(profile);
      setProfileSuccess("Đã lưu mục tiêu và lịch học cho khóa học.");
    } catch (requestError) {
      setProfileError(errorMessage(requestError));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="border-b border-slate-200 pb-5">
        <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-emerald-700">
          <BookOpen className="size-4" />
          {detail.subject} · Lớp {detail.grade_level} · Revision {detail.publication_revision}
        </div>
        <h2 className="mt-2 break-words text-xl font-bold text-slate-950">{detail.title}</h2>
        {detail.description && <p className="mt-2 text-sm text-slate-600">{detail.description}</p>}
        <div className="mt-5 grid grid-cols-2 gap-4 border-y border-slate-200 py-4 sm:grid-cols-4">
          <Count value={detail.document_count} label="Tài liệu" />
          <Count value={detail.chapter_count} label="Chương" />
          <Count value={detail.lesson_count} label="Bài học" />
          <Count value={detail.concept_count} label="Concept" />
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-slate-600">
            {savedProfile ? `Onboarding phiên bản ${savedProfile.profile_version}` : "Chưa thiết lập mục tiêu cho khóa học"}
          </p>
          <Button type="button" variant="secondary" onClick={() => setShowOnboarding((value) => !value)}>
            <Target className="size-4" /> {showOnboarding ? "Đóng onboarding" : savedProfile ? "Cập nhật onboarding" : "Thiết lập onboarding"}
          </Button>
        </div>
      </div>

      {showOnboarding && (
        <OnboardingForm
          value={onboarding}
          stale={savedProfile?.stale ?? false}
          saving={saving}
          error={profileError}
          success={profileSuccess}
          onChange={setOnboarding}
          onToggle={toggleChoice}
          onSubmit={handleOnboardingSubmit}
        />
      )}

      <DiagnosticPanel courseId={detail.id} onboardingReady={Boolean(savedProfile && !savedProfile.stale)} />
      <LearningPathPanel courseId={detail.id} onboardingReady={Boolean(savedProfile && !savedProfile.stale)} />

      <div className="space-y-3">
        {detail.versions.map((version, versionIndex) => {
          const newest = versionIndex === detail.versions.length - 1;
          return (
          <details key={version.course_version_id} className="rounded-lg border border-slate-200 bg-white" open={newest}>
            <summary className="flex cursor-pointer list-none items-start justify-between gap-3 p-4">
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <FileText className="size-4 shrink-0 text-emerald-700" />
                  <span className="break-words">Version {version.version_number} · {version.original_name}</span>
                  {newest && <span className="shrink-0 rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800">Mới nhất</span>}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {version.chapter_count} chương · {version.lesson_count} bài · {version.concept_count} concept · {version.chunk_count} chunks
                </p>
              </div>
              <ChevronDown className="size-4 shrink-0 text-slate-400" />
            </summary>
            <div className="space-y-5 border-t border-slate-200 p-4">
              {version.chapters.map((chapter, chapterIndex) => (
                <div key={chapter.id} className="border-l-2 border-emerald-600 pl-4">
                  <p className="text-xs font-semibold text-emerald-700">Chương {chapterIndex + 1}</p>
                  <h3 className="mt-1 break-words text-base font-bold text-slate-900">{chapter.title}</h3>
                  <p className="mt-1 text-sm text-slate-600">{chapter.summary}</p>
                  <div className="mt-3 space-y-3">
                    {chapter.lessons.map((lesson, lessonIndex) => (
                      <div key={lesson.id} className="rounded-lg bg-slate-50 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-slate-900">
                            Bài {lessonIndex + 1}. {lesson.title}
                          </p>
                          <span className="flex items-center gap-1 text-xs text-slate-500">
                            <Layers3 className="size-3.5" /> {lesson.chunk_count} chunks
                          </span>
                        </div>
                        {!sameContent(lesson.summary, chapter.summary) && (
                          <p className="mt-1 text-sm text-slate-600">{lesson.summary}</p>
                        )}
                        <div className="mt-3 space-y-2">
                          {lesson.concepts.map((concept) => (
                            <div key={concept.id} className="border-t border-slate-200 pt-2">
                              <p className="text-sm font-medium text-slate-900">{concept.title}</p>
                              {!sameContent(concept.description, chapter.summary) &&
                                !sameContent(concept.description, lesson.summary) &&
                                !sameContent(concept.description, concept.title) && (
                                  <p className="mt-1 text-xs text-slate-600">{concept.description}</p>
                                )}
                              <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                                <span className="flex items-center gap-1"><Clock3 className="size-3.5" />{concept.estimated_minutes} phút</span>
                                {concept.prerequisite_keys.length > 0 && (
                                  <span className="flex items-center gap-1"><Network className="size-3.5" />{concept.prerequisite_keys.length} tiên quyết</span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </details>
          );
        })}
      </div>
    </div>
  );
}

function LearningPathPanel({ courseId, onboardingReady }: { courseId: string; onboardingReady: boolean }) {
  const [path, setPath] = useState<CourseLearningPath | null>(null);
  const [requiredMastery, setRequiredMastery] = useState(0.7);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setPath(null);
    setError("");
    void getLatestCourseLearningPath(courseId)
      .then(setPath)
      .catch((requestError) => {
        if (!axios.isAxiosError(requestError) || requestError.response?.status !== 404) {
          setError(errorMessage(requestError));
        }
      });
  }, [courseId]);

  async function generate() {
    setBusy(true);
    setError("");
    try {
      setPath(await createCourseLearningPath(courseId, requiredMastery));
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-4 border-y border-slate-200 py-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h3 className="flex items-center gap-2 font-bold text-slate-950"><Route className="size-5 text-emerald-700" /> Lộ trình đề xuất</h3>
          <p className="mt-1 text-sm text-slate-500">Lập kế hoạch từ onboarding, diagnostic mastery và prerequisite.</p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm font-medium text-slate-700">
            Mastery {Math.round(requiredMastery * 100)}%
            <input className="mt-2 block h-2 w-36 accent-emerald-700" type="range" min={0.3} max={1} step={0.05} value={requiredMastery} onChange={(event) => setRequiredMastery(Number(event.target.value))} />
          </label>
          <Button type="button" disabled={!onboardingReady} isLoading={busy} onClick={() => void generate()}><Route className="size-4" /> {path ? "Tạo phiên bản mới" : "Tạo lộ trình"}</Button>
        </div>
      </div>
      {error && <Notice>{error}</Notice>}
      {!onboardingReady && <p className="text-sm text-slate-500">Hoàn thành onboarding và bài chẩn đoán để tạo lộ trình.</p>}
      {path && (
        <div>
          {path.stale && <Notice tone="info">Lộ trình này đã cũ do publication thay đổi. Hãy tạo phiên bản mới.</Notice>}
          <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
            <div><p className="text-xs font-semibold uppercase text-emerald-700">Version {path.path_version} · {path.status}</p><h4 className="mt-1 text-lg font-bold text-slate-950">{path.title}</h4><p className="mt-1 text-sm text-slate-600">{path.summary}</p></div>
            <div className="text-right text-sm text-slate-600"><p>{path.total_estimated_minutes} phút</p><p>{path.items.length} phiên · {path.skipped.length} concept đã đạt</p></div>
          </div>
          <ol className="mt-5 border-l-2 border-emerald-200 pl-5">
            {path.items.map((item) => (
              <li key={`${item.sequence}-${item.concept_id}`} className="relative pb-5 last:pb-0">
                <span className="absolute -left-[25px] top-1 size-2.5 rounded-full bg-emerald-600" />
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0"><p className="font-semibold text-slate-900">Phiên {item.session_number}. {item.title}</p><p className="mt-1 text-sm text-slate-600">{item.instructions}</p></div>
                  <span className="flex shrink-0 items-center gap-1 text-xs text-slate-500"><CalendarDays className="size-3.5" />{new Date(item.planned_date).toLocaleDateString("vi-VN")} · {item.estimated_minutes} phút</span>
                </div>
                <p className="mt-2 text-xs text-slate-500">{item.activity_type} · {item.source_chunk_ids.length} nguồn RAG</p>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}

function DiagnosticPanel({ courseId, onboardingReady }: { courseId: string; onboardingReady: boolean }) {
  const [attempt, setAttempt] = useState<DiagnosticAttempt | null>(null);
  const [answers, setAnswers] = useState<number[]>([]);
  const [result, setResult] = useState<DiagnosticResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setAttempt(null);
    setAnswers([]);
    setResult(null);
    setError("");
  }, [courseId]);

  async function start() {
    setBusy(true);
    setError("");
    try {
      const next = await startCourseDiagnostic(courseId);
      setAttempt(next);
      setAnswers(Array(next.questions.length).fill(-1));
      setResult(null);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!attempt || answers.some((answer) => answer < 0)) {
      setError("Hãy trả lời tất cả câu hỏi trước khi nộp bài.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      setResult(await submitCourseDiagnostic(attempt.attempt_id, answers, crypto.randomUUID()));
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  if (!onboardingReady) {
    return (
      <div className="border-y border-slate-200 py-5">
        <p className="flex items-center gap-2 font-semibold text-slate-900"><ClipboardCheck className="size-5 text-emerald-700" /> Bài chẩn đoán</p>
        <p className="mt-1 text-sm text-slate-500">Hoàn thành onboarding để mở bài chẩn đoán của khóa học.</p>
      </div>
    );
  }

  return (
    <section className="space-y-4 border-y border-slate-200 py-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 font-bold text-slate-950"><ClipboardCheck className="size-5 text-emerald-700" /> Bài chẩn đoán</h3>
          <p className="mt-1 text-sm text-slate-500">Đánh giá kiến thức hiện tại trước khi tạo lộ trình.</p>
        </div>
        {!attempt && <Button type="button" isLoading={busy} onClick={() => void start()}>Bắt đầu chẩn đoán</Button>}
      </div>
      {error && <Notice>{error}</Notice>}
      {attempt && !result && (
        <div className="space-y-5">
          <p className="text-sm font-medium text-slate-700">Assessment {attempt.assessment_version} · {attempt.questions.length} câu</p>
          {attempt.questions.map((question, questionIndex) => (
            <fieldset key={question.id} className="space-y-2 border-t border-slate-200 pt-4">
              <p className="text-xs font-semibold text-emerald-700">{question.lesson_title}</p>
              <legend className="text-sm font-semibold text-slate-900">Câu {questionIndex + 1}. {question.prompt}</legend>
              <p className="text-xs text-slate-500">Nguồn: {question.source_label}</p>
              {question.options.map((option, optionIndex) => (
                <label key={optionIndex} className="flex min-h-10 items-start gap-3 rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-700">
                  <input type="radio" name={question.id} checked={answers[questionIndex] === optionIndex} onChange={() => setAnswers((current) => current.map((answer, index) => index === questionIndex ? optionIndex : answer))} className="mt-0.5 size-4 accent-emerald-700" />
                  <span>{option}</span>
                </label>
              ))}
            </fieldset>
          ))}
          <div className="flex justify-end"><Button type="button" isLoading={busy} onClick={() => void submit()}><ClipboardCheck className="size-4" /> Nộp bài</Button></div>
        </div>
      )}
      {result && (
        <div>
          <p className="text-2xl font-bold text-slate-950">{result.score}%</p>
          <p className="text-sm text-slate-600">Đúng {result.correct_count}/{result.question_count} câu</p>
          <div className="mt-4 divide-y divide-slate-200 border-y border-slate-200">
            {result.results.map((item) => <div key={item.concept_id} className="flex items-center justify-between gap-3 py-3 text-sm"><span>{item.concept_title}</span><span className={item.correct ? "font-semibold text-emerald-700" : "font-semibold text-red-600"}>{item.correct ? "Đúng" : "Chưa đúng"}</span></div>)}
          </div>
          <div className="mt-4 flex justify-end"><Button type="button" variant="secondary" onClick={() => { setAttempt(null); setResult(null); }}>Làm bài mới</Button></div>
        </div>
      )}
    </section>
  );
}

const periodOptions = [
  ["morning", "Buổi sáng"],
  ["afternoon", "Buổi chiều"],
  ["evening", "Buổi tối"],
] as const;
const formatOptions = [
  ["reading", "Đọc nội dung"],
  ["video", "Video"],
  ["practice", "Bài tập"],
  ["quiz", "Câu hỏi nhanh"],
] as const;

function OnboardingForm({ value, stale, saving, error, success, onChange, onToggle, onSubmit }: {
  value: LearnerCourseProfilePayload;
  stale: boolean;
  saving: boolean;
  error: string;
  success: string;
  onChange: (value: LearnerCourseProfilePayload) => void;
  onToggle: (field: "available_periods" | "content_formats", value: string) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <form onSubmit={onSubmit} className="space-y-5 border-y border-slate-200 py-5">
      <div>
        <h3 className="text-lg font-bold text-slate-950">Mục tiêu và lịch học</h3>
        <p className="mt-1 text-sm text-slate-500">Thông tin này được dùng để tạo chẩn đoán và lộ trình cho đúng khóa học.</p>
      </div>
      {stale && <Notice tone="info">Khóa học đã có publication mới. Lưu lại để đồng bộ hồ sơ với nội dung mới nhất.</Notice>}
      {error && <Notice>{error}</Notice>}
      {success && <Notice tone="success">{success}</Notice>}
      <Field label="Mục tiêu học tập">
        <Textarea className="min-h-28" value={value.learning_goal} minLength={10} maxLength={5000} required onChange={(event) => onChange({ ...value, learning_goal: event.target.value })} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Ngày bắt đầu"><Input type="date" value={value.start_date} required onChange={(event) => onChange({ ...value, start_date: event.target.value })} /></Field>
        <Field label="Deadline"><Input type="date" min={value.start_date} value={value.deadline} required onChange={(event) => onChange({ ...value, deadline: event.target.value })} /></Field>
        <Field label="Số phút mỗi ngày"><Input type="number" min={10} max={600} value={value.minutes_per_day} required onChange={(event) => onChange({ ...value, minutes_per_day: Number(event.target.value) })} /></Field>
        <Field label="Số ngày mỗi tuần"><Input type="number" min={1} max={7} value={value.days_per_week} required onChange={(event) => onChange({ ...value, days_per_week: Number(event.target.value) })} /></Field>
      </div>
      <ChoiceGroup label="Khung giờ có thể học" options={periodOptions} selected={value.available_periods} onToggle={(choice) => onToggle("available_periods", choice)} />
      <ChoiceGroup label="Định dạng học ưu tiên" options={formatOptions} selected={value.content_formats} onToggle={(choice) => onToggle("content_formats", choice)} />
      <div className="flex justify-end"><Button type="submit" isLoading={saving}><Save className="size-4" /> Lưu onboarding</Button></div>
    </form>
  );
}

function ChoiceGroup({ label, options, selected, onToggle }: {
  label: string;
  options: readonly (readonly [string, string])[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium text-slate-700">{label}</legend>
      <div className="flex flex-wrap gap-3">
        {options.map(([value, text]) => (
          <label key={value} className="flex min-h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700">
            <input type="checkbox" checked={selected.includes(value)} onChange={() => onToggle(value)} className="size-4 accent-emerald-700" /> {text}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
