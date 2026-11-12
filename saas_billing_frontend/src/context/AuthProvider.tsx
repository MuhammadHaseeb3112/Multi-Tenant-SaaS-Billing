import {
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import {
  getMe,
  login as loginApi,
  logout as logoutApi,
  register as registerApi,
} from "../api/auth";
import { refreshAccessToken } from "../api/client";
import {
  clearLegacyStoredTokens,
  setAccessToken,
} from "../api/tokenStore";

import type {
  AuthResponse,
  LoginCredentials,
  RegisterData,
  User,
} from "../types/auth";

import { AuthContext } from "./AuthContext";

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({
  children,
}: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  // Until the refresh cookie has been checked we don't know yet.
  const [isLoading, setIsLoading] = useState(true);

  const isAuthenticated = Boolean(user);

  const saveSession = (response: AuthResponse) => {
    setAccessToken(response.tokens.access);
  };

  // Restores the session on page load: the httpOnly refresh cookie (sent
  // by the browser) is exchanged for a new in-memory access token. Sets no
  // state before the request, so it can run straight from the effect.
  const loadUser = useCallback(async () => {
    clearLegacyStoredTokens();

    await refreshAccessToken()
      .then((access) => (access ? getMe() : null))
      .then((currentUser) => setUser(currentUser))
      .catch((error: unknown) => {
        console.error(
          "Authentication initialization failed:",
          error,
        );

        setAccessToken(null);
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    void loadUser();
  }, [loadUser]);

  const login = async (
    credentials: LoginCredentials,
  ) => {
    const response = await loginApi(credentials);

    saveSession(response);

    const currentUser = await getMe();

    setUser(currentUser);
    setIsLoading(false);
  };

  const register = async (
    data: RegisterData,
  ) => {
    const response = await registerApi(data);

    saveSession(response);

    const currentUser = await getMe();

    setUser(currentUser);
    setIsLoading(false);
  };

  const refreshUser = async () => {
    const currentUser = await getMe();

    setUser(currentUser);

    return currentUser;
  };

  const logout = async () => {
    try {
      // Blacklists the refresh token and deletes the cookie.
      await logoutApi();
    } catch {
      // Session already expired on the server: nothing to revoke.
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  };
  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isLoading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
