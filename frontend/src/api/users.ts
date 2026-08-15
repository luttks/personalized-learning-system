import { apiClient } from "./client";
import type {
  CreateUserPayload,
  User,
  UserRole,
} from "../types/user";

export async function getUsers(
  limit = 20,
  offset = 0,
): Promise<User[]> {
  const response = await apiClient.get<User[]>("/users", {
    params: { limit, offset },
  });
  return response.data;
}

export async function createUser(
  payload: CreateUserPayload,
): Promise<User> {
  const response = await apiClient.post<User>(
    "/users",
    payload,
  );

  return response.data;
}

export interface UpdateUserPayload {
  full_name?: string;
  role?: UserRole;
  is_active?: boolean;
}

export async function updateUser(
  id: string,
  payload: UpdateUserPayload,
): Promise<User> {
  const response = await apiClient.put<User>(
    `/users/${id}`,
    payload,
  );
  return response.data;
}

export async function deleteUser(
  id: string,
): Promise<void> {
  await apiClient.delete(`/users/${id}`);
}
