import apiClient from "./client";
import type {
  AuthResponse,
  LoginCredentials,
  LogoutData,
  LogoutResponse,
  RefreshResponse,
  RegisterData,
  User,
} from "../types/auth";

export const register = async (
  data: RegisterData,
): Promise<AuthResponse> => {
  const response = await apiClient.post<AuthResponse>(
    "/auth/register/",
    data,
  );

  return response.data;
};

export const login = async (
  data: LoginCredentials,
): Promise<AuthResponse> => {
  const response = await apiClient.post<AuthResponse>(
    "/auth/login/",
    data,
  );

  return response.data;
};

export const getMe = async (): Promise<User> => {
  const response = await apiClient.get<User>("/auth/me/");

  return response.data;
};

export const refreshToken = async (
  refresh: string,
): Promise<RefreshResponse> => {
  const response = await apiClient.post<RefreshResponse>(
    "/auth/token/refresh/",
    { refresh },
  );

  return response.data;
};

export const logout = async (
  data: LogoutData,
): Promise<LogoutResponse> => {
  const response = await apiClient.post<LogoutResponse>(
    "/auth/logout/",
    data,
  );

  return response.data;
};