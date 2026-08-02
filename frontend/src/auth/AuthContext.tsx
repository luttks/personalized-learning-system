import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import * as authApi from "../api/auth";
import {
  clearTokens,
  getStoredTokens,
  storeTokens,
} from "../api/client";
import type { LoginPayload } from "../types/auth";
import type { User } from "../types/user";
import { AuthContext } from "./useAuth";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);

  const refreshUser = useCallback(async () => {
    if (!getStoredTokens()) {
      setUser(null);
      return null;
    }

    try {
      const currentUser = await authApi.getMe();
      setUser(currentUser);
      return currentUser;
    } catch {
      clearTokens();
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    void refreshUser().finally(() => setIsBootstrapping(false));

    const handleExpired = () => setUser(null);
    window.addEventListener("auth:expired", handleExpired);
    return () => window.removeEventListener("auth:expired", handleExpired);
  }, [refreshUser]);

  const signIn = useCallback(async (payload: LoginPayload) => {
    const response = await authApi.login(payload);
    storeTokens({
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
    });
    setUser(response.user);
    return response.user;
  }, []);

  const signOut = useCallback(async (allDevices = false) => {
    const refreshToken = getStoredTokens()?.refreshToken;
    try {
      if (allDevices) await authApi.logoutAll();
      else if (refreshToken) await authApi.logout(refreshToken);
    } finally {
      clearTokens();
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({ user, isBootstrapping, signIn, signOut, refreshUser }),
    [user, isBootstrapping, signIn, signOut, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
