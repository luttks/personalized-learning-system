import { apiClient } from "./client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SubQuestion {
  label: string;
  text: string;
}

export interface ExamQuestion {
  id: string;
  title: string;
  points: string;
  content: string;
  sub_questions: SubQuestion[];
}

export interface ExamParsedResult {
  loai: 1;
  header: string;
  question_count: number;
  formula_count: number;
  questions: ExamQuestion[];
  raw_markdown: string;
  elapsed_seconds: number;
  filename: string;
  status: string;
  ocr_engine: string;
}

export interface GradebookColumn {
  key: string;
  label: string;
}

export interface GradebookRow {
  subject: string;
  [key: string]: string;
}

export interface GradebookResult {
  loai: 2;
  metadata: { grade: string | null; semester: string | null };
  columns: GradebookColumn[];
  rows: GradebookRow[];
  critic: string;
  elapsed_seconds: number;
  filename: string;
  status: string;
  ocr_engine: string;
}

export type OCRResult = ExamParsedResult | GradebookResult;

export interface RecommendationDetail {
  id_cau: string;
  kien_thuc_can_hoc: string;
  loi_khuyen_ngan: string;
}

export interface RecommendationGroup {
  loi_khuyen_chung: string;
  chi_tiet_tung_cau: RecommendationDetail[];
}

export interface RecommendationResult {
  nhom_co_ban: RecommendationGroup;
  nhom_van_dung: RecommendationGroup;
  nhom_van_dung_cao: RecommendationGroup;
}

export interface CrawlResult {
  search_query: string;
  raw_input: string;
  total_items: number;
  youtube_tutorials: Array<{
    title: string;
    video_id: string;
    thumbnail_url: string;
    channel_title: string;
    watch_url: string;
  }>;
  quiz_exercises: Array<{
    title: string;
    url: string;
    snippet: string;
  }>;
  academic_papers: Array<{
    title: string;
    authors: string[];
    year: number | null;
    citation_count: number;
    pdf_url: string | null;
    semantic_url: string;
  }>;
  github_repos: Array<{
    full_name: string;
    stars: number;
    language: string | null;
    description: string;
    url: string;
  }>;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export async function processFile(file: File): Promise<OCRResult> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<OCRResult>(
    "/exam-workflow/process-file",
    form,
    {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 120_000, // OCR can be slow
    },
  );
  return data;
}

export async function parseMarkdown(
  markdownText: string,
): Promise<{ status: string; data: ExamParsedResult }> {
  const { data } = await apiClient.post("/exam-workflow/parse-markdown", {
    markdown_text: markdownText,
  });
  return data;
}

export async function getRecommendations(
  questions: string[],
): Promise<RecommendationResult> {
  const { data } = await apiClient.post<RecommendationResult>(
    "/exam-workflow/recommend",
    { questions },
    { timeout: 90_000 },
  );
  return data;
}

export async function crawlResources(
  query: string,
): Promise<CrawlResult> {
  const { data } = await apiClient.post<CrawlResult>(
    "/exam-workflow/crawl-resources",
    { query },
    { timeout: 60_000 },
  );
  return data;
}
