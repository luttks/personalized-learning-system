import { apiClient } from "./client";

export interface HealthStatus {
  status: string;
  service?: string;
  database?: number;
}

export interface JobStatus {
  job_id: string;
  status: string;
  result?: unknown;
  error?: string;
  meta?: unknown;
}

export async function getHealth(): Promise<HealthStatus> {
  return (await apiClient.get<HealthStatus>("/health")).data;
}

export async function getDatabaseHealth(): Promise<HealthStatus> {
  return (await apiClient.get<HealthStatus>("/health/database")).data;
}

export async function checkPermission(role: string): Promise<string> {
  const endpoint =
    role === "student"
      ? "/permissions/student-only"
      : role === "admin"
        ? "/permissions/admin-only"
        : "/permissions/teacher-or-admin";
  const response = await apiClient.get<{ message: string }>(endpoint);
  return response.data.message;
}

export async function createTestJob(): Promise<JobStatus> {
  return (await apiClient.post<JobStatus>("/jobs/test")).data;
}

export async function getJob(jobId: string): Promise<JobStatus> {
  return (await apiClient.get<JobStatus>(`/jobs/${jobId}`)).data;
}
