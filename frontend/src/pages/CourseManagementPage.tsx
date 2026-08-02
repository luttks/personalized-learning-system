import {
  BookOpen,
  CheckCircle2,
  CloudUpload,
  Database,
  FileText,
  Eye,
  ListTree,
  Pencil,
  Save,
  Search,
  Trash2,
  RefreshCw,
  Send,
  Upload,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";

import { getApiErrorMessage } from "../api/client";
import {
  createCourse,
  buildCourseCatalog,
  buildCourseQualityGate,
  deleteCourse,
  deleteDocumentVersion,
  getCourseDocuments,
  getCourseCatalog,
  getCourseQualityGate,
  getDocumentPreview,
  getCourses,
  getDocumentAnalysis,
  getDocumentJob,
  getRagIndex,
  publishCourse,
  rebuildRagIndex,
  retryDocumentJob,
  saveDocumentEdit,
  saveDocumentAnalysis,
  saveCourseCatalog,
  searchRagIndex,
  unpublishCourse,
  uploadCourseDocument,
} from "../api/courses";
import {
  Button,
  EmptyState,
  Field,
  Input,
  LoadingState,
  Notice,
  PageHeader,
  Textarea,
} from "../components/ui";
import type {
  Course,
  CourseCreatePayload,
  CourseCatalog,
  CourseQualityGate,
  DocumentAnalysis,
  DocumentJob,
  DocumentStructure,
  RagIndex,
  RagSearchResponse,
} from "../types/course";
import { useAuth } from "../auth/useAuth";

const initialForm: CourseCreatePayload = {
  title: "",
  subject: "",
  grade_level: 8,
  description: null,
};

const terminalStatuses = new Set(["completed", "failed"]);
const statusLabels: Record<string, string> = {
  draft: "Bản nháp",
  queued: "Đang chờ xử lý",
  processing: "Đang xác minh file",
  verifying: "Đang xác minh file",
  ready_for_analysis: "Đã nhận, chờ phân tích",
  analyzing: "Đang phân tích nội dung",
  completed: "Đã phân tích nội dung",
  failed: "Xử lý thất bại",
};

export function CourseManagementPage() {
  const { user } = useAuth();
  const [courses, setCourses] = useState<Course[]>([]);
  const [form, setForm] = useState(initialForm);
  const [selectedCourseId, setSelectedCourseId] = useState("");
  const [job, setJob] = useState<DocumentJob | null>(null);
  const [analysis, setAnalysis] = useState<DocumentAnalysis | null>(null);
  const [documents, setDocuments] = useState<import("../types/course").CourseDocumentItem[]>([]);
  const [preview, setPreview] = useState<import("../types/course").DocumentPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [deletingId, setDeletingId] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadCourses = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getCourses();
      setCourses(result);
      setSelectedCourseId((current) => current || result[0]?.id || "");
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể tải danh sách khóa học."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCourses();
  }, [loadCourses]);

  useEffect(() => {
    if (!job || terminalStatuses.has(job.status)) return;
    const timer = window.setInterval(() => {
      void getDocumentJob(job.id)
        .then(setJob)
        .catch((requestError) => setError(getApiErrorMessage(requestError, "Không thể đọc trạng thái xử lý.")));
    }, 2000);
    return () => window.clearInterval(timer);
  }, [job]);

  useEffect(() => {
    if (!selectedCourseId) return;
    void getCourseDocuments(selectedCourseId)
      .then(setDocuments)
      .catch((requestError) => setError(getApiErrorMessage(requestError, "Không thể tải kho tài liệu.")));
  }, [selectedCourseId, job?.status]);

  useEffect(() => {
    if (!job || job.status !== "completed") return;
    void getDocumentAnalysis(job.course_version_id)
      .then(setAnalysis)
      .catch((requestError) => setError(getApiErrorMessage(requestError, "Không thể tải bản phân tích.")));
  }, [job]);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const course = await createCourse(form);
      setCourses((current) => [course, ...current]);
      setSelectedCourseId(course.id);
      setForm(initialForm);
      setSuccess(`Đã tạo khóa học "${course.title}" ở trạng thái bản nháp.`);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể tạo khóa học."));
    } finally {
      setSaving(false);
    }
  }

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !selectedCourseId) return;
    setUploading(true);
    setError("");
    setSuccess("");
    void uploadCourseDocument(selectedCourseId, file)
      .then((result) => {
        setJob(result.job);
        setAnalysis(null);
        setPreview(null);
        setSuccess(`Đã nhận ${result.document.original_name} và đưa vào hàng đợi.`);
      })
      .catch((requestError) => setError(getApiErrorMessage(requestError, "Không thể upload tài liệu.")))
      .finally(() => setUploading(false));
  }

  async function handleRetry() {
    if (!job) return;
    setRetrying(true);
    setError("");
    setSuccess("");
    try {
      const retriedJob = await retryDocumentJob(job.id);
      setJob(retriedJob);
      setAnalysis(null);
      setSuccess("Đã đưa tài liệu vào hàng đợi OCR lại.");
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể thử xử lý lại tài liệu."));
    } finally {
      setRetrying(false);
    }
  }

  async function handleDeleteCourse(course: Course) {
    if (!window.confirm(`Xóa vĩnh viễn khóa học "${course.title}" và toàn bộ tài liệu bên trong?`)) return;
    setDeletingId(course.id);
    setError("");
    try {
      await deleteCourse(course.id);
      const remaining = courses.filter((item) => item.id !== course.id);
      setCourses(remaining);
      if (selectedCourseId === course.id) {
        setSelectedCourseId(remaining[0]?.id ?? "");
        setDocuments([]);
        setPreview(null);
        setJob(null);
        setAnalysis(null);
      }
      setSuccess(`Đã xóa khóa học "${course.title}".`);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể xóa khóa học."));
    } finally {
      setDeletingId("");
    }
  }

  async function handleDeleteDocument(item: import("../types/course").CourseDocumentItem) {
    if (!window.confirm(`Xóa vĩnh viễn Version ${item.version.version_number} - ${item.document.original_name}?`)) return;
    setDeletingId(item.version.id);
    setError("");
    try {
      await deleteDocumentVersion(item.version.id);
      setDocuments((current) => current.filter((entry) => entry.version.id !== item.version.id));
      if (preview?.version.id === item.version.id) setPreview(null);
      if (job?.course_version_id === item.version.id) setJob(null);
      setSuccess(`Đã xóa ${item.document.original_name}.`);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể xóa tài liệu."));
    } finally {
      setDeletingId("");
    }
  }

  const selectedCourse = courses.find((course) => course.id === selectedCourseId);

  return (
    <div className="space-y-7">
      <PageHeader
        title="Khóa học và tài liệu"
        description="Tạo bản nháp, upload tài liệu và theo dõi bước xác minh file."
        actions={<Button variant="secondary" onClick={() => void loadCourses()}><RefreshCw className="size-4" /> Làm mới</Button>}
      />
      {error && <Notice>{error}</Notice>}
      {success && <Notice tone="success" onClose={() => setSuccess("")}>{success}</Notice>}

      <section className="grid gap-8 xl:grid-cols-[360px_minmax(0,1fr)]">
        <form className="h-fit rounded-lg border border-slate-200 bg-white p-5" onSubmit={handleCreate}>
          <h2 className="flex items-center gap-2 font-bold text-slate-900"><BookOpen className="size-5 text-emerald-700" /> Khóa học mới</h2>
          <div className="mt-5 space-y-4">
            <Field label="Tên khóa học"><Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} maxLength={255} required /></Field>
            <Field label="Môn học"><Input value={form.subject} onChange={(event) => setForm({ ...form, subject: event.target.value })} maxLength={150} required /></Field>
            <Field label="Khối lớp"><Input type="number" min={1} max={12} value={form.grade_level} onChange={(event) => setForm({ ...form, grade_level: Number(event.target.value) })} required /></Field>
            <Field label="Mô tả"><Textarea value={form.description ?? ""} onChange={(event) => setForm({ ...form, description: event.target.value || null })} maxLength={5000} /></Field>
            <Button className="w-full" type="submit" isLoading={saving}><BookOpen className="size-4" /> Tạo bản nháp</Button>
          </div>
        </form>

        <div className="min-w-0">
          {loading ? <LoadingState /> : courses.length === 0 ? (
            <EmptyState>Chưa có khóa học. Hãy tạo bản nháp đầu tiên.</EmptyState>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full min-w-[680px] text-left text-sm">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                  <tr><th className="px-4 py-3 font-semibold">Khóa học</th><th className="px-4 py-3 font-semibold">Môn/khối</th><th className="px-4 py-3 font-semibold">Trạng thái</th><th className="px-4 py-3 font-semibold">Tài liệu</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {courses.map((course) => (
                    <tr key={course.id} className={`cursor-pointer hover:bg-slate-50 ${selectedCourseId === course.id ? "bg-emerald-50/50" : ""}`} onClick={() => setSelectedCourseId(course.id)}>
                      <td className="px-4 py-4"><p className="font-semibold text-slate-800">{course.title}</p><p className="mt-1 text-xs text-slate-500">{new Date(course.created_at).toLocaleDateString("vi-VN")}</p></td>
                      <td className="px-4 py-4 text-slate-600">{course.subject} · Lớp {course.grade_level}</td>
                      <td className="px-4 py-4"><span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">{statusLabels[course.status] ?? course.status}</span></td>
                      <td className="px-4 py-4"><div className="flex items-center gap-2"><Button type="button" variant="secondary" className="px-3" onClick={(event) => { event.stopPropagation(); setSelectedCourseId(course.id); fileInputRef.current?.click(); }} disabled={uploading}><Upload className="size-4" /> Thêm tài liệu</Button>{user?.role === "admin" && <Button type="button" variant="danger" className="px-3" aria-label={`Xóa khóa học ${course.title}`} isLoading={deletingId === course.id} onClick={(event) => { event.stopPropagation(); void handleDeleteCourse(course); }}><Trash2 className="size-4" /></Button>}</div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <input ref={fileInputRef} className="sr-only" type="file" accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg" onChange={selectFile} />

          <section className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-3"><CloudUpload className="mt-0.5 size-5 shrink-0 text-emerald-700" /><div><h2 className="font-bold text-slate-900">Thêm tài liệu vào khóa học</h2><p className="mt-1 text-sm text-slate-500">{selectedCourse ? selectedCourse.title : "Chọn một khóa học trong danh sách"}</p></div></div>
              <Button type="button" onClick={() => fileInputRef.current?.click()} disabled={!selectedCourseId || uploading} isLoading={uploading}><FileText className="size-4" /> Thêm tài liệu</Button>
            </div>
            <p className="mt-4 text-xs text-slate-500">Định dạng: PDF, DOCX, PPTX, TXT, PNG, JPEG · giới hạn 150 MB.</p>
          </section>

          <DocumentRepository
            documents={documents}
            previewing={Boolean(preview)}
            onPreview={async (versionId) => {
              try {
                const [documentPreview, documentAnalysis] = await Promise.all([
                  getDocumentPreview(versionId),
                  getDocumentAnalysis(versionId),
                ]);
                setPreview(documentPreview);
                setAnalysis(documentAnalysis);
              } catch (requestError) {
                setError(getApiErrorMessage(requestError, "Không thể mở nội dung và bản phân tích tài liệu."));
              }
            }}
            canDelete={user?.role === "admin"}
            deletingId={deletingId}
            onDelete={handleDeleteDocument}
          />
          {selectedCourseId && (
            <AggregateQualityGatePanel
              courseId={selectedCourseId}
              refreshKey={documents.map((item) => `${item.version.id}:${item.job.status}`).join("|")}
              canBuild={user?.role === "admin"}
              isPublished={Boolean(selectedCourse?.active_publication_id)}
              onPublicationChange={async () => {
                await loadCourses();
                setDocuments(await getCourseDocuments(selectedCourseId));
              }}
            />
          )}
          {preview && <DocumentPreviewPanel preview={preview} onChange={setPreview} onClose={() => setPreview(null)} />}
          {job && <JobPanel job={job} retrying={retrying} onRetry={handleRetry} />}
          {analysis && (
            <AnalysisPanel
              analysis={analysis}
              canEdit={user?.role === "admin"}
              onChange={setAnalysis}
            />
          )}
        </div>
      </section>
    </div>
  );
}

