import { apiClient } from "./client";

export interface DashboardStats {
  course_document_count: number;
  exam_upload_count: number;
  roadmap_count: number;
  study_minutes_per_day: number | null;
  study_days_per_week: number | null;
  total_study_minutes: number;
}

export async function getDashboardStats(): Promise<DashboardStats> {
  return (await apiClient.get<DashboardStats>("/dashboard/stats")).data;
}
