import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "./useAuth";
import type { UserRole } from "../types/user";
import { LoadingState } from "../components/ui";

export function RequireAuth() {
  const { user, isBootstrapping } = useAuth();
  const location = useLocation();

  if (isBootstrapping) return <LoadingState />;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  
  if (
    user.role === "student" &&
    !user.has_completed_profile &&
    location.pathname !== "/student-profile" &&
    location.pathname !== "/"
  ) {
    return <Navigate to="/student-profile" replace state={{ blocked: true }} />;
  }
  
  return <Outlet />;
}

export function RequireRole({ allowed }: { allowed: UserRole[] }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user || !allowed.includes(user.role)) return <Navigate to="/" replace />;
  
  if (
    user.role === "student" &&
    !user.has_completed_profile &&
    location.pathname !== "/student-profile" &&
    location.pathname !== "/"
  ) {
    return <Navigate to="/student-profile" replace state={{ blocked: true }} />;
  }

  return <Outlet />;
}

export function GuestOnly() {
  const { user, isBootstrapping } = useAuth();
  if (isBootstrapping) return <LoadingState />;
  if (user) return <Navigate to="/" replace />;
  return <Outlet />;
}
