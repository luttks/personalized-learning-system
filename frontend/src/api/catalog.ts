import { apiClient } from "./client";
import type {
  LearnerCourseProfile,
  LearnerCourseProfilePayload,
  DiagnosticAttempt,
  DiagnosticResult,
  CourseLearningPath,
  PublishedCourseDetail,
  PublishedCourseSummary,
} from "../types/course";

export async function getPublishedCourses(): Promise<PublishedCourseSummary[]> {
  return (await apiClient.get<PublishedCourseSummary[]>("/catalog/courses")).data;
}

export async function createCourseLearningPath(
  courseId: string,
  requiredMastery: number,
): Promise<CourseLearningPath> {
  return (await apiClient.post<CourseLearningPath>(`/catalog/courses/${courseId}/learning-paths`, {
    required_mastery: requiredMastery,
  })).data;
}

export async function getLatestCourseLearningPath(courseId: string): Promise<CourseLearningPath> {
  return (await apiClient.get<CourseLearningPath>(`/catalog/courses/${courseId}/learning-paths/latest`)).data;
}

export async function startCourseDiagnostic(courseId: string): Promise<DiagnosticAttempt> {
  return (
    await apiClient.post<DiagnosticAttempt>(
      `/catalog/courses/${courseId}/diagnostics`,
      undefined,
      { timeout: 120_000 },
    )
  ).data;
}

export async function submitCourseDiagnostic(
  attemptId: string,
  answers: number[],
  idempotencyKey: string,
): Promise<DiagnosticResult> {
  return (await apiClient.post<DiagnosticResult>(`/diagnostic-attempts/${attemptId}/submit`, {
    answers,
    idempotency_key: idempotencyKey,
  })).data;
}

export async function getPublishedCourse(courseId: string): Promise<PublishedCourseDetail> {
  return (await apiClient.get<PublishedCourseDetail>(`/catalog/courses/${courseId}`)).data;
}

export async function getLearnerCourseProfile(courseId: string): Promise<LearnerCourseProfile> {
  return (await apiClient.get<LearnerCourseProfile>(`/catalog/courses/${courseId}/learner-profile`)).data;
}

export async function saveLearnerCourseProfile(
  courseId: string,
  payload: LearnerCourseProfilePayload,
): Promise<LearnerCourseProfile> {
  return (await apiClient.put<LearnerCourseProfile>(`/catalog/courses/${courseId}/learner-profile`, payload)).data;
}
