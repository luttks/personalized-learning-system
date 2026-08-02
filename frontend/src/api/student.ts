import type {
  StudentProfile,
  StudentProfilePayload,
} from "../types/student";
import { apiClient } from "./client";

export async function getStudentProfile(): Promise<StudentProfile> {
  return (await apiClient.get<StudentProfile>("/student-profile/me")).data;
}

export async function createStudentProfile(
  payload: StudentProfilePayload,
): Promise<StudentProfile> {
  return (await apiClient.post<StudentProfile>("/student-profile", payload)).data;
}

export async function updateStudentProfile(
  payload: Partial<StudentProfilePayload>,
): Promise<StudentProfile> {
  return (await apiClient.patch<StudentProfile>("/student-profile/me", payload)).data;
}
