/**
 * Auth state management — token storage, user session.
 */
import Cookies from "js-cookie";
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  org_id: string | null;
  is_active: boolean;
}

interface AuthState {
  user: AuthUser | null;
  isAuthenticated: boolean;
  setUser: (user: AuthUser) => void;
  setTokens: (access: string, refresh: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      setUser: (user) => set({ user, isAuthenticated: true }),
      setTokens: (access, refresh) => {
        // 30 min for access token, 7 days for refresh
        Cookies.set("access_token", access, { expires: 1 / 48, sameSite: "strict" });
        Cookies.set("refresh_token", refresh, { expires: 7, sameSite: "strict" });
      },
      logout: () => {
        Cookies.remove("access_token");
        Cookies.remove("refresh_token");
        set({ user: null, isAuthenticated: false });
      },
    }),
    {
      name: "auth-store",
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
);

export function getAccessToken(): string | undefined {
  return Cookies.get("access_token");
}

export function isLoggedIn(): boolean {
  return !!Cookies.get("access_token");
}
