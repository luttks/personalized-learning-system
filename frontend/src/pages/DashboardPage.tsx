import {
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  FileText,
  GraduationCap,
  Loader2,
  Map,
  Rocket,
  Trophy,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getLearnerStats, type LearnerStats } from "../api/exam";
import { useAuth } from "../auth/useAuth";
import { PageHeader } from "../components/ui";

const statColors = [
  { bg: "bg-indigo-50", border: "border-indigo-200", icon: "text-indigo-600", value: "text-indigo-900" },
  { bg: "bg-emerald-50", border: "border-emerald-200", icon: "text-emerald-600", value: "text-emerald-900" },
  { bg: "bg-amber-50", border: "border-amber-200", icon: "text-amber-600", value: "text-amber-900" },
  { bg: "bg-sky-50", border: "border-sky-200", icon: "text-sky-600", value: "text-sky-900" },
  { bg: "bg-purple-50", border: "border-purple-200", icon: "text-purple-600", value: "text-purple-900" },
  { bg: "bg-rose-50", border: "border-rose-200", icon: "text-rose-600", value: "text-rose-900" },
];

export function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<LearnerStats | null>(null);
  const [statsError, setStatsError] = useState(false);

  useEffect(() => {
    if (user?.role !== "student") return;
    let cancelled = false;
    getLearnerStats()
      .then((data) => {
        if (!cancelled) setStats(data);
      })
      .catch(() => {
        if (!cancelled) setStatsError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [user?.role]);

  if (!user) return null;

  const roleAction =
    user.role === "admin" ? { to: "/users", label: "Quản lý người dùng", icon: Users } : null;

  const statCards = stats
    ? [
        { label: "Tài liệu đã gửi lên", value: stats.total_documents, icon: FileText },
        { label: "Môn học đã tạo", value: stats.total_subjects, icon: GraduationCap },
        { label: "Bài kiểm tra đã phân tích", value: stats.total_exams, icon: ClipboardCheck },
        { label: "Lộ trình đã tạo", value: stats.total_roadmaps, icon: Map },
        { label: "Lộ trình đang áp dụng", value: stats.total_roadmaps_applied, icon: Rocket },
        { label: "Giai đoạn đã vượt qua", value: stats.total_phases_passed, icon: Trophy },
      ]
    : [];

  return (
    <div className="space-y-7">
      <PageHeader
        title={`Xin chào, ${user.full_name}`}
        description="Chào mừng đến với Personalized Learning"
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

      {user.role === "student" && (
        <section>
          <h2 className="text-lg font-bold text-slate-900 mb-4">Hoạt động học tập của bạn</h2>
          {statsError ? (
            <p className="text-sm text-slate-500">Không thể tải số liệu tổng quan lúc này.</p>
          ) : !stats ? (
            <div className="flex items-center gap-2 text-sm text-slate-400 py-8 justify-center">
              <Loader2 className="size-4 animate-spin" /> Đang tải số liệu...
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {statCards.map((card, i) => {
                const c = statColors[i % statColors.length];
                return (
                  <div key={card.label} className={`rounded-xl border ${c.border} ${c.bg} p-4`}>
                    <card.icon className={`size-5 mb-2 ${c.icon}`} />
                    <p className={`text-2xl font-black ${c.value}`}>{card.value}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{card.label}</p>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      <section>
        <h2 className="text-lg font-bold text-slate-900">Phiên hiện tại</h2>
        <dl className="mt-4 divide-y divide-slate-200 border-y border-slate-200 text-sm bg-white rounded-lg px-4 border">
          <div className="flex justify-between gap-4 py-4">
            <dt className="text-slate-500">Trạng thái</dt>
            <dd className="flex items-center gap-2 font-medium text-emerald-700">
              <CheckCircle2 className="size-4" /> Hoạt động
            </dd>
          </div>
          <div className="flex justify-between gap-4 py-4">
            <dt className="text-slate-500">Tạo lúc</dt>
            <dd className="flex items-center gap-2 font-medium text-slate-800">
              <Clock3 className="size-4 text-slate-400" />
              {new Date(user.created_at).toLocaleDateString("vi-VN")}
            </dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
