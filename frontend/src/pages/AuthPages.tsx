import {
  ArrowRight,
  Eye,
  EyeOff,
  GraduationCap,
  LockKeyhole,
  Mail,
  UserRound,
} from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { register } from "../api/auth";
import { getApiErrorMessage } from "../api/client";
import { useAuth } from "../auth/useAuth";
import heroImage from "../assets/hero.png";
import { Button, Field, Input, Notice } from "../components/ui";

function AuthFrame({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-screen bg-white lg:grid-cols-[minmax(0,1fr)_minmax(420px,0.72fr)]">
      <section className="relative hidden overflow-hidden bg-slate-950 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-lg bg-emerald-500 text-slate-950">
            <GraduationCap className="size-6" />
          </div>
          <span className="font-bold">Personalized Learning System</span>
        </div>

        <div className="relative z-10 max-w-xl">
          <p className="mb-4 text-sm font-semibold uppercase text-emerald-400">Learning workspace</p>
          <h1 className="text-4xl font-bold leading-tight">
            Một không gian học tập thích ứng với từng mục tiêu.
          </h1>
          <div className="mt-8 h-1 w-20 bg-emerald-500" />
        </div>

        <img
          src={heroImage}
          alt="Các lớp kiến thức trong hệ thống học tập"
          className="absolute bottom-16 right-8 w-64 opacity-60"
        />
        <p className="text-xs text-slate-500">Personalized Learning System 0.1.0</p>
      </section>

      <section className="flex min-h-screen items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-md">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="grid size-9 place-items-center rounded-lg bg-emerald-600 text-white">
              <GraduationCap className="size-5" />
            </div>
            <span className="text-sm font-bold text-slate-900">Personalized Learning</span>
          </div>
          {children}
        </div>
      </section>
    </main>
  );
}

function PasswordInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <LockKeyhole className="pointer-events-none absolute left-3 top-3 size-4 text-slate-400" />
      <Input
        type={visible ? "text" : "password"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="px-9"
        minLength={8}
        required
        autoComplete="current-password"
      />
      <button
        type="button"
        className="absolute right-1 top-1 grid size-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700"
        onClick={() => setVisible((current) => !current)}
        aria-label={visible ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
      >
        {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  );
}

export function LoginPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await signIn({ email, password });
      const destination = (location.state as { from?: { pathname?: string } })?.from?.pathname;
      navigate(destination || "/", { replace: true });
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Email hoặc mật khẩu không chính xác."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthFrame>
      <p className="text-sm font-semibold text-emerald-700">Chào mừng trở lại</p>
      <h2 className="mt-2 text-3xl font-bold text-slate-950">Đăng nhập</h2>
      <p className="mt-2 text-sm text-slate-500">Tiếp tục phiên học tập của bạn.</p>

      <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
        {error && <Notice>{error}</Notice>}
        <Field label="Email">
          <div className="relative">
            <Mail className="pointer-events-none absolute left-3 top-3 size-4 text-slate-400" />
            <Input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="pl-9"
              required
              autoComplete="email"
            />
          </div>
        </Field>
        <Field label="Mật khẩu">
          <PasswordInput value={password} onChange={setPassword} />
        </Field>
        <Button className="w-full" type="submit" isLoading={loading}>
          Đăng nhập <ArrowRight className="size-4" />
        </Button>
      </form>

      <p className="mt-7 text-center text-sm text-slate-500">
        Chưa có tài khoản?{" "}
        <Link className="font-semibold text-emerald-700 hover:text-emerald-800" to="/register">
          Đăng ký
        </Link>
      </p>
    </AuthFrame>
  );
}

export function RegisterPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register(form);
      await signIn({ email: form.email, password: form.password });
      navigate("/", { replace: true });
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể tạo tài khoản."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthFrame>
      <p className="text-sm font-semibold text-emerald-700">Tài khoản học sinh</p>
      <h2 className="mt-2 text-3xl font-bold text-slate-950">Đăng ký</h2>
      <p className="mt-2 text-sm text-slate-500">Bắt đầu hồ sơ học tập cá nhân.</p>

      <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
        {error && <Notice>{error}</Notice>}
        <Field label="Họ và tên">
          <div className="relative">
            <UserRound className="pointer-events-none absolute left-3 top-3 size-4 text-slate-400" />
            <Input
              value={form.full_name}
              onChange={(event) => setForm({ ...form, full_name: event.target.value })}
              className="pl-9"
              minLength={2}
              maxLength={150}
              required
              autoComplete="name"
            />
          </div>
        </Field>
        <Field label="Email">
          <div className="relative">
            <Mail className="pointer-events-none absolute left-3 top-3 size-4 text-slate-400" />
            <Input
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
              className="pl-9"
              required
              autoComplete="email"
            />
          </div>
        </Field>
        <Field label="Mật khẩu" hint="Tối thiểu 8 ký tự">
          <PasswordInput
            value={form.password}
            onChange={(password) => setForm({ ...form, password })}
          />
        </Field>
        <Button className="w-full" type="submit" isLoading={loading}>
          Tạo tài khoản <ArrowRight className="size-4" />
        </Button>
      </form>

      <p className="mt-7 text-center text-sm text-slate-500">
        Đã có tài khoản?{" "}
        <Link className="font-semibold text-emerald-700 hover:text-emerald-800" to="/login">
          Đăng nhập
        </Link>
      </p>
    </AuthFrame>
  );
}
