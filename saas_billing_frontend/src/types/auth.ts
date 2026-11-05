export interface Organization {
  id: string;
  name: string;
  slug: string;
  role: string;
}

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  organizations: Organization[];
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
  organization_name?: string;
  invitation_token?: string;
}

export interface AuthUserResponse {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  organizations: Organization[];
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface AuthResponse {
  message: string;
  user: AuthUserResponse;
  tokens: AuthTokens;
}

export interface RefreshResponse {
  access: string;
  refresh?: string;
}

export interface LogoutData {
  refresh: string;
}

export interface LogoutResponse {
  message: string;
}