import axios, {
  type AxiosError,
  type InternalAxiosRequestConfig,
} from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8000/api";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

interface RetryableRequestConfig
  extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

/*
|--------------------------------------------------------------------------
| Request Interceptor
|--------------------------------------------------------------------------
| Automatically attach the access token to every API request.
*/
apiClient.interceptors.request.use(
  (config) => {
    const accessToken =
      localStorage.getItem("access_token");

    if (accessToken) {
      config.headers.Authorization =
        `Bearer ${accessToken}`;
    }

    return config;
  },
  (error) => Promise.reject(error),
);

/*
|--------------------------------------------------------------------------
| Response Interceptor
|--------------------------------------------------------------------------
| If the access token expires:
|
| 1. Get refresh token
| 2. Request a new access token
| 3. Save it
| 4. Retry the original request
|
| If refresh fails, clear authentication.
*/
apiClient.interceptors.response.use(
  (response) => response,

  async (error: AxiosError) => {
    const originalRequest =
      error.config as RetryableRequestConfig | undefined;

    /*
     * Only handle 401 responses.
     */
    if (
      error.response?.status !== 401 ||
      !originalRequest ||
      originalRequest._retry
    ) {
      return Promise.reject(error);
    }

    /*
     * Never try to refresh the token for the
     * authentication endpoints themselves.
     */
    const requestUrl = originalRequest.url || "";

    if (
      requestUrl.includes("/auth/login/") ||
      requestUrl.includes("/auth/register/") ||
      requestUrl.includes("/auth/token/refresh/") ||
      requestUrl.includes("/auth/logout/")
    ) {
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    const refreshToken =
      localStorage.getItem("refresh_token");

    if (!refreshToken) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");

      return Promise.reject(error);
    }

    try {
      /*
       * Use a separate Axios request here so the
       * interceptor doesn't recursively intercept
       * the refresh request.
       */
      const refreshResponse = await axios.post<{
        access: string;
        refresh?: string;
      }>(
        `${API_BASE_URL}/auth/token/refresh/`,
        {
          refresh: refreshToken,
        },
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );

      const newAccessToken =
        refreshResponse.data.access;

      localStorage.setItem(
        "access_token",
        newAccessToken,
      );

      /*
       * SimpleJWT rotation can return a new
       * refresh token.
       */
      if (refreshResponse.data.refresh) {
        localStorage.setItem(
          "refresh_token",
          refreshResponse.data.refresh,
        );
      }

      /*
       * Retry original request using the
       * newly generated access token.
       */
      originalRequest.headers.Authorization =
        `Bearer ${newAccessToken}`;

      return apiClient(originalRequest);
    } catch (refreshError) {
      /*
       * Refresh token is invalid/expired.
       * User must log in again.
       */
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");

      return Promise.reject(refreshError);
    }
  },
);

export default apiClient;