import {
  BookOpenCheck,
  CheckCircle2,
  Clock3,
  LogOut,
  Users,
  FileText,
  ClipboardCheck,
  Map,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/useAuth";
import { Button, PageHeader } from "../components/ui";
import { roleLabels } from "../types/user";
import { getDashboardStats, type DashboardStats } from "../api/dashboard";
import { useEffect } from "react";

export function DashboardPage() {
  const { user, signOut } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [statsError, setStatsError] = useState("");

  useEffect(() => {
    void getDashboardStats().then(setStats).catch(() => setStatsError("Không thể tải thống kê hoạt động."));
  }, []);

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

      <section>
        <div className="flex items-end justify-between gap-3"><div><h2 className="text-lg font-bold text-slate-900">Thống kê học tập</h2><p className="mt-1 text-sm text-slate-500">Tổng hợp tài liệu, bài kiểm tra và lịch học của bạn.</p></div>{statsError && <p className="text-xs text-red-600">{statsError}</p>}</div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <StatCard icon={FileText} label="Tài liệu khóa học" value={stats?.course_document_count ?? "—"} tone="emerald" />
          <StatCard icon={ClipboardCheck} label="Bài kiểm tra đã upload" value={stats?.exam_upload_count ?? "—"} tone="blue" />
          <StatCard icon={Map} label="Lộ trình đã tạo" value={stats?.roadmap_count ?? "—"} tone="indigo" />
          <StatCard icon={Clock3} label="Tổng thời gian học" value={stats ? formatStudyDuration(stats.total_study_minutes) : "—"} tone="amber" />
          <StatCard icon={BookOpenCheck} label="Thời gian mục tiêu/ngày" value={stats?.study_minutes_per_day != null ? `${stats.study_minutes_per_day} phút` : "—"} tone="violet" />
        </div>
      </section>
    </div>
  );
}

function formatStudyDuration(totalMinutes: number): string {
  if (totalMinutes < 60) return `${totalMinutes} phút`;
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  const parts: string[] = [];
  if (days) parts.push(`${days} ngày`);
  if (hours) parts.push(`${hours} giờ`);
  if (minutes) parts.push(`${minutes} phút`);
  return parts.join(" ");
}

function StatCard({ icon: Icon, label, value, tone }: { icon: typeof FileText; label: string; value: string | number; tone: string }) {
  const colors: Record<string, string> = { emerald: "bg-emerald-50 text-emerald-700", blue: "bg-blue-50 text-blue-700", indigo: "bg-indigo-50 text-indigo-700", amber: "bg-amber-50 text-amber-700", violet: "bg-violet-50 text-violet-700" };
  return <div className="rounded-lg border border-slate-200 bg-white p-4"><div className={`grid size-9 place-items-center rounded-lg ${colors[tone] ?? colors.emerald}`}><Icon className="size-5" /></div><p className="mt-4 text-xs font-medium text-slate-500">{label}</p><p className="mt-1 text-2xl font-bold text-slate-900">{value}</p></div>;
}
