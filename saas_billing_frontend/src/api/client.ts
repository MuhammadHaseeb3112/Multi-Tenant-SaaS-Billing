import axios, {
  type AxiosError,
  type InternalAxiosRequestConfig,
} from "axios";

import { getAccessToken, setAccessToken } from "./tokenStore";

// Same-origin by default: Vite (dev) and nginx (production) proxy /api to
// Django, so the httpOnly refresh cookie is first-party.
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "/api";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  // Send the refresh cookie (needed only if the API is on another origin).
  withCredentials: true,
});

interface RetryableRequestConfig
  extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

const AUTH_ENDPOINTS = [
  "/auth/login/",
  "/auth/register/",
  "/auth/token/refresh/",
  "/auth/logout/",
];

/*
|--------------------------------------------------------------------------
| Access token refresh (single flight)
|--------------------------------------------------------------------------
| Refresh tokens rotate (the old one is blacklisted on use), so parallel
| 401s must share ONE refresh request; otherwise the second refresh would
| use an already-blacklisted token and log the user out.
*/
let refreshPromise: Promise<string | null> | null = null;

export const refreshAccessToken = (): Promise<string | null> => {
  if (!refreshPromise) {
    refreshPromise = axios
      .post<{ access: string }>(
        `${API_BASE_URL}/auth/token/refresh/`,
        null,
        { withCredentials: true },
      )
      .then((response) => {
        setAccessToken(response.data.access);
        return response.data.access;
      })
      .catch(() => {
        setAccessToken(null);
        return null;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
};

/*
|--------------------------------------------------------------------------
| Request interceptor: attach the in-memory access token.
|--------------------------------------------------------------------------
*/
apiClient.interceptors.request.use((config) => {
  const accessToken = getAccessToken();

  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }

  return config;
});

/*
|--------------------------------------------------------------------------
| Response interceptor: on 401, refresh once and retry the request.
|--------------------------------------------------------------------------
*/
apiClient.interceptors.response.use(
  (response) => response,

  async (error: AxiosError) => {
    const originalRequest =
      error.config as RetryableRequestConfig | undefined;

    if (
      error.response?.status !== 401 ||
      !originalRequest ||
      originalRequest._retry
    ) {
      return Promise.reject(error);
    }

    const requestUrl = originalRequest.url || "";

    if (AUTH_ENDPOINTS.some((path) => requestUrl.includes(path))) {
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    const newAccessToken = await refreshAccessToken();

    if (!newAccessToken) {
      return Promise.reject(error);
    }

    originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;

    return apiClient(originalRequest);
  },
);

export default apiClient;