function AggregateQualityGatePanel({ courseId, refreshKey, canBuild, isPublished, onPublicationChange }: { courseId: string; refreshKey: string; canBuild: boolean; isPublished: boolean; onPublicationChange: () => Promise<void> }) {
  const [gate, setGate] = useState<CourseQualityGate | null>(null);
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [gateError, setGateError] = useState("");
  const [expandedVersionId, setExpandedVersionId] = useState("");
  const [catalogDetail, setCatalogDetail] = useState<CourseCatalog | null>(null);
  const [catalogDraft, setCatalogDraft] = useState<CourseCatalog | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [editingDetail, setEditingDetail] = useState(false);
  const [savingDetail, setSavingDetail] = useState(false);
  const [publishing, setPublishing] = useState(false);

  useEffect(() => {
    setLoading(true);
    setGateError("");
    void getCourseQualityGate(courseId)
      .then(setGate)
      .catch((requestError) => setGateError(getApiErrorMessage(requestError, "Không thể đọc quality gate khóa học.")))
      .finally(() => setLoading(false));
  }, [courseId, refreshKey]);

  async function handleBuild() {
    setBuilding(true);
    setGateError("");
    try {
      setGate(await buildCourseQualityGate(courseId));
    } catch (requestError) {
      setGateError(getApiErrorMessage(requestError, "Không thể dựng toàn bộ học liệu."));
    } finally {
      setBuilding(false);
    }
  }

  async function toggleDetail(versionId: string) {
    if (expandedVersionId === versionId) {
      setExpandedVersionId("");
      setCatalogDetail(null);
      setCatalogDraft(null);
      setEditingDetail(false);
      return;
    }
    setExpandedVersionId(versionId);
    setLoadingDetail(true);
    setEditingDetail(false);
    setGateError("");
    try {
      const detail = await getCourseCatalog(versionId);
      setCatalogDetail(detail);
      setCatalogDraft(structuredClone(detail));
    } catch (requestError) {
      setGateError(getApiErrorMessage(requestError, "Không thể tải chi tiết Version."));
    } finally {
      setLoadingDetail(false);
    }
  }

  async function handleSaveDetail() {
    if (!catalogDraft) return;
    setSavingDetail(true);
    setGateError("");
    try {
      const saved = await saveCourseCatalog(catalogDraft.course_version_id, catalogDraft);
      setCatalogDetail(saved);
      setCatalogDraft(structuredClone(saved));
      setEditingDetail(false);
    } catch (requestError) {
      setGateError(getApiErrorMessage(requestError, "Không thể lưu chi tiết học liệu."));
    } finally {
      setSavingDetail(false);
    }
  }

  async function handlePublication() {
    const action = isPublished ? "unpublish" : "publish";
    const confirmed = window.confirm(isPublished ? "Thu hồi khóa học khỏi catalog học sinh?" : "Publish snapshot hiện tại cho học sinh?");
    if (!confirmed) return;
    setPublishing(true);
    setGateError("");
    try {
      if (action === "publish") await publishCourse(courseId);
      else await unpublishCourse(courseId);
      await onPublicationChange();
      setExpandedVersionId("");
    } catch (requestError) {
      setGateError(getApiErrorMessage(requestError, isPublished ? "Không thể unpublish khóa học." : "Không thể publish khóa học."));
    } finally {
      setPublishing(false);
    }
  }

  return (
    <section className="mt-6 rounded-lg border border-slate-200 bg-white p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><p className="text-xs font-semibold uppercase tracking-wide text-sky-700">Quality gate cuối</p><h2 className="mt-1 flex items-center gap-2 font-bold text-slate-900"><ListTree className="size-5" /> Toàn bộ học liệu của khóa học</h2><p className="mt-1 text-xs text-slate-500">{loading ? "Đang kiểm tra..." : gate?.ready ? "Sẵn sàng cho bước publish" : "Chưa đủ điều kiện publish"}</p></div>
        {canBuild && <div className="flex flex-wrap gap-2"><Button type="button" variant="secondary" isLoading={building} disabled={!gate?.document_count || isPublished} onClick={() => void handleBuild()}><Database className="size-4" /> Dựng toàn bộ học liệu</Button><Button type="button" variant={isPublished ? "danger" : "primary"} isLoading={publishing} disabled={!isPublished && !gate?.ready} onClick={() => void handlePublication()}><Send className="size-4" /> {isPublished ? "Unpublish" : "Publish"}</Button></div>}
      </div>
      {gateError && <div className="mt-4"><Notice>{gateError}</Notice></div>}
      {gate && <>
        <div className="mt-5 grid grid-cols-2 gap-3 text-sm sm:grid-cols-5"><div><p className="text-xs text-slate-500">Tài liệu đạt</p><p className="font-bold text-slate-900">{gate.ready_document_count}/{gate.document_count}</p></div><div><p className="text-xs text-slate-500">Chương</p><p className="font-bold text-slate-900">{gate.chapter_count}</p></div><div><p className="text-xs text-slate-500">Bài học</p><p className="font-bold text-slate-900">{gate.lesson_count}</p></div><div><p className="text-xs text-slate-500">Concept</p><p className="font-bold text-slate-900">{gate.concept_count}</p></div><div><p className="text-xs text-slate-500">Chunk nguồn</p><p className="font-bold text-slate-900">{gate.chunk_count}</p></div></div>
        {gate.issues.length > 0 && <div className="mt-4"><Notice>{gate.issues.join(" ")}</Notice></div>}
        <div className="mt-5 divide-y divide-slate-200 border-y border-slate-200">{gate.versions.map((version) => <div key={version.course_version_id} className="py-3"><div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"><div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-800">Version {version.version_number} · {version.original_name}</p><p className="mt-1 text-xs text-slate-500">{version.chapter_count} chương · {version.lesson_count} bài · {version.concept_count} concept · {version.chunk_count} chunks</p>{version.issues.length > 0 && <p className="mt-1 text-xs text-red-600">{version.issues.join(" ")}</p>}</div><div className="flex items-center gap-2"><span className={`w-fit rounded-full px-2 py-1 text-xs font-semibold ${version.ready ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{version.ready ? "Đạt" : statusLabels[version.processing_status] ?? "Chưa đạt"}</span><Button type="button" variant="secondary" className="px-3" disabled={!version.ready} onClick={() => void toggleDetail(version.course_version_id)}><Eye className="size-4" /> {expandedVersionId === version.course_version_id ? "Thu gọn" : "Chi tiết"}</Button></div></div>{expandedVersionId === version.course_version_id && <div className="mt-4 border-t border-slate-200 pt-4">{loadingDetail ? <LoadingState /> : catalogDetail && catalogDraft && <CatalogDetailEditor catalog={editingDetail ? catalogDraft : catalogDetail} editing={editingDetail} canEdit={canBuild} saving={savingDetail} onChange={setCatalogDraft} onEdit={() => { setCatalogDraft(structuredClone(catalogDetail)); setEditingDetail(true); }} onCancel={() => { setCatalogDraft(structuredClone(catalogDetail)); setEditingDetail(false); }} onSave={() => void handleSaveDetail()} />}</div>}</div>)}</div>
      </>}
    </section>
  );
}

function CatalogDetailEditor({ catalog, editing, canEdit, saving, onChange, onEdit, onCancel, onSave }: { catalog: CourseCatalog; editing: boolean; canEdit: boolean; saving: boolean; onChange: (catalog: CourseCatalog) => void; onEdit: () => void; onCancel: () => void; onSave: () => void }) {
  function updateChapter(chapterIndex: number, changes: Partial<CourseCatalog["chapters"][number]>) {
    onChange({ ...catalog, chapters: catalog.chapters.map((chapter, index) => index === chapterIndex ? { ...chapter, ...changes } : chapter) });
  }

  function updateLesson(chapterIndex: number, lessonIndex: number, changes: Partial<CourseCatalog["chapters"][number]["lessons"][number]>) {
    const chapter = catalog.chapters[chapterIndex];
    updateChapter(chapterIndex, { lessons: chapter.lessons.map((lesson, index) => index === lessonIndex ? { ...lesson, ...changes } : lesson) });
  }

  function updateConcept(chapterIndex: number, lessonIndex: number, conceptIndex: number, changes: Partial<CourseCatalog["chapters"][number]["lessons"][number]["concepts"][number]>) {
    const lesson = catalog.chapters[chapterIndex].lessons[lessonIndex];
    updateLesson(chapterIndex, lessonIndex, { concepts: lesson.concepts.map((concept, index) => index === conceptIndex ? { ...concept, ...changes } : concept) });
  }

  return <div><div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm font-semibold text-slate-800">Nội dung chi tiết dùng cho lộ trình</p>{canEdit && !editing && <Button type="button" variant="secondary" onClick={onEdit}><Pencil className="size-4" /> Chỉnh sửa</Button>}</div><div className="mt-4 space-y-6">{catalog.chapters.map((chapter, chapterIndex) => <div key={chapter.id}><div className="border-l-2 border-sky-500 pl-3">{editing ? <><Field label={`Chương ${chapter.order_index + 1} - tiêu đề`}><Input value={chapter.title} onChange={(event) => updateChapter(chapterIndex, { title: event.target.value })} /></Field><div className="mt-3"><Field label="Mô tả chương"><Textarea value={chapter.summary} onChange={(event) => updateChapter(chapterIndex, { summary: event.target.value })} /></Field></div></> : <><h4 className="font-semibold text-slate-900">Chương {chapter.order_index + 1}: {chapter.title}</h4><p className="mt-1 text-sm leading-6 text-slate-600">{chapter.summary}</p></>}</div>{chapter.lessons.map((lesson, lessonIndex) => <div key={lesson.id} className="mt-4 pl-5"><div className="flex flex-wrap items-center justify-between gap-2">{!editing && <h5 className="text-sm font-semibold text-slate-800">Bài {lesson.order_index + 1}: {lesson.title}</h5>}<span className="text-xs text-slate-500">{lesson.source_label} · {lesson.chunk_count} chunks</span></div>{editing ? <div className="mt-3 space-y-3"><Field label="Tên bài học"><Input value={lesson.title} onChange={(event) => updateLesson(chapterIndex, lessonIndex, { title: event.target.value })} /></Field><Field label="Mô tả bài học"><Textarea value={lesson.summary} onChange={(event) => updateLesson(chapterIndex, lessonIndex, { summary: event.target.value })} /></Field></div> : <p className="mt-1 text-sm leading-6 text-slate-600">{lesson.summary}</p>}<div className="mt-3 divide-y divide-slate-100 border-y border-slate-100">{lesson.concepts.map((concept, conceptIndex) => <div key={concept.id} className="py-3">{editing ? <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_120px]"><Field label="Tên concept"><Input value={concept.title} onChange={(event) => updateConcept(chapterIndex, lessonIndex, conceptIndex, { title: event.target.value })} /></Field><Field label="Số phút"><Input type="number" min={5} max={480} value={concept.estimated_minutes} onChange={(event) => updateConcept(chapterIndex, lessonIndex, conceptIndex, { estimated_minutes: Number(event.target.value) })} /></Field><div className="md:col-span-2"><Field label="Mô tả concept"><Textarea value={concept.description} onChange={(event) => updateConcept(chapterIndex, lessonIndex, conceptIndex, { description: event.target.value })} /></Field></div></div> : <><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-medium text-slate-800">{concept.title}</p><span className="text-xs text-slate-500">{concept.estimated_minutes} phút</span></div><p className="mt-1 text-sm text-slate-600">{concept.description}</p><p className="mt-1 break-all text-xs text-slate-400">ID: {concept.stable_key}{concept.prerequisite_keys.length ? ` · Tiên quyết: ${concept.prerequisite_keys.join(", ")}` : " · Không có tiên quyết"}</p></>}</div>)}</div></div>)}</div>)}</div>{editing && <div className="mt-5 flex justify-end gap-2"><Button type="button" variant="secondary" disabled={saving} onClick={onCancel}>Hủy</Button><Button type="button" isLoading={saving} onClick={onSave}><Save className="size-4" /> Lưu chi tiết</Button></div>}</div>;
}

function DocumentRepository({
  documents,
  previewing,
  onPreview,
  canDelete,
  deletingId,
  onDelete,
}: {
  documents: import("../types/course").CourseDocumentItem[];
  previewing: boolean;
  onPreview: (versionId: string) => Promise<void>;
  canDelete: boolean;
  deletingId: string;
  onDelete: (item: import("../types/course").CourseDocumentItem) => Promise<void>;
}) {
  return (
    <section className="mt-6 rounded-lg border border-slate-200 bg-white p-6">
      <div className="flex items-center justify-between gap-3">
        <div><p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Giai đoạn 1</p><h2 className="mt-1 font-bold text-slate-900">Kho tài liệu đã lưu</h2></div>
        <span className="text-xs text-slate-500">{documents.length} phiên bản</span>
      </div>
      {documents.length === 0 ? <p className="mt-4 text-sm text-slate-500">Chưa có tài liệu được lưu.</p> : (
        <div className="mt-4 divide-y divide-slate-100">
          {documents.map((item) => (
            <div key={item.document.id} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
              <div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-800">Version {item.version.version_number} · {item.document.original_name}</p><p className="mt-1 text-xs text-slate-500">{statusLabels[item.job.status] ?? item.job.status} · {item.source_characters.toLocaleString("vi-VN")} ký tự</p></div>
              <div className="flex items-center gap-2"><Button type="button" variant="secondary" className="px-3" disabled={item.analysis_status !== "completed" || previewing} onClick={() => void onPreview(item.version.id)}><Eye className="size-4" /> Preview</Button>{canDelete && <Button type="button" variant="danger" className="px-3" aria-label={`Xóa ${item.document.original_name}`} isLoading={deletingId === item.version.id} onClick={() => void onDelete(item)}><Trash2 className="size-4" /></Button>}</div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function DocumentPreviewPanel({ preview, onChange, onClose }: { preview: import("../types/course").DocumentPreview; onChange: (preview: import("../types/course").DocumentPreview) => void; onClose: () => void }) {
  const [mode, setMode] = useState<"original" | "llm" | "edit">("edit");
  const [draft, setDraft] = useState(preview.edited_text ?? preview.original_text);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  const displayedText = mode === "original" ? preview.original_text : mode === "llm" ? preview.llm_input_text : draft;

  async function handleSave() {
    setSaving(true);
    setSaveError("");
    try {
      const saved = await saveDocumentEdit(preview.version.id, draft);
      onChange(saved);
      setDraft(saved.edited_text ?? saved.original_text);
    } catch (requestError) {
      setSaveError(getApiErrorMessage(requestError, "Không thể lưu nội dung chỉnh sửa."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="mt-6 rounded-lg border border-sky-200 bg-sky-50/40 p-6">
      <div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wide text-sky-700">Preview tài liệu đã lưu</p><h2 className="mt-1 font-bold text-slate-900">Version {preview.version.version_number} · {preview.document.original_name}</h2></div><Button type="button" variant="ghost" className="px-2" onClick={onClose}>Đóng</Button></div>
      <p className="mt-3 text-xs text-slate-500">{preview.source_characters.toLocaleString("vi-VN")} ký tự · trạng thái {preview.status}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button type="button" variant={mode === "original" ? "primary" : "secondary"} className="px-3" onClick={() => setMode("original")}>Bản gốc</Button>
        <Button type="button" variant={mode === "llm" ? "primary" : "secondary"} className="px-3" onClick={() => setMode("llm")}>Đã gửi LLM</Button>
        <Button type="button" variant={mode === "edit" ? "primary" : "secondary"} className="px-3" onClick={() => setMode("edit")}><Pencil className="size-4" /> Bản chỉnh sửa</Button>
      </div>
      {saveError && <div className="mt-3"><Notice>{saveError}</Notice></div>}
      {mode === "edit" ? (
        <Textarea className="mt-4 min-h-[32rem] font-mono leading-6" value={draft} onChange={(event) => setDraft(event.target.value)} />
      ) : (
        <pre className="mt-4 max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-white p-4 text-sm leading-6 text-slate-700">{displayedText}</pre>
      )}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-slate-500">{preview.edited_at ? `Đã lưu chỉnh sửa ${new Date(preview.edited_at).toLocaleString("vi-VN")}` : "Chưa có bản chỉnh sửa"}</p>
        {mode === "edit" && <Button type="button" isLoading={saving} disabled={!draft.trim()} onClick={() => void handleSave()}><Save className="size-4" /> Lưu nội dung chỉnh sửa</Button>}
      </div>
    </section>
  );
}

function AnalysisPanel({
  analysis,
  canEdit,
  onChange,
}: {
  analysis: DocumentAnalysis;
  canEdit: boolean;
  onChange: (analysis: DocumentAnalysis) => void;
}) {
  const structure = analysis.structure;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<DocumentStructure>(() => structuredClone(structure));
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  function startEditing() {
    setDraft(structuredClone(analysis.structure));
    setSaveError("");
    setEditing(true);
  }

  function updateChapter(index: number, changes: Partial<DocumentStructure["chapters"][number]>) {
    setDraft((current) => ({
      ...current,
      chapters: current.chapters.map((chapter, chapterIndex) =>
        chapterIndex === index ? { ...chapter, ...changes } : chapter,
      ),
    }));
  }

  async function handleSave() {
    setSaving(true);
    setSaveError("");
    try {
      const saved = await saveDocumentAnalysis(analysis.course_version_id, draft);
      onChange(saved);
      setDraft(structuredClone(saved.structure));
      setEditing(false);
    } catch (requestError) {
      setSaveError(getApiErrorMessage(requestError, "Không thể lưu bản phân tích chỉnh sửa."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="mt-6 rounded-lg border border-slate-200 bg-white p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Kiểm duyệt bản phân tích</p>
          {!editing && <h2 className="mt-1 text-xl font-bold text-slate-900">{structure.title}</h2>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-sky-50 px-2 py-1 text-xs font-semibold text-sky-700">
            {analysis.edited_structure ? "Đã chỉnh sửa" : structure.source === "llm" ? "LLM" : "Fallback"}
          </span>
          {canEdit && !editing && <Button type="button" variant="secondary" className="px-3" onClick={startEditing}><Pencil className="size-4" /> Chỉnh sửa</Button>}
        </div>
      </div>
      {saveError && <div className="mt-4"><Notice>{saveError}</Notice></div>}
      {editing ? (
        <div className="mt-5 space-y-4">
          <Field label="Tiêu đề nội dung"><Input value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} required /></Field>
          <Field label="Tóm tắt nội dung"><Textarea className="min-h-28" value={draft.summary} onChange={(event) => setDraft({ ...draft, summary: event.target.value })} required /></Field>
        </div>
      ) : <p className="mt-4 text-sm leading-6 text-slate-600">{structure.summary}</p>}
      <div className="mt-6 border-t border-slate-200 pt-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="font-bold text-slate-900">Các chương và nội dung chính</h3>
          <span className="text-xs text-slate-500">
            {(editing ? draft : structure).chapters.length} chương · {analysis.source_characters.toLocaleString("vi-VN")} ký tự
          </span>
        </div>
        <div className="mt-4 space-y-3">
          {(editing ? draft : structure).chapters.map((chapter, index) => (
            <article key={`${chapter.number}-${index}`} className="rounded-lg border border-slate-200 p-4">
              {editing ? (
                <div className="space-y-4">
                  <Field label={`Chương ${chapter.number} - tiêu đề`}><Input value={chapter.title} onChange={(event) => updateChapter(index, { title: event.target.value })} required /></Field>
                  <Field label="Tóm tắt chương"><Textarea className="min-h-24" value={chapter.summary} onChange={(event) => updateChapter(index, { summary: event.target.value })} required /></Field>
                  <Field label="Ý chính (mỗi dòng là một ý)"><Textarea className="min-h-28" value={chapter.key_points.join("\n")} onChange={(event) => updateChapter(index, { key_points: event.target.value.split("\n").map((point) => point.trim()).filter(Boolean) })} /></Field>
                </div>
              ) : <>
                <h4 className="font-semibold text-slate-800">{chapter.number}. {chapter.title}</h4>
                <p className="mt-2 text-sm leading-6 text-slate-600">{chapter.summary}</p>
              </>}
              {!editing && chapter.key_points.length > 0 && (
                <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-500">
                  {chapter.key_points.map((point) => <li key={point}>{point}</li>)}
                </ul>
              )}
            </article>
          ))}
        </div>
      </div>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4">
        <p className="text-xs text-slate-500">{analysis.structure_edited_at ? `Admin đã lưu ${new Date(analysis.structure_edited_at).toLocaleString("vi-VN")}. Bản LLM gốc vẫn được giữ lại.` : "Chưa có chỉnh sửa của admin. Bản đang xem là kết quả LLM gốc."}</p>
        {editing && <div className="flex gap-2"><Button type="button" variant="secondary" disabled={saving} onClick={() => setEditing(false)}>Hủy</Button><Button type="button" isLoading={saving} disabled={!draft.title.trim() || !draft.summary.trim()} onClick={() => void handleSave()}><Save className="size-4" /> Lưu bản phân tích</Button></div>}
      </div>
      <RagReviewPanel versionId={analysis.course_version_id} canRebuild={canEdit} />
      <CatalogReviewPanel versionId={analysis.course_version_id} canBuild={canEdit} />
    </section>
  );
}

function RagReviewPanel({ versionId, canRebuild }: { versionId: string; canRebuild: boolean }) {
  const [index, setIndex] = useState<RagIndex | null>(null);
  const [query, setQuery] = useState("");
  const [searchResult, setSearchResult] = useState<RagSearchResponse | null>(null);
  const [loadingIndex, setLoadingIndex] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [searching, setSearching] = useState(false);
  const [ragError, setRagError] = useState("");

  useEffect(() => {
    setLoadingIndex(true);
    setSearchResult(null);
    void getRagIndex(versionId)
      .then(setIndex)
      .catch((requestError) => setRagError(getApiErrorMessage(requestError, "Không thể đọc chỉ mục RAG.")))
      .finally(() => setLoadingIndex(false));
  }, [versionId]);

  async function handleRebuild() {
    setRebuilding(true);
    setRagError("");
    try {
      const result = await rebuildRagIndex(versionId);
      setIndex(result);
      setSearchResult(null);
    } catch (requestError) {
      setRagError(getApiErrorMessage(requestError, "Không thể tạo chỉ mục RAG."));
    } finally {
      setRebuilding(false);
    }
  }

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setRagError("");
    try {
      setSearchResult(await searchRagIndex(versionId, query.trim()));
    } catch (requestError) {
      setRagError(getApiErrorMessage(requestError, "Không thể truy vấn chỉ mục RAG."));
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="mt-6 border-t border-slate-200 pt-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h3 className="flex items-center gap-2 font-bold text-slate-900"><Database className="size-5 text-emerald-700" /> Kiểm tra RAG</h3><p className="mt-1 text-xs text-slate-500">{loadingIndex ? "Đang đọc chỉ mục..." : `${index?.chunk_count ?? 0} đoạn nguồn · ${index?.embedding_model ?? "chưa tạo embedding"}`}</p></div>
        {canRebuild && <Button type="button" variant="secondary" isLoading={rebuilding} onClick={() => void handleRebuild()}><RefreshCw className="size-4" /> {index?.chunk_count ? "Tạo lại chỉ mục" : "Tạo chỉ mục"}</Button>}
      </div>
      {ragError && <div className="mt-3"><Notice>{ragError}</Notice></div>}
      <form className="mt-4 flex flex-col gap-2 sm:flex-row" onSubmit={(event) => void handleSearch(event)}>
        <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nhập nội dung cần tìm trong tài liệu" minLength={2} maxLength={1000} disabled={!index?.chunk_count} />
        <Button type="submit" isLoading={searching} disabled={!index?.chunk_count || query.trim().length < 2}><Search className="size-4" /> Tìm nguồn</Button>
      </form>
      {searchResult && <div className="mt-4 space-y-3">{searchResult.results.length === 0 ? <p className="text-sm text-slate-500">Không tìm thấy đoạn phù hợp.</p> : searchResult.results.map((result, position) => <article key={result.chunk_id} className="border-l-2 border-emerald-500 pl-4"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-semibold text-emerald-700">#{position + 1} · {result.source_label}</p><span className="text-xs text-slate-500">Điểm {(result.score * 100).toFixed(1)}%</span></div><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-600">{result.text}</p></article>)}</div>}
    </div>
  );
}

function CatalogReviewPanel({ versionId, canBuild }: { versionId: string; canBuild: boolean }) {
  const [catalog, setCatalog] = useState<CourseCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [catalogError, setCatalogError] = useState("");

  useEffect(() => {
    setLoading(true);
    void getCourseCatalog(versionId)
      .then(setCatalog)
      .catch((requestError) => setCatalogError(getApiErrorMessage(requestError, "Không thể đọc cấu trúc học liệu.")))
      .finally(() => setLoading(false));
  }, [versionId]);

  async function handleBuild() {
    setBuilding(true);
    setCatalogError("");
    try {
      setCatalog(await buildCourseCatalog(versionId));
    } catch (requestError) {
      setCatalogError(getApiErrorMessage(requestError, "Không thể dựng cấu trúc học liệu."));
    } finally {
      setBuilding(false);
    }
  }

  return (
    <div className="mt-6 border-t border-slate-200 pt-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h3 className="flex items-center gap-2 font-bold text-slate-900"><ListTree className="size-5 text-sky-700" /> Cấu trúc học liệu</h3><p className="mt-1 text-xs text-slate-500">{loading ? "Đang đọc cấu trúc..." : catalog?.ready ? "Đạt quality gate cấu trúc" : "Chưa sẵn sàng"}</p></div>
        {canBuild && <Button type="button" variant="secondary" isLoading={building} onClick={() => void handleBuild()}><ListTree className="size-4" /> {catalog?.chapter_count ? "Dựng lại cấu trúc" : "Dựng cấu trúc"}</Button>}
      </div>
      {catalogError && <div className="mt-3"><Notice>{catalogError}</Notice></div>}
      {catalog && <>
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4"><div><p className="text-xs text-slate-500">Chương</p><p className="font-bold text-slate-900">{catalog.chapter_count}</p></div><div><p className="text-xs text-slate-500">Bài học</p><p className="font-bold text-slate-900">{catalog.lesson_count}</p></div><div><p className="text-xs text-slate-500">Concept</p><p className="font-bold text-slate-900">{catalog.concept_count}</p></div><div><p className="text-xs text-slate-500">Chunk đã nối</p><p className="font-bold text-slate-900">{catalog.chunk_count}</p></div></div>
        {catalog.issues.length > 0 && <div className="mt-4"><Notice>{catalog.issues.join(" ")}</Notice></div>}
        <div className="mt-4 divide-y divide-slate-200 border-y border-slate-200">{catalog.chapters.map((chapter) => <div key={chapter.id} className="py-4"><h4 className="font-semibold text-slate-900">{chapter.order_index + 1}. {chapter.title}</h4>{chapter.lessons.map((lesson) => <div key={lesson.id} className="mt-3 pl-4"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-semibold text-slate-700">Bài {lesson.order_index + 1}: {lesson.title}</p><span className="text-xs text-slate-500">{lesson.source_label} · {lesson.chunk_count} chunks</span></div><ul className="mt-2 space-y-1 text-sm text-slate-600">{lesson.concepts.map((concept) => <li key={concept.id}><span className="font-medium">{concept.title}</span><span className="text-xs text-slate-400"> · {concept.estimated_minutes} phút{concept.prerequisite_keys.length ? ` · có ${concept.prerequisite_keys.length} tiên quyết` : ""}</span></li>)}</ul></div>)}</div>)}</div>
      </>}
    </div>
  );
}

function JobPanel({ job, retrying, onRetry }: { job: DocumentJob; retrying: boolean; onRetry: () => void }) {
  const isFailed = job.status === "failed";
  const isReady = job.status === "completed";
  return (
    <section className="mt-6 rounded-lg border border-slate-200 bg-white p-6">
      <div className="flex items-start justify-between gap-4">
        <div><p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Version {job.version_number}</p><h2 className="mt-1 flex items-center gap-2 font-bold text-slate-900"><FileText className="size-5" /> {job.original_name}</h2></div>
        {isFailed ? <XCircle className="size-5 text-red-600" /> : isReady ? <CheckCircle2 className="size-5 text-emerald-600" /> : <RefreshCw className="size-5 animate-spin text-sky-600" />}
      </div>
      <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100"><div className={`h-full transition-all ${isFailed ? "bg-red-500" : "bg-emerald-500"}`} style={{ width: `${job.progress}%` }} /></div>
      <div className="mt-3 flex flex-wrap justify-between gap-2 text-sm"><span className={`font-semibold ${isFailed ? "text-red-700" : "text-slate-700"}`}>{statusLabels[job.status] ?? job.status}</span><span className="text-slate-500">{job.progress}%</span></div>
      {job.current_step && <p className="mt-2 text-sm text-slate-500">Bước hiện tại: {job.current_step}</p>}
      {job.error_detail && <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{job.error_detail}</p>}
      {(isFailed || isReady) && <Button className="mt-4" type="button" variant="secondary" isLoading={retrying} onClick={onRetry}><RefreshCw className="size-4" /> OCR và xử lý lại</Button>}
      {isReady && <p className="mt-3 text-sm text-emerald-700">File đã được đọc và tạo bản phân tích nội dung.</p>}
    </section>
  );
}
