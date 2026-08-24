import { createContext, useContext } from "react";

import type { LoginPayload, TokenResponse } from "../types/auth";
import type { User } from "../types/user";

export interface AuthContextValue {
  user: User | null;
  isBootstrapping: boolean;
  signIn: (payload: LoginPayload) => Promise<User>;
  /** Áp dụng token đã có sẵn (VD sau khi xác thực OTP thành công) mà không cần gọi lại /auth/login. */
  applySession: (response: TokenResponse) => User;
  signOut: (allDevices?: boolean) => Promise<void>;
  refreshUser: () => Promise<User | null>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
