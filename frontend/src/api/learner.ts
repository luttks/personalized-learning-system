import type {
  LearnerProfile,
  LearnerProfilePayload,
  LearningEventPayload,
  Mastery,
  Roadmap,
  RoadmapPayload,
  UnderstandingResponse,
} from "../types/learner";
import { apiClient } from "./client";

export async function getLearnerProfile(): Promise<LearnerProfile> {
  return (await apiClient.get<LearnerProfile>("/learners/me")).data;
}

export async function updateLearnerProfile(
  payload: LearnerProfilePayload,
): Promise<LearnerProfile> {
  return (await apiClient.patch<LearnerProfile>("/learners/me", payload)).data;
}

export async function understandInput(
  message: string,
  conversationContext?: string,
): Promise<UnderstandingResponse> {
  return (
    await apiClient.post<UnderstandingResponse>("/learners/me/understand-input", {
      message,
      conversation_context: conversationContext || null,
    })
  ).data;
}

export async function getMastery(): Promise<Mastery[]> {
  return (await apiClient.get<Mastery[]>("/learners/me/mastery")).data;
}

export async function createLearningEvent(
  payload: LearningEventPayload,
): Promise<Mastery> {
  return (
    await apiClient.post<Mastery>("/learners/me/learning-events", payload)
  ).data;
}

export async function createRoadmap(payload: RoadmapPayload): Promise<Roadmap> {
  return (await apiClient.post<Roadmap>("/learners/me/roadmaps", payload)).data;
}
