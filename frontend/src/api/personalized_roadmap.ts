import { apiClient } from "./client";
import { type InlineRoadmap } from "./exam";

export interface PersonalizedRoadmapResponse {
  id: string;
  title: string;
  overview: string;
  total_weeks: number;
  roadmap_data: InlineRoadmap;
  created_at: string;
  applied_at: string | null;
  current_phase_number: number;
  exam_analysis_id: string | null;
  source_filename: string | null;
}

export type PhaseAssessmentStatus =
  | "pending"
  | "generating"
  | "ready"
  | "failed"
  | "passed"
  | "not_passed"
  | "locked_for_retry";

export interface PhaseAssessmentStatusResponse {
  phase_number: number;
  status: PhaseAssessmentStatus;
  unlocked: boolean;
  is_current_phase: boolean;
  score_ratio: number | null;
  pass_threshold: number;
  attempts_count: number;
  error_message: string | null;
  retry_unlock_at: string | null;
}

export interface PhaseAssessmentQuestion {
  id: number | string;
  question: string;
  options: { A: string; B: string; C: string; D: string };
  difficulty: "easy" | "medium" | "hard";
}

export interface PhaseAssessmentQuestionsResponse {
  phase_number: number;
  status: PhaseAssessmentStatus;
  questions: PhaseAssessmentQuestion[];
}

export interface PhaseAssessmentResultItem {
  question_id: number | string;
  question: string;
  selected: string | null;
  correct: string;
  is_correct: boolean;
  explanation: string;
  topic_ref: string;
}

export interface SubmitPhaseAssessmentResult {
  score_ratio: number;
  passed: boolean;
  pass_threshold: number;
  unlocked_next_phase: boolean;
  results: PhaseAssessmentResultItem[];
  status: PhaseAssessmentStatus;
}

export type RoadmapFinalExamStatus = "pending" | "generating" | "ready" | "failed" | "completed";

export interface FinalExamQuestion {
  id: number | string;
  question: string;
  options: { A: string; B: string; C: string; D: string };
  difficulty: "easy" | "medium" | "hard";
  phase_number: number | null;
}

export interface PhaseRecapItem {
  phase_number: number;
  title: string;
  status: PhaseAssessmentStatus;
  score_ratio: number | null;
}

export interface RoadmapFinalExamResponse {
  status: RoadmapFinalExamStatus;
  questions: FinalExamQuestion[];
  phase_recap: PhaseRecapItem[];
  score_ratio: number | null;
  error_message: string | null;
}

export interface FinalExamResultItem {
  question_id: number | string;
  question: string;
  selected: string | null;
  correct: string;
  is_correct: boolean;
  explanation: string;
  topic_ref: string;
  phase_number: number | null;
}

export interface SubmitFinalExamResult {
  score_ratio: number;
  results: FinalExamResultItem[];
  phase_recap: PhaseRecapItem[];
}

export async function getPersonalizedRoadmaps(): Promise<PersonalizedRoadmapResponse[]> {
  const response = await apiClient.get("/learners/me/roadmaps");
  return response.data;
}

export async function getPersonalizedRoadmap(id: string): Promise<PersonalizedRoadmapResponse> {
  const response = await apiClient.get(`/learners/me/roadmaps/${id}`);
  return response.data;
}

export async function deletePersonalizedRoadmap(id: string): Promise<void> {
  await apiClient.delete(`/learners/me/roadmaps/${id}`);
}

/** Đánh dấu lộ trình đang được áp dụng — bật nhắc học hằng ngày qua email. Idempotent. */
export async function applyPersonalizedRoadmap(id: string): Promise<PersonalizedRoadmapResponse> {
  const response = await apiClient.post(`/learners/me/roadmaps/${id}/apply`);
  return response.data;
}

/** Trạng thái bài kiểm tra cuối giai đoạn của từng giai đoạn trong lộ trình. */
export async function getPhaseAssessments(roadmapId: string): Promise<PhaseAssessmentStatusResponse[]> {
  const response = await apiClient.get(`/learners/me/roadmaps/${roadmapId}/phases`);
  return response.data;
}

/** Tự xác nhận đã học xong sớm giai đoạn hiện tại, không cần chờ tới ngày cuối lịch học. */
export async function unlockPhaseAssessmentEarly(
  roadmapId: string,
  phaseNumber: number
): Promise<PhaseAssessmentStatusResponse> {
  const response = await apiClient.post(
    `/learners/me/roadmaps/${roadmapId}/phases/${phaseNumber}/unlock-early`
  );
  return response.data;
}

/** Lấy câu hỏi bài kiểm tra (không kèm đáp án đúng) — chỉ thành công khi giai đoạn đã mở khóa. */
export async function getPhaseAssessmentQuestions(
  roadmapId: string,
  phaseNumber: number
): Promise<PhaseAssessmentQuestionsResponse> {
  const response = await apiClient.get(
    `/learners/me/roadmaps/${roadmapId}/phases/${phaseNumber}/questions`
  );
  return response.data;
}

/** Nộp bài kiểm tra cuối giai đoạn — trả điểm + đáp án đúng + có mở khóa giai đoạn sau hay không. */
export async function submitPhaseAssessment(
  roadmapId: string,
  phaseNumber: number,
  answers: { question_id: number | string; selected: string }[]
): Promise<SubmitPhaseAssessmentResult> {
  const response = await apiClient.post(
    `/learners/me/roadmaps/${roadmapId}/phases/${phaseNumber}/submit`,
    { answers }
  );
  return response.data;
}

/** Lấy bài thi chốt hạ cuối lộ trình — chỉ mở khi đã đi qua hết mọi giai đoạn. Tự sinh câu hỏi
 * (lazy, self-heal) nếu chưa có, giống cơ chế bài kiểm tra giai đoạn. */
export async function getFinalExam(roadmapId: string): Promise<RoadmapFinalExamResponse> {
  const response = await apiClient.get(`/learners/me/roadmaps/${roadmapId}/final-exam`);
  return response.data;
}

/** Nộp bài thi chốt hạ — chỉ 1 lần duy nhất, trả điểm số + đáp án đúng + tóm tắt điểm từng giai đoạn. */
export async function submitFinalExam(
  roadmapId: string,
  answers: { question_id: number | string; selected: string }[]
): Promise<SubmitFinalExamResult> {
  const response = await apiClient.post(`/learners/me/roadmaps/${roadmapId}/final-exam/submit`, {
    answers,
  });
  return response.data;
}
