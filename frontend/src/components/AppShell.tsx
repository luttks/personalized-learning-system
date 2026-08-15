import {
  Activity,
  BookOpen,
  ChevronDown,
  Gauge,
  GraduationCap,
  LogOut,
  Map,
  Menu,
  ShieldCheck,
  Trophy,
  UserRound,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/useAuth";
import type { UserRole } from "../types/user";
import { roleLabels } from "../types/user";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  roles?: UserRole[];
}

const navigation: NavItem[] = [
  { to: "/", label: "Tổng quan", icon: Gauge },
  { to: "/student-profile", label: "Hồ sơ học sinh", icon: UserRound, roles: ["student"] },
  { to: "/personalized/onboarding", label: "Bắt đầu học mới", icon: BookOpen, roles: ["student"] },
  { to: "/personalized/post-exam", label: "Cải thiện sau thi", icon: Trophy, roles: ["student"] },
  { to: "/roadmap", label: "Quản lý lộ trình", icon: Map, roles: ["student"] },
  { to: "/users", label: "Người dùng", icon: Users, roles: ["admin"] },
  { to: "/admin/subjects", label: "Quản lý môn học", icon: BookOpen, roles: ["admin"] },
];

export function AppShell() {
  const { user, signOut } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  if (!user) return null;

  const visibleNavigation = navigation.filter(
    (item) => !item.roles || item.roles.includes(user.role),
  );

  const navContent = (
    <>
      <div className="flex h-16 items-center gap-3 border-b border-slate-800 px-5">
        <div className="grid size-9 place-items-center rounded-lg bg-emerald-500 text-slate-950">
          <GraduationCap className="size-5" />
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-bold text-white">Personalized Learning</p>
          <p className="text-xs text-slate-400">Learning workspace</p>
        </div>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {visibleNavigation.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              `flex min-h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium transition ${
                isActive
                  ? "bg-emerald-500 text-slate-950"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
              }`
            }
          >
            <Icon className="size-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-slate-800 p-4 text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-emerald-400" />
          Phiên được bảo vệ bằng JWT
        </div>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-slate-50">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col bg-slate-950 lg:flex">
        {navContent}
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            className="absolute inset-0 bg-slate-950/50"
            aria-label="Đóng menu"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative flex h-full w-72 flex-col bg-slate-950 shadow-xl">
            <button
              className="absolute right-3 top-4 z-10 grid size-9 place-items-center text-slate-300"
              aria-label="Đóng menu"
              onClick={() => setMobileOpen(false)}
            >
              <X className="size-5" />
            </button>
            {navContent}
          </aside>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-6">
          <button
            className="grid size-10 place-items-center rounded-lg text-slate-600 hover:bg-slate-100 lg:hidden"
            aria-label="Mở menu"
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="size-5" />
          </button>

          <div className="hidden items-center gap-2 text-sm text-slate-500 lg:flex">
            <Activity className="size-4 text-emerald-600" />
            Workspace đang hoạt động
          </div>

          <div className="relative ml-auto">
            <button
              className="flex min-h-10 items-center gap-3 rounded-lg px-2 text-left hover:bg-slate-100"
              onClick={() => setAccountOpen((value) => !value)}
              aria-expanded={accountOpen}
            >
              <div className="grid size-8 place-items-center rounded-full bg-emerald-100 text-sm font-bold text-emerald-800">
                {user.full_name.charAt(0).toUpperCase()}
              </div>
              <div className="hidden sm:block">
                <p className="max-w-44 truncate text-sm font-semibold text-slate-800">{user.full_name}</p>
                <p className="text-xs text-slate-500">{roleLabels[user.role]}</p>
              </div>
              <ChevronDown className="size-4 text-slate-400" />
            </button>

            {accountOpen && (
              <div className="absolute right-0 mt-2 w-64 rounded-lg border border-slate-200 bg-white p-2 shadow-lg">
                <div className="border-b border-slate-100 px-3 py-2">
                  <p className="truncate text-sm font-semibold text-slate-800">{user.email}</p>
                  <p className="mt-0.5 text-xs text-slate-500">{roleLabels[user.role]}</p>
                </div>
                <button
                  className="mt-1 flex min-h-10 w-full items-center gap-2 rounded-lg px-3 text-sm font-medium text-red-600 hover:bg-red-50"
                  onClick={() => void signOut()}
                >
                  <LogOut className="size-4" />
                  Đăng xuất
                </button>
              </div>
            )}
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
