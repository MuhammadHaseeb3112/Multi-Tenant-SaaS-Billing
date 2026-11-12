import { createContext, useContext } from "react";

import type {
  LoginCredentials,
  RegisterData,
  User,
} from "../types/auth";

// Context object + hook. The provider lives in AuthProvider.tsx so this
// file exports no components (keeps React Fast Refresh working).

export interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  // Reloads the user (and their organizations) from the server.
  refreshUser: () => Promise<User | null>;
}

export const AuthContext = createContext<AuthContextType | undefined>(
  undefined,
);

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside an AuthProvider",
    );
  }

  return context;
}
