import { apiClient } from "./client";
import { type InlineRoadmap } from "./exam";

export interface PersonalizedRoadmapResponse {
  id: string;
  title: string;
  overview: string;
  total_weeks: number;
  roadmap_data: InlineRoadmap;
  created_at: string;
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
