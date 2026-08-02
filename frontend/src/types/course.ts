export interface Course {
  id: string;
  owner_id: string;
  title: string;
  subject: string;
  grade_level: number;
  description: string | null;
  status: string;
  published_version_id: string | null;
  active_publication_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CourseVersion {
  id: string;
  course_id: string;
  version_number: number;
  status: string;
  created_by_id: string;
  failure_code: string | null;
  failure_detail: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentSummary {
  id: string;
  course_version_id: string;
  original_name: string;
  content_type: string;
  size_bytes: number;
  checksum_sha256: string;
  created_at: string;
}

export interface DocumentJob {
  id: string;
  document_id: string;
  course_version_id: string;
  course_id: string;
  version_number: number;
  original_name: string;
  version_status: string;
  status: string;
  progress: number;
  current_step: string | null;
  retry_count: number;
  error_code: string | null;
  error_detail: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentUploadResponse {
  course_version: CourseVersion;
  document: DocumentSummary;
  job: DocumentJob;
}

export interface AnalysisChapter {
  number: number;
  title: string;
  summary: string;
  key_points: string[];
}

export interface DocumentStructure {
  title: string;
  summary: string;
  chapters: AnalysisChapter[];
  source: string;
}

export interface DocumentAnalysis {
  id: string;
  course_version_id: string;
  document_id: string;
  status: string;
  source_characters: number;
  structure: DocumentStructure;
  original_structure: DocumentStructure;
  edited_structure: DocumentStructure | null;
  structure_edited_by_id: string | null;
  structure_edited_at: string | null;
  provider: string | null;
  model: string | null;
  error_code: string | null;
  error_detail: string | null;
  created_at: string;
  updated_at: string;
}

export interface CourseDocumentItem {
  document: DocumentSummary;
  version: CourseVersion;
  job: DocumentJob;
  analysis_status: string | null;
  source_characters: number;
}

export interface DocumentPreview {
  document: DocumentSummary;
  version: CourseVersion;
  status: string;
  original_text: string;
  llm_input_text: string;
  edited_text: string | null;
  effective_text: string;
  edited_by_id: string | null;
  edited_at: string | null;
  source_characters: number;
  structure: DocumentStructure | null;
}

export interface RagIndex {
  course_version_id: string;
  chunk_count: number;
  embedding_model: string;
}

export interface RagSearchResult {
  chunk_id: string;
  chunk_index: number;
  text: string;
  page_number: number | null;
  source_label: string;
  cosine_score: number;
  score: number;
}

export interface RagSearchResponse {
  course_version_id: string;
  query: string;
  index_count: number;
  results: RagSearchResult[];
}

export interface CatalogConcept {
  id: string;
  stable_key: string;
  order_index: number;
  title: string;
  description: string;
  estimated_minutes: number;
  prerequisite_keys: string[];
}

export interface CatalogLesson {
  id: string;
  order_index: number;
  title: string;
  summary: string;
  source_label: string;
  chunk_count: number;
  concepts: CatalogConcept[];
}

export interface CatalogChapter {
  id: string;
  order_index: number;
  title: string;
  summary: string;
  source_label: string;
  lessons: CatalogLesson[];
}

export interface CourseCatalog {
  course_version_id: string;
  ready: boolean;
  issues: string[];
  chapter_count: number;
  lesson_count: number;
  concept_count: number;
  chunk_count: number;
  chapters: CatalogChapter[];
}

export interface CourseQualityVersion {
  course_version_id: string;
  version_number: number;
  document_id: string;
  original_name: string;
  processing_status: string;
  ready: boolean;
  issues: string[];
  chapter_count: number;
  lesson_count: number;
  concept_count: number;
  chunk_count: number;
}

export interface CourseQualityGate {
  course_id: string;
  ready: boolean;
  issues: string[];
  document_count: number;
  ready_document_count: number;
  chapter_count: number;
  lesson_count: number;
  concept_count: number;
  chunk_count: number;
  versions: CourseQualityVersion[];
}

export interface CoursePublication {
  id: string;
  course_id: string;
  revision: number;
  status: string;
  version_ids: string[];
  quality_snapshot: Record<string, unknown>;
  published_by_id: string;
  published_at: string;
  unpublished_at: string | null;
}

export interface PublishedCourseSummary {
  id: string;
  title: string;
  subject: string;
  grade_level: number;
  description: string | null;
  publication_revision: number;
  document_count: number;
  chapter_count: number;
  lesson_count: number;
  concept_count: number;
  published_at: string;
}

export interface PublishedCourseVersion {
  course_version_id: string;
  version_number: number;
  original_name: string;
  chapter_count: number;
  lesson_count: number;
  concept_count: number;
  chunk_count: number;
  chapters: CatalogChapter[];
}

export interface PublishedCourseDetail extends PublishedCourseSummary {
  publication_id: string;
  versions: PublishedCourseVersion[];
}

export interface LearnerCourseProfilePayload {
  learning_goal: string;
  start_date: string;
  deadline: string;
  minutes_per_day: number;
  days_per_week: number;
  available_periods: string[];
  content_formats: string[];
}

export interface LearnerCourseProfile extends LearnerCourseProfilePayload {
  id: string;
  user_id: string;
  course_id: string;
  publication_id: string;
  version_ids: string[];
  profile_version: number;
  stale: boolean;
  created_at: string;
  updated_at: string;
}

export interface DiagnosticQuestion {
  id: string;
  concept_id: string;
  lesson_title: string;
  prompt: string;
  options: string[];
  source_label: string;
}

export interface DiagnosticAttempt {
  attempt_id: string;
  assessment_id: string;
  course_id: string;
  status: string;
  assessment_version: number;
  questions: DiagnosticQuestion[];
  started_at: string;
}

export interface DiagnosticResult {
  attempt_id: string;
  status: string;
  score: number;
  correct_count: number;
  question_count: number;
  results: Array<{
    concept_id: string;
    concept_title: string;
    correct: boolean;
    selected_index: number;
    correct_index: number;
  }>;
  submitted_at: string;
}

export interface CourseLearningPathItem {
  concept_id: string;
  lesson_id: string;
  title: string;
  objective: string;
  sequence: number;
  session_number: number;
  planned_date: string;
  estimated_minutes: number;
  activity_type: string;
  instructions: string;
  completion_criteria: string[];
  source_chunk_ids: string[];
}

export interface CourseLearningPath {
  id: string;
  course_id: string;
  publication_id: string;
  diagnostic_attempt_id: string;
  path_version: number;
  status: string;
  title: string;
  summary: string;
  required_mastery: number;
  total_estimated_minutes: number;
  profile_version: number;
  stale: boolean;
  gaps: Array<Record<string, unknown>>;
  skipped: Array<Record<string, unknown>>;
  items: CourseLearningPathItem[];
  created_at: string;
}

export interface CourseCreatePayload {
  title: string;
  subject: string;
  grade_level: number;
  description: string | null;
}
