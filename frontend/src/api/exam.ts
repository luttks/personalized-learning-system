import { apiClient } from "./client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DocumentAnalysisResult {
  is_learning_doc: boolean;
  subject: string;
  topics: string[];
  suggested_goals: string[];
  content_summary: string;
  is_code_related: boolean;
  raw_text: string;
  ocr_engine: string;
  not_learning_message: string | null;
  document_level: number | null;
  level_gap: "exceeds_user" | "below_user" | "match" | null;
  warning_message: string | null;
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

export interface RoadmapPhase {
  phase_number: number;
  title: string;
  duration_weeks: number;
  goal: string;
  topics: string[];
  daily_plan: string;
  milestone: string;
}

export interface InlineRoadmap {
  total_weeks: number;
  overview: string;
  phases: RoadmapPhase[];
}

export interface PhaseResources {
  phase_title: string;
  search_query?: string;
  youtube_tutorials: YouTubeTutorial[];
  web_exercises: WebExercise[];
  github_repos: GitHubRepo[];
}

export interface ExamAnalysisDetail {
  id: string;
  filename: string;
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
  created_at: string;
}

export interface ExamAnalysisSummary {
  id: string;
  filename: string;
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

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

/**
 * Luồng 1 — Bước 1: Upload tài liệu + thông tin cá nhân
 * Backend sẽ detect môn học và trả về gợi ý mục tiêu
 */
export async function analyzeDocument(
  file: File
): Promise<DocumentAnalysisResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiClient.post<DocumentAnalysisResult>(
    "/learners/me/exams/analyze-document",
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
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
    { headers: { "Content-Type": "multipart/form-data" } }
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
}): Promise<{ quiz: QuizQuestion[]; topic_summary: string }> {
  const response = await apiClient.post<{ quiz: QuizQuestion[]; topic_summary: string }>(
    "/learners/me/exams/generate-quiz",
    payload
  );
  return response.data;
}

/**
 * Luồng 1 — Bước 3 / Luồng 2: Nộp kết quả
 */
export async function submitExam(
  file: File,
  options: {
    mode?: "onboarding" | "post_exam";
    // Luồng 1
    selectedGoal?: string;
    quickQuizResults?: string;
    subject?: string;
    rawTextForCrawl?: string;
    isCodeRelated?: boolean;
    // Luồng 2
    examScore?: string;
    examMaxScore?: string;
    selectedQuestions?: string;
    rawText?: string;
  } = {}
): Promise<ExamAnalysisDetail> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("mode", options.mode ?? "post_exam");
  formData.append("is_code_related", String(options.isCodeRelated ?? false));

  if (options.selectedGoal) formData.append("selected_goal", options.selectedGoal);
  if (options.quickQuizResults) formData.append("quick_quiz_results", options.quickQuizResults);
  if (options.subject) formData.append("subject", options.subject);
  if (options.rawTextForCrawl) formData.append("raw_text_for_crawl", options.rawTextForCrawl.slice(0, 1000));
  if (options.examScore !== undefined) formData.append("exam_score", options.examScore);
  if (options.examMaxScore !== undefined) formData.append("exam_max_score", options.examMaxScore);
  if (options.selectedQuestions) formData.append("selected_questions", options.selectedQuestions);
  if (options.rawText) formData.append("raw_text", options.rawText);

  const response = await apiClient.post<ExamAnalysisDetail>(
    "/learners/me/exams",
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return response.data;
}

// Backward compat alias (Luồng 2)
export const uploadExam = (file: File, opts: Parameters<typeof submitExam>[1]) =>
  submitExam(file, opts);

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
