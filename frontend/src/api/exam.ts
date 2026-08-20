import { apiClient } from "./client";

// Các endpoint OCR/LLM (phân tích tài liệu, sinh quiz, tạo lộ trình...) có thể chạy
// lâu hơn nhiều so với timeout mặc định 20s của apiClient, đặc biệt với file lớn cần OCR nhiều
// trang (đo thực tế: PDF 115 trang mất ~5.5 phút, kể cả khi Gemini phải retry do lỗi tạm thời).
// Dùng timeout riêng, dài hơn, cho các endpoint này.
const AI_REQUEST_TIMEOUT_MS = 600_000;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ReadingTimeEstimate {
  word_count: number;
  survey_minutes_min: number;
  survey_minutes_max: number;
  general_minutes_min: number;
  general_minutes_max: number;
  technical_minutes_min: number;
  technical_minutes_max: number;
  deep_study_minutes_min: number;
  deep_study_minutes_max: number;
}

export interface DocumentAnalysisResult {
  is_learning_doc: boolean;
  subject: string;
  subjects: string[];                  // Danh sách môn khi upload nhiều file
  multi_subject_detected: boolean;     // True nếu phát hiện > 1 môn
  topics: string[];
  suggested_goals: string[];
  content_summary: string;
  is_code_related: boolean;
  raw_text: string;
  ocr_engine: string;
  not_learning_message: string | null;
  has_clear_structure: boolean;        // False nếu tài liệu không chia chương/mục rõ ràng
  structure_reason: string | null;     // Lý do khi has_clear_structure=false
  temp_file_id: string | null;         // Tham chiếu file đã lưu tạm — dùng khi nộp bài cuối cùng
  reading_time: ReadingTimeEstimate | null; // Ước lượng thời gian đọc — tính bằng code, chưa cá nhân hóa
  document_level: number | null;
  level_gap: "exceeds_user" | "below_user" | "match" | null;
  warning_message: string | null;
  has_existing_mastery: boolean;       // Đã có mastery cho môn này
  existing_roadmap_title: string | null; // Tên lộ trình đang học cùng môn
  // Phát hiện file trùng lập
  duplicate_file: boolean;             // True nếu file này đã tồn tại trong kho
  existing_analysis_id: string | null; // ID phân tích trước có cùng hash
  duplicate_subject: string | null;    // Tên môn của phân tích trước
  duplicate_created_at: string | null; // Ngày tạo phân tích trước
}

export interface QuizQuestion {
  id: number;
  question: string;
  options: { A: string; B: string; C: string; D: string };
  correct: string;
  explanation: string;
  difficulty: "easy" | "medium" | "hard";
  topic: string;
}

export interface ExamQuestion {
  id: string;
  title: string;
  points: string;
  content: string;
  sub_questions: { label: string; text: string }[];
}

export interface ExamQuestionDetail {
  id_cau: string;
  kien_thuc_can_hoc: string;
  loi_khuyen_ngan: string;
  mini_test_and_roadmap?: string;
}

export interface ExamGroup {
  loi_khuyen_chung: string;
  chi_tiet_tung_cau: ExamQuestionDetail[];
}

export interface ExamRecommendation {
  nhom_co_ban?: ExamGroup;
  nhom_van_dung?: ExamGroup;
  nhom_van_dung_cao?: ExamGroup;
  tom_tat_tong_quat?: string;
  _goal?: string;
  [key: string]: any;
}

export interface YouTubeTutorial {
  title: string;
  video_id: string;
  thumbnail_url: string;
  channel_title: string;
  watch_url: string;
}

export interface WebExercise {
  title: string;
  url: string;
  snippet: string;
}

export interface GitHubRepo {
  full_name: string;
  stars: number;
  language: string | null;
  description: string;
  url: string;
}

export interface ExamResources {
  search_query?: string;
  youtube_tutorials: YouTubeTutorial[];
  quiz_exercises: WebExercise[];
  github_repos: GitHubRepo[];
  is_code_related?: boolean;
}

export interface MasteryUpdate {
  topic_id: string;
  group: string;
  mastery_score: number;
  confidence: number;
}

export interface RoadmapDayTopic {
  title: string;
  why: string;
  activities: string;
  minutes: number;
  resource_type?: "video" | "exercise" | "reading" | "mixed";
  location_hint?: string; // Vị trí ước lượng trong tài liệu gốc
}

export interface RoadmapDay {
  day_number: number;
  date: string; // ISO date
  note?: string; // Nhận xét riêng biệt cho ngày này
  topics: RoadmapDayTopic[];
  total_minutes: number;
}

export interface RoadmapPhase {
  phase_number: number;
  title: string;
  why?: string;
  milestone: string;
  search_query?: string;
  days: RoadmapDay[];
}

export interface InlineRoadmap {
  overview: string;
  pacing_note?: string; // Nhận xét lệch pha giữa khối lượng tài liệu và quỹ thời gian
  phases: RoadmapPhase[];
  feasible?: boolean;
  feasibility_note?: string;
  total_days?: number;
  end_date?: string; // ISO date
}

