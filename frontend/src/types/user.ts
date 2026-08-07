export type UserRole =
  | "student"
  | "admin";

export interface User {
  id: string;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  has_completed_profile: boolean;
}

export interface CreateUserPayload {
  full_name: string;
  email: string;
  password: string;
  role: UserRole;
}

export const roleLabels: Record<UserRole, string> = {
  student: "Học sinh",
  admin: "Quản trị viên",
};
