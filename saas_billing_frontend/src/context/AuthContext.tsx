import {
  createContext,
  useCallback,
  useContext,
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

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(
  undefined,
);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({
  children,
}: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

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

  const loadUser = useCallback(async () => {
    const accessToken =
      localStorage.getItem("access_token");

    if (!accessToken || accessToken === "undefined") {
      clearTokens();
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      const currentUser = await getMe();

      setUser(currentUser);
    } catch (error) {
      console.error(
        "Authentication initialization failed:",
        error,
      );

      clearTokens();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
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

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside an AuthProvider",
    );
  }

  return context;
}