import { apiClient } from "./client";
import type {
  CreateUserPayload,
  User,
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
