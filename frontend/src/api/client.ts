import axios, {
  AxiosError,
  type InternalAxiosRequestConfig,
} from "axios";

const apiBaseUrl =
  import.meta.env.VITE_API_URL ??
  "http://localhost:8000/api/v1";

const ACCESS_TOKEN_KEY = "pls_access_token";
const REFRESH_TOKEN_KEY = "pls_refresh_token";

export interface StoredTokens {
  accessToken: string;
  refreshToken: string;
}

export function getStoredTokens(): StoredTokens | null {
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);

  if (!accessToken || !refreshToken) return null;
  return { accessToken, refreshToken };
}

export function storeTokens(tokens: StoredTokens): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export const apiClient = axios.create({
  baseURL: apiBaseUrl,
  timeout: 20_000,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config) => {
  const tokens = getStoredTokens();
  if (tokens) config.headers.Authorization = `Bearer ${tokens.accessToken}`;
  return config;
});

interface RetryableRequest extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

let refreshRequest: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  const tokens = getStoredTokens();
  if (!tokens) throw new Error("Missing refresh token");

  const response = await axios.post<{
    access_token: string;
    refresh_token: string;
  }>(`${apiBaseUrl}/auth/refresh`, {
    refresh_token: tokens.refreshToken,
  });

  storeTokens({
    accessToken: response.data.access_token,
    refreshToken: response.data.refresh_token,
  });
  return response.data.access_token;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const request = error.config as RetryableRequest | undefined;
    const requestPath = request?.url?.split("?")[0];
    const skipsTokenRefresh = [
      "/auth/login",
      "/auth/register",
      "/auth/refresh",
      "/auth/logout",
    ].includes(requestPath ?? "");

    if (
      error.response?.status !== 401 ||
      !request ||
      request._retry ||
      skipsTokenRefresh ||
      !getStoredTokens()
    ) {
      throw error;
    }

    request._retry = true;
    refreshRequest ??= refreshAccessToken().finally(() => {
      refreshRequest = null;
    });

    try {
      const accessToken = await refreshRequest;
      request.headers.Authorization = `Bearer ${accessToken}`;
      return await apiClient(request);
    } catch (refreshError) {
      clearTokens();
      window.dispatchEvent(new Event("auth:expired"));
      throw refreshError;
    }
  },
);

export function getApiErrorMessage(
  error: unknown,
  fallback = "Đã có lỗi xảy ra. Vui lòng thử lại.",
): string {
  if (!axios.isAxiosError(error)) return fallback;

  const detail = error.response?.data?.detail as
    | string
    | { message?: string; missing_fields?: string[] }
    | Array<{ msg?: string }>
    | undefined;

  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).filter(Boolean).join(". ") || fallback;
  }
  if (detail?.message) {
    const missing = detail.missing_fields?.join(", ");
    return missing ? `${detail.message} (${missing})` : detail.message;
  }
  return fallback;
}
