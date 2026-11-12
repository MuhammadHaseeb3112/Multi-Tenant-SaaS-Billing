import apiClient from "./client";
import { setAccessToken } from "./tokenStore";
import type {
  AuthResponse,
  LoginCredentials,
  LogoutResponse,
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

export const logout = async (): Promise<LogoutResponse> => {
  // The refresh token is sent automatically as an httpOnly cookie.
  const response = await apiClient.post<LogoutResponse>(
    "/auth/logout/",
  );

  return response.data;
};

/* ---------- Account self-service ---------- */

export const updateProfile = async (data: {
  first_name: string;
  last_name: string;
}): Promise<User> => {
  const response = await apiClient.patch<User>("/auth/me/", data);

  return response.data;
};

export interface PasswordChangeData {
  current_password: string;
  new_password: string;
  new_password_confirm: string;
}

/**
 * Changing the password signs out every other device. This session
 * gets a fresh access token (and refresh cookie) straight away.
 */
export const changePassword = async (
  data: PasswordChangeData,
): Promise<string> => {
  const response = await apiClient.post<AuthResponse>(
    "/auth/password/change/",
    data,
  );

  setAccessToken(response.data.tokens.access);

  return response.data.message;
};

export const requestPasswordReset = async (
  email: string,
): Promise<string> => {
  const response = await apiClient.post<{ detail: string }>(
    "/auth/password/reset/",
    { email },
  );

  return response.data.detail;
};

export const validatePasswordResetLink = async (
  uid: string,
  token: string,
): Promise<void> => {
  await apiClient.get("/auth/password/reset/validate/", {
    params: { uid, token },
  });
};

export const confirmPasswordReset = async (data: {
  uid: string;
  token: string;
  new_password: string;
  new_password_confirm: string;
}): Promise<string> => {
  const response = await apiClient.post<{ detail: string }>(
    "/auth/password/reset/confirm/",
    data,
  );

  return response.data.detail;
};
