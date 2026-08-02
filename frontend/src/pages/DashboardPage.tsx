import {
  Activity,
  BookOpenCheck,
  CheckCircle2,
  Clock3,
  Database,
  LogOut,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getApiErrorMessage } from "../api/client";
import {
  checkPermission,
  getDatabaseHealth,
  getHealth,
} from "../api/system";
import { useAuth } from "../auth/useAuth";
import { Button, Notice, PageHeader } from "../components/ui";
import { roleLabels } from "../types/user";

export function DashboardPage() {
  const { user, signOut } = useAuth();
  const [status, setStatus] = useState({ api: false, database: false, permission: false });
  const [permissionMessage, setPermissionMessage] = useState("");
  const [error, setError] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    if (!user) return;
    void Promise.all([getHealth(), getDatabaseHealth(), checkPermission(user.role)])
      .then(([api, database, permission]) => {
        setStatus({
          api: api.status === "ok",
          database: database.status === "ok",
          permission: true,
        });
        setPermissionMessage(permission);
      })
      .catch((requestError) => setError(getApiErrorMessage(requestError)));
  }, [user]);

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

      {error && <Notice>{error}</Notice>}

      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Trạng thái hệ thống</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            { label: "API", ready: status.api, icon: Activity },
            { label: "Cơ sở dữ liệu", ready: status.database, icon: Database },
            { label: "Phân quyền", ready: status.permission, icon: ShieldCheck },
          ].map(({ label, ready, icon: Icon }) => (
            <div key={label} className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between">
                <Icon className="size-5 text-slate-500" />
                <span className={`size-2.5 rounded-full ${ready ? "bg-emerald-500" : "bg-amber-400"}`} />
              </div>
              <p className="mt-4 text-sm font-semibold text-slate-800">{label}</p>
              <p className="mt-0.5 text-xs text-slate-500">{ready ? "Sẵn sàng" : "Đang kiểm tra"}</p>
            </div>
          ))}
        </div>
      </section>

      {permissionMessage && (
        <Notice tone="success">
          <span className="font-medium">{permissionMessage}</span>
        </Notice>
      )}

      <section className="grid gap-6 border-t border-slate-200 pt-6 lg:grid-cols-[1fr_360px]">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Phiên hiện tại</h2>
          <dl className="mt-4 divide-y divide-slate-200 border-y border-slate-200 text-sm">
            <div className="flex justify-between gap-4 py-3">
              <dt className="text-slate-500">Trạng thái</dt>
              <dd className="flex items-center gap-2 font-medium text-emerald-700">
                <CheckCircle2 className="size-4" /> Hoạt động
              </dd>
            </div>
            <div className="flex justify-between gap-4 py-3">
              <dt className="text-slate-500">Vai trò</dt>
              <dd className="font-medium text-slate-800">{roleLabels[user.role]}</dd>
            </div>
            <div className="flex justify-between gap-4 py-3">
              <dt className="text-slate-500">Tạo lúc</dt>
              <dd className="flex items-center gap-2 font-medium text-slate-800">
                <Clock3 className="size-4 text-slate-400" />
                {new Date(user.created_at).toLocaleDateString("vi-VN")}
              </dd>
            </div>
          </dl>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-bold text-slate-900">Bảo mật tài khoản</h2>
          <p className="mt-1 text-sm text-slate-500">Thu hồi tất cả refresh token đang hoạt động.</p>
          <Button
            variant="secondary"
            className="mt-5 w-full text-red-600"
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
