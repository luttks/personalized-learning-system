import type {
  LoginPayload,
  RegisterPayload,
  TokenResponse,
} from "../types/auth";
import type { User } from "../types/user";
import { apiClient } from "./client";

export async function register(payload: RegisterPayload): Promise<User> {
  const response = await apiClient.post<User>("/auth/register", payload);
  return response.data;
}

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>("/auth/login", payload);
  return response.data;
}

export async function getMe(): Promise<User> {
  const response = await apiClient.get<User>("/auth/me");
  return response.data;
}

export async function logout(refreshToken: string): Promise<void> {
  await apiClient.post("/auth/logout", { refresh_token: refreshToken });
}

export async function logoutAll(): Promise<void> {
  await apiClient.post("/auth/logout-all");
}
