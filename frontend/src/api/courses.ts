import { apiClient } from "./client";
import type {
  Course,
  CourseDocumentItem,
  CourseCreatePayload,
  CourseCatalog,
  CourseQualityGate,
  CoursePublication,
  DocumentAnalysis,
  DocumentJob,
  DocumentPreview,
  DocumentStructure,
  DocumentUploadResponse,
  RagIndex,
  RagSearchResponse,
} from "../types/course";

export async function createCourse(payload: CourseCreatePayload): Promise<Course> {
  return (await apiClient.post<Course>("/courses", payload)).data;
}

export async function getCourses(limit = 50, offset = 0): Promise<Course[]> {
  return (await apiClient.get<Course[]>("/courses", { params: { limit, offset } })).data;
}

export async function deleteCourse(courseId: string): Promise<void> {
  await apiClient.delete(`/courses/${courseId}`);
}

export async function publishCourse(courseId: string): Promise<CoursePublication> {
  return (await apiClient.post<CoursePublication>(`/courses/${courseId}/publish`)).data;
}

export async function unpublishCourse(courseId: string): Promise<CoursePublication> {
  return (await apiClient.post<CoursePublication>(`/courses/${courseId}/unpublish`)).data;
}

export async function getCourseDocuments(courseId: string): Promise<CourseDocumentItem[]> {
  return (await apiClient.get<CourseDocumentItem[]>(`/courses/${courseId}/documents`)).data;
}

export async function getCourseQualityGate(courseId: string): Promise<CourseQualityGate> {
  return (await apiClient.get<CourseQualityGate>(`/courses/${courseId}/quality-gate`)).data;
}

export async function buildCourseQualityGate(courseId: string): Promise<CourseQualityGate> {
  return (await apiClient.post<CourseQualityGate>(`/courses/${courseId}/quality-gate/build`)).data;
}

export async function getDocumentPreview(versionId: string): Promise<DocumentPreview> {
  return (await apiClient.get<DocumentPreview>(`/courses/versions/${versionId}/preview`)).data;
}

export async function deleteDocumentVersion(versionId: string): Promise<void> {
  await apiClient.delete(`/courses/versions/${versionId}/document`);
}

export async function saveDocumentEdit(versionId: string, editedText: string): Promise<DocumentPreview> {
  return (
    await apiClient.patch<DocumentPreview>(`/courses/versions/${versionId}/preview`, {
      edited_text: editedText,
    })
  ).data;
}

export async function uploadCourseDocument(
  courseId: string,
  file: File,
): Promise<DocumentUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return (
    await apiClient.post<DocumentUploadResponse>(
      `/courses/${courseId}/documents`,
      form,
      { headers: { "Content-Type": "multipart/form-data" } },
    )
  ).data;
}

export async function getDocumentJob(jobId: string): Promise<DocumentJob> {
  return (await apiClient.get<DocumentJob>(`/document-jobs/${jobId}`)).data;
}

export async function retryDocumentJob(jobId: string): Promise<DocumentJob> {
  return (await apiClient.post<DocumentJob>(`/document-jobs/${jobId}/retry`)).data;
}

export async function getDocumentAnalysis(versionId: string): Promise<DocumentAnalysis> {
  return (await apiClient.get<DocumentAnalysis>(`/courses/versions/${versionId}/analysis`)).data;
}

export async function saveDocumentAnalysis(
  versionId: string,
  structure: DocumentStructure,
): Promise<DocumentAnalysis> {
  return (
    await apiClient.patch<DocumentAnalysis>(`/courses/versions/${versionId}/analysis`, {
      structure,
    })
  ).data;
}

export async function getRagIndex(versionId: string): Promise<RagIndex> {
  return (await apiClient.get<RagIndex>(`/courses/versions/${versionId}/rag`)).data;
}

export async function rebuildRagIndex(versionId: string): Promise<RagIndex> {
  return (await apiClient.post<RagIndex>(`/courses/versions/${versionId}/rag/index`)).data;
}

export async function searchRagIndex(
  versionId: string,
  query: string,
  limit = 5,
): Promise<RagSearchResponse> {
  return (
    await apiClient.post<RagSearchResponse>(`/courses/versions/${versionId}/rag/search`, {
      query,
      limit,
    })
  ).data;
}

export async function getCourseCatalog(versionId: string): Promise<CourseCatalog> {
  return (await apiClient.get<CourseCatalog>(`/courses/versions/${versionId}/catalog`)).data;
}

export async function buildCourseCatalog(versionId: string): Promise<CourseCatalog> {
  return (await apiClient.post<CourseCatalog>(`/courses/versions/${versionId}/catalog/build`)).data;
}

export async function saveCourseCatalog(
  versionId: string,
  catalog: CourseCatalog,
): Promise<CourseCatalog> {
  return (
    await apiClient.patch<CourseCatalog>(`/courses/versions/${versionId}/catalog`, {
      chapters: catalog.chapters.map((chapter) => ({
        id: chapter.id,
        title: chapter.title,
        summary: chapter.summary,
        lessons: chapter.lessons.map((lesson) => ({
          id: lesson.id,
          title: lesson.title,
          summary: lesson.summary,
          concepts: lesson.concepts.map((concept) => ({
            id: concept.id,
            title: concept.title,
            description: concept.description,
            estimated_minutes: concept.estimated_minutes,
          })),
        })),
      })),
    })
  ).data;
}
