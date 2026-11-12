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

// The refresh token is never in the body: it is an httpOnly cookie.
export interface AuthTokens {
  access: string;
}

export interface AuthResponse {
  message: string;
  user: AuthUserResponse;
  tokens: AuthTokens;
}

export interface LogoutResponse {
  message: string;
}