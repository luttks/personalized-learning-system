import { apiClient } from "./client";
import { type InlineRoadmap } from "./exam";
import type { DocumentChatSession } from "../types/course";

export interface PersonalizedRoadmapResponse {
  id: string;
  title: string;
  overview: string;
  total_weeks: number;
  roadmap_data: InlineRoadmap;
  created_at: string;
  source_version_id: string | null;
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

export async function chatWithRoadmap(roadmapId: string, question: string, sessionId?: string): Promise<DocumentChatSession> {
  return (await apiClient.post<DocumentChatSession>(`/learners/me/roadmaps/${roadmapId}/chat`, { question, session_id: sessionId ?? null }, { timeout: 120_000 })).data;
}

export async function chatBySubject(subject: string, question: string, sessionId?: string): Promise<DocumentChatSession> {
  return (await apiClient.post<DocumentChatSession>("/learners/me/roadmaps/chat-by-subject", { subject, question, session_id: sessionId ?? null }, { timeout: 120_000 })).data;
}

export async function emailRoadmapByAnalysis(analysisId: string): Promise<string> {
  return (await apiClient.post<{ message: string }>(`/learners/me/roadmaps/by-analysis/${analysisId}/email`)).data.message;
}
