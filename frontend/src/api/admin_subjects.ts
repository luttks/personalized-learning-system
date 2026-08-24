import { apiClient } from "./client";

export interface SubjectSummaryResponse {
  user_id?: string;
  user_email?: string;
  subject: string;
  count: number;
  last_used?: string;
}

export async function listAllSubjects(): Promise<SubjectSummaryResponse[]> {
  const response = await apiClient.get<SubjectSummaryResponse[]>('/admin/users/subjects');
  return response.data;
}

export async function listUserSubjects(userId: string): Promise<SubjectSummaryResponse[]> {
  const response = await apiClient.get<SubjectSummaryResponse[]>(`/admin/users/${userId}/subjects`);
  return response.data;
}

export async function createUserSubject(userId: string, subject: string, mode = "onboarding"): Promise<SubjectSummaryResponse> {
  const response = await apiClient.post<SubjectSummaryResponse>(`/admin/users/${userId}/subjects`, { subject, mode });
  return response.data;
}

export async function renameUserSubject(userId: string, oldSubject: string, newSubject: string): Promise<void> {
  await apiClient.put(`/admin/users/${userId}/subjects/${encodeURIComponent(oldSubject)}`, { new_subject: newSubject });
}

export async function deleteUserSubject(userId: string, subject: string): Promise<void> {
  await apiClient.delete(`/admin/users/${userId}/subjects/${encodeURIComponent(subject)}`);
}
