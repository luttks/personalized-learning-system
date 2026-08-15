import { apiClient } from "./client";

export interface HealthStatus {
  status: string;
  service?: string;
  database?: number;
}

export async function getHealth(): Promise<HealthStatus> {
  return (await apiClient.get<HealthStatus>("/health")).data;
}

export async function getDatabaseHealth(): Promise<HealthStatus> {
  return (await apiClient.get<HealthStatus>("/health/database")).data;
}
