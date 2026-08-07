import {
  BookOpenCheck,
  CheckCircle2,
  Clock3,
  LogOut,
  Users,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/useAuth";
import { Button, PageHeader } from "../components/ui";
import { roleLabels } from "../types/user";

export function DashboardPage() {
  const { user, signOut } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);

  if (!user) return null;

  const roleAction =
    user.role === "student"
      ? { to: "/learning-profile", label: "Tiếp tục hồ sơ học tập", icon: BookOpenCheck }
      : user.role === "admin"
        ? { to: "/users", label: "Quản lý người dùng", icon: Users }
        : null;

  return (
    <div className="space-y-7">
      <PageHeader
        title={`Xin chào, ${user.full_name}`}
        description={`${roleLabels[user.role]} · ${user.email}`}
        actions={
          roleAction ? (
            <Link
              to={roleAction.to}
              className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800"
            >
              <roleAction.icon className="size-4" />
              {roleAction.label}
            </Link>
          ) : undefined
        }
      />

      <section className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Phiên hiện tại</h2>
          <dl className="mt-4 divide-y divide-slate-200 border-y border-slate-200 text-sm bg-white rounded-lg px-4 border">
            <div className="flex justify-between gap-4 py-4">
              <dt className="text-slate-500">Trạng thái</dt>
              <dd className="flex items-center gap-2 font-medium text-emerald-700">
                <CheckCircle2 className="size-4" /> Hoạt động
              </dd>
            </div>
            <div className="flex justify-between gap-4 py-4">
              <dt className="text-slate-500">Vai trò</dt>
              <dd className="font-medium text-slate-800">{roleLabels[user.role]}</dd>
            </div>
            <div className="flex justify-between gap-4 py-4">
              <dt className="text-slate-500">Tạo lúc</dt>
              <dd className="flex items-center gap-2 font-medium text-slate-800">
                <Clock3 className="size-4 text-slate-400" />
                {new Date(user.created_at).toLocaleDateString("vi-VN")}
              </dd>
            </div>
          </dl>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5 h-fit">
          <h2 className="font-bold text-slate-900">Bảo mật tài khoản</h2>
          <p className="mt-1 text-sm text-slate-500">Thu hồi tất cả refresh token đang hoạt động.</p>
          <Button
            variant="secondary"
            className="mt-5 w-full text-red-600 border-red-200 hover:bg-red-50"
            isLoading={loggingOut}
            onClick={() => {
              setLoggingOut(true);
              void signOut(true);
            }}
          >
            <LogOut className="size-4" /> Đăng xuất mọi thiết bị
          </Button>
        </div>
      </section>
    </div>
  );
}
