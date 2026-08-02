import { createContext, useContext } from "react";

import type { LoginPayload } from "../types/auth";
import type { User } from "../types/user";

export interface AuthContextValue {
  user: User | null;
  isBootstrapping: boolean;
  signIn: (payload: LoginPayload) => Promise<User>;
  signOut: (allDevices?: boolean) => Promise<void>;
  refreshUser: () => Promise<User | null>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
