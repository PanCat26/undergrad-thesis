"use client";

import * as React from "react";
import { toast } from "sonner";

import { API_BASE_URL, ApiError, apiRequest, type RequestOptions } from "@/lib/api";

const TOKEN_KEY = "rt_token";

export interface User {
  id: string;
  email: string | null;
  is_guest: boolean;
}

interface TokenResponse {
  access_token: string;
  expires_in: number | null;
  user: User;
}

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  token: string | null;
  startGuest: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  confirm: (email: string, code: string) => Promise<void>;
  forgotPassword: (email: string) => Promise<void>;
  resetPassword: (email: string, code: string, newPassword: string) => Promise<void>;
  changePassword: (oldPassword: string, newPassword: string) => Promise<void>;
  deleteAccount: () => Promise<void>;
  logout: () => void;
  request: <T>(path: string, options?: Omit<RequestOptions, "token">) => Promise<T>;
  requestRaw: (path: string, options?: Omit<RequestOptions, "token">) => Promise<Response>;
  upload: <T>(path: string, formData: FormData) => Promise<T>;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = React.useState<string | null>(null);
  const [user, setUser] = React.useState<User | null>(null);
  const [status, setStatus] = React.useState<AuthStatus>("loading");

  const persist = React.useCallback((resp: TokenResponse) => {
    localStorage.setItem(TOKEN_KEY, resp.access_token);
    setToken(resp.access_token);
    setUser(resp.user);
    setStatus("authenticated");
  }, []);

  const logout = React.useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  // Restore an existing session on first load.
  React.useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (!stored) {
      setStatus("unauthenticated");
      return;
    }
    apiRequest<User>("/api/auth/me", { token: stored })
      .then((me) => {
        setToken(stored);
        setUser(me);
        setStatus("authenticated");
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setStatus("unauthenticated");
      });
  }, []);

  const request = React.useCallback(
    async <T,>(path: string, options: Omit<RequestOptions, "token"> = {}): Promise<T> => {
      try {
        return await apiRequest<T>(path, { ...options, token });
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          if (token) toast.error("Your session has expired. Please log in again.");
          logout();
        }
        throw err;
      }
    },
    [token, logout]
  );

  const requestRaw = React.useCallback(
    async (path: string, options: Omit<RequestOptions, "token"> = {}): Promise<Response> => {
      const headers: Record<string, string> = {};
      if (options.body !== undefined) headers["Content-Type"] = "application/json";
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const response = await fetch(`${API_BASE_URL}${path}`, {
        method: options.method ?? "GET",
        headers,
        body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
        signal: options.signal,
      });
      if (response.status === 401) {
        if (token) toast.error("Your session has expired. Please log in again.");
        logout();
      }
      return response;
    },
    [token, logout]
  );

  const upload = React.useCallback(
    async <T,>(path: string, formData: FormData): Promise<T> => {
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      let response: Response;
      try {
        response = await fetch(`${API_BASE_URL}${path}`, {
          method: "POST",
          headers,
          body: formData,
        });
      } catch {
        throw new ApiError(0, "network_error", "Cannot reach the server. Please try again.");
      }
      const isJson = response.headers.get("content-type")?.includes("application/json");
      const payload = isJson ? await response.json() : null;
      if (!response.ok) {
        if (response.status === 401) {
          if (token) toast.error("Your session has expired. Please log in again.");
          logout();
        }
        throw new ApiError(
          response.status,
          payload?.error?.code ?? "error",
          payload?.error?.message ?? "Upload failed",
          payload?.error?.detail
        );
      }
      return payload as T;
    },
    [token, logout]
  );

  const startGuest = React.useCallback(async () => {
    persist(await apiRequest<TokenResponse>("/api/auth/guest", { method: "POST" }));
  }, [persist]);

  const login = React.useCallback(
    async (email: string, password: string) => {
      persist(
        await apiRequest<TokenResponse>("/api/auth/login", {
          method: "POST",
          body: { email, password },
        })
      );
    },
    [persist]
  );

  const register = React.useCallback(async (email: string, password: string) => {
    await apiRequest("/api/auth/register", { method: "POST", body: { email, password } });
  }, []);

  const confirm = React.useCallback(async (email: string, code: string) => {
    await apiRequest("/api/auth/confirm", { method: "POST", body: { email, code } });
  }, []);

  const forgotPassword = React.useCallback(async (email: string) => {
    await apiRequest("/api/auth/forgot-password", { method: "POST", body: { email } });
  }, []);

  const resetPassword = React.useCallback(
    async (email: string, code: string, newPassword: string) => {
      await apiRequest("/api/auth/reset-password", {
        method: "POST",
        body: { email, code, new_password: newPassword },
      });
    },
    []
  );

  const changePassword = React.useCallback(
    async (oldPassword: string, newPassword: string) => {
      await request("/api/auth/change-password", {
        method: "POST",
        body: { old_password: oldPassword, new_password: newPassword },
      });
    },
    [request]
  );

  const deleteAccount = React.useCallback(async () => {
    await request("/api/auth/account", { method: "DELETE" });
    logout();
  }, [request, logout]);

  const value: AuthContextValue = {
    status,
    user,
    token,
    startGuest,
    login,
    register,
    confirm,
    forgotPassword,
    resetPassword,
    changePassword,
    deleteAccount,
    logout,
    request,
    requestRaw,
    upload,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
