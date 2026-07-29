import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setAuthToken, setUnauthorizedHandler } from "../api/client";
import type { AuthUser, Role } from "../types";

interface StoredAuth {
  token: string;
  user: AuthUser;
  mustChangePassword: boolean;
}

interface AuthContextValue {
  user: AuthUser | null;
  mustChangePassword: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  completePasswordChange: () => void;
  error: string | null;
  clearError: () => void;
}

const STORAGE_KEY = "colonels-till-auth";
const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function readStorage(): StoredAuth | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredAuth;
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

function writeStorage(stored: StoredAuth | null) {
  if (stored) localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
  else localStorage.removeItem(STORAGE_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [mustChangePassword, setMustChangePassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Restore a previous session on load (e.g. tablet was rebooted or the
  // PWA was closed and reopened) — this must NOT create a new login/clock-in.
  useEffect(() => {
    const stored = readStorage();
    if (stored) {
      setAuthToken(stored.token);
      setUser(stored.user);
      setMustChangePassword(stored.mustChangePassword);
    }
  }, []);

  // If any API call ever comes back 401 (token invalid, session closed
  // elsewhere, backend restarted), drop straight back to the login screen
  // rather than leaving the till in a half-authenticated state.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setAuthToken(null);
      setUser(null);
      setMustChangePassword(false);
      writeStorage(null);
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  async function login(username: string, password: string) {
    setError(null);
    try {
      const res = await api.login(username, password);
      setAuthToken(res.token);
      const authUser: AuthUser = { id: res.user_id, username: res.username, role: res.role as Role };
      setUser(authUser);
      setMustChangePassword(res.must_change_password);
      writeStorage({ token: res.token, user: authUser, mustChangePassword: res.must_change_password });
    } catch (e) {
      setAuthToken(null);
      setError(e instanceof Error ? e.message : "Login failed.");
      throw e;
    }
  }

  async function logout() {
    try {
      await api.logout();
    } catch {
      // Clock-out locally regardless — the till must never trap a staff
      // member on a "logging out..." screen because of a network hiccup.
    }
    setAuthToken(null);
    setUser(null);
    setMustChangePassword(false);
    writeStorage(null);
  }

  function completePasswordChange() {
    setMustChangePassword(false);
    const stored = readStorage();
    if (stored) writeStorage({ ...stored, mustChangePassword: false });
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        mustChangePassword,
        login,
        logout,
        completePasswordChange,
        error,
        clearError: () => setError(null),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