export interface CompetencyEvidenceResult {
  is_competency_evidence: boolean;
  evidence_type: "transcript" | "certificate" | "exam" | "other";
  reason: string | null;
}

export interface PhaseResources {
  phase_title: string;
  search_query?: string;
  youtube_tutorials: YouTubeTutorial[];
  web_exercises: WebExercise[];
  github_repos: GitHubRepo[];
}

/** Kết quả xử lý từng câu theo phương án (post_exam) */
export interface SolutionResult {
  question_id: string;
  question_content: string;
  support_level: string;
  hint: string;
  traps: string;
  tips: string;
  crawled_solutions: WebExercise[];
}

export interface ExamAnalysisDetail {
  id: string;
  filename: string;
  subject: string | null;
  mode: "onboarding" | "post_exam";
  question_count: number;
  formula_count: number;
  ocr_engine: string;
  exam_score: number | null;
  exam_max_score: number | null;
  self_assessed_weak_areas: string | null;
  questions: ExamQuestion[];
  raw_markdown: string | null;
  ai_recommendation: ExamRecommendation;
  resources: ExamResources;
  mastery_updates: MasteryUpdate[];
  roadmap: InlineRoadmap | null;
  phase_resources: Record<string, PhaseResources>;
  roadmap_error: string | null;         // Lỗi nếu sinh lộ trình thất bại
  solution_results: SolutionResult[];   // Per-question results for post_exam
  created_at: string;
}

export interface ExamAnalysisSummary {
  id: string;
  filename: string;
  subject: string | null;
  mode: string;
  question_count: number;
  formula_count: number;
  ocr_engine: string;
  exam_score: number | null;
  exam_max_score: number | null;
  mastery_updates_count: number;
  created_at: string;
}

export interface ParseExamResponse {
  header: string;
  question_count: number;
  formula_count: number;
  questions: ExamQuestion[];
  raw_markdown: string;
  ocr_engine: string;
  filename: string;
}

export interface SubjectSummary {
  subject: string;
  mode: string;
  count: number;
  last_used: string;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

/**
 * Luồng 1 — Bước 1: Upload tài liệu (hỗ trợ nhiều file)
 * Backend sẽ detect môn học và trả về gợi ý mục tiêu + kiểm tra lịch sử mastery
 */
export async function analyzeDocument(
  files: File | File[]
): Promise<DocumentAnalysisResult> {
  const formData = new FormData();
  const fileList = Array.isArray(files) ? files : [files];
  fileList.forEach((f) => formData.append("files", f));

  const response = await apiClient.post<DocumentAnalysisResult>(
    "/learners/me/exams/analyze-document",
    formData,
    { headers: { "Content-Type": "multipart/form-data" }, timeout: AI_REQUEST_TIMEOUT_MS }
  );
  return response.data;
}

/**
 * Luồng 1 — Nhóm 2: Xác thực tài liệu minh chứng năng lực (bảng điểm/chứng chỉ/bài kiểm tra)
 */
export async function analyzeCompetencyEvidence(
  file: File
): Promise<CompetencyEvidenceResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiClient.post<CompetencyEvidenceResult>(
    "/learners/me/exams/analyze-competency-evidence",
    formData,
    { headers: { "Content-Type": "multipart/form-data" }, timeout: AI_REQUEST_TIMEOUT_MS }
  );
  return response.data;
}

/**
 * Luồng 2 — Bước 1: Parse đề thi để chọn câu hỏi
 */
export async function parseExamDocument(
  file: File
): Promise<ParseExamResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiClient.post<ParseExamResponse>(
    "/learners/me/exams/parse-exam",
    formData,
    { headers: { "Content-Type": "multipart/form-data" }, timeout: AI_REQUEST_TIMEOUT_MS }
  );
  return response.data;
}

/**
 * Luồng 1 — Bước 2: Sinh quiz từ nội dung thực của tài liệu
 */
export async function generateQuiz(payload: {
  subject: string;
  document_text: string;
  selected_goal: string;
  num_questions?: number;
}): Promise<{ quiz: QuizQuestion[]; topic_summary: string; quiz_skipped: boolean }> {
  const response = await apiClient.post<{ quiz: QuizQuestion[]; topic_summary: string; quiz_skipped: boolean }>(
    "/learners/me/exams/generate-quiz",
    payload,
    { timeout: AI_REQUEST_TIMEOUT_MS }
  );
  return response.data;
}

/**
 * Luồng 1 Bước 3 / Luồng 2 Bước 2: Nộp kết quả
 * Post-exam: điểm số đã được gộp vào cùng payload, không cần bước riêng
 */
