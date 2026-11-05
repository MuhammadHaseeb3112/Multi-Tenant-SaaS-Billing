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

import type {
  AuthResponse,
  LoginCredentials,
  RegisterData,
  User,
} from "../types/auth";

import { AuthContext } from "./AuthContext";

const hasStoredToken = () => {
  const accessToken = localStorage.getItem("access_token");

  return Boolean(accessToken) && accessToken !== "undefined";
};

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({
  children,
}: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  // Without a stored token there is nothing to restore: not loading.
  const [isLoading, setIsLoading] = useState(hasStoredToken);

  const isAuthenticated = Boolean(user);

  const saveTokens = (response: AuthResponse) => {
    localStorage.setItem(
      "access_token",
      response.tokens.access,
    );

    localStorage.setItem(
      "refresh_token",
      response.tokens.refresh,
    );
  };

  const clearTokens = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  };

  // Restores the session from a stored token. Sets no state before the
  // request, so it can run straight from the mount effect.
  const loadUser = useCallback(async () => {
    if (!hasStoredToken()) {
      clearTokens();
      return;
    }

    await getMe()
      .then((currentUser) => setUser(currentUser))
      .catch((error: unknown) => {
        console.error(
          "Authentication initialization failed:",
          error,
        );

        clearTokens();
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

  saveTokens(response);

  const currentUser = await getMe();

  setUser(currentUser);
  setIsLoading(false);
};


const register = async (
  data: RegisterData,
) => {
  const response = await registerApi(data);

  saveTokens(response);

  const currentUser = await getMe();

  setUser(currentUser);
  setIsLoading(false);
};

  const logout = async () => {
    const refreshToken =
      localStorage.getItem("refresh_token");

    try {
      if (
        refreshToken &&
        refreshToken !== "undefined"
      ) {
        await logoutApi({
          refresh: refreshToken,
        });
      }
    } finally {
      clearTokens();
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
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