export async function submitExam(
  file: File | null,
  options: {
    mode?: "onboarding" | "post_exam";
    // Luồng 1
    selectedGoal?: string;
    quickQuizResults?: string;
    subject?: string;
    rawTextForCrawl?: string;
    isCodeRelated?: boolean;
    // Luồng 1 — vị trí hiện tại trong chương trình + thời hạn/quỹ thời gian mục tiêu
    curriculumPosition?: string;
    topics?: string;
    deadline?: string;
    startDate?: string;
    minutesPerDay?: number;
    daysPerWeek?: number;
    evidenceType?: string;
    readingTimeHint?: string;
    // Dùng lại file đã lưu tạm ở bước phân tích tài liệu thay vì upload lại (file có thể là null nếu dùng cách này)
    tempFileId?: string;
    // Luồng 2 (điểm số gộp vào bước 2 chọn câu)
    examScore?: string;
    examMaxScore?: string;
    selectedQuestions?: string;
    rawText?: string;
  } = {}
): Promise<ExamAnalysisDetail> {
  const formData = new FormData();
  if (file) formData.append("file", file);
  formData.append("mode", options.mode ?? "post_exam");
  formData.append("is_code_related", String(options.isCodeRelated ?? false));

  if (options.selectedGoal) formData.append("selected_goal", options.selectedGoal);
  if (options.quickQuizResults) formData.append("quick_quiz_results", options.quickQuizResults);
  if (options.subject) formData.append("subject", options.subject);
  if (options.rawTextForCrawl) formData.append("raw_text_for_crawl", options.rawTextForCrawl.slice(0, 1000));
  if (options.curriculumPosition) formData.append("curriculum_position", options.curriculumPosition);
  if (options.topics) formData.append("topics", options.topics);
  if (options.deadline) formData.append("deadline", options.deadline);
  if (options.startDate) formData.append("start_date", options.startDate);
  if (options.tempFileId) formData.append("temp_file_id", options.tempFileId);
  if (options.minutesPerDay !== undefined) formData.append("minutes_per_day", String(options.minutesPerDay));
  if (options.daysPerWeek !== undefined) formData.append("days_per_week", String(options.daysPerWeek));
  if (options.readingTimeHint) formData.append("reading_time_hint", options.readingTimeHint);
  if (options.evidenceType) formData.append("evidence_type", options.evidenceType);
  if (options.examScore !== undefined) formData.append("exam_score", options.examScore);
  if (options.examMaxScore !== undefined) formData.append("exam_max_score", options.examMaxScore);
  if (options.selectedQuestions) formData.append("selected_questions", options.selectedQuestions);
  if (options.rawText) formData.append("raw_text", options.rawText);

  const response = await apiClient.post<ExamAnalysisDetail>(
    "/learners/me/exams",
    formData,
    { headers: { "Content-Type": "multipart/form-data" }, timeout: AI_REQUEST_TIMEOUT_MS }
  );
  return response.data;
}

// Backward compat alias (Luồng 2)
export const uploadExam = (file: File, opts: Parameters<typeof submitExam>[1]) =>
  submitExam(file, opts);

/** Lấy danh sách môn học / đề thi đã làm theo mode */
export async function listSubjects(mode: "onboarding" | "post_exam" = "onboarding"): Promise<SubjectSummary[]> {
  const response = await apiClient.get<SubjectSummary[]>("/learners/me/exams/subjects", {
    params: { mode },
  });
  return response.data;
}

/** Lấy danh sách analyses theo môn học */
export async function listAnalysesBySubject(subject: string, limit = 20): Promise<ExamAnalysisSummary[]> {
  const response = await apiClient.get<ExamAnalysisSummary[]>(
    `/learners/me/exams/subjects/${encodeURIComponent(subject)}/analyses`,
    { params: { limit } }
  );
  return response.data;
}

export async function listExamAnalyses(limit = 20, offset = 0): Promise<ExamAnalysisSummary[]> {
  const response = await apiClient.get<ExamAnalysisSummary[]>("/learners/me/exams", {
    params: { limit, offset },
  });
  return response.data;
}

export async function getExamAnalysis(id: string): Promise<ExamAnalysisDetail> {
  const response = await apiClient.get<ExamAnalysisDetail>(`/learners/me/exams/${id}`);
  return response.data;
}

/** Xóa toàn bộ tài liệu/lộ trình của một môn học (chỉ dữ liệu của chính người dùng) */
export async function deleteSubject(subject: string): Promise<void> {
  await apiClient.delete(`/learners/me/exams/subjects/${encodeURIComponent(subject)}`);
}

/** Xóa một tài liệu/bản phân tích cụ thể (chỉ dữ liệu của chính người dùng) */
export async function deleteExamAnalysis(id: string): Promise<void> {
  await apiClient.delete(`/learners/me/exams/${id}`);
}

/** Xóa file đã lưu tạm khi người dùng bỏ dở luồng (không nộp bài) */
export async function discardTempFile(tempFileId: string): Promise<void> {
  await apiClient.delete(`/learners/me/exams/temp-files/${tempFileId}`);
}

/** Lấy file gốc đã upload (để xem lại) dạng Blob — dùng để hiển thị trong modal xem trước */
export async function getExamAnalysisFileBlob(id: string): Promise<Blob> {
  const response = await apiClient.get(`/learners/me/exams/${id}/file`, { responseType: "blob" });
  return response.data as Blob;
}
