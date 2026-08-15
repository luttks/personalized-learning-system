import { ChevronLeft, ChevronRight, Plus, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { getApiErrorMessage } from "../api/client";
import { createUser, getUsers, updateUser, deleteUser, type UpdateUserPayload } from "../api/users";
import {
  Button,
  EmptyState,
  Field,
  Input,
  LoadingState,
  Notice,
  PageHeader,
  Select,
} from "../components/ui";
import type { CreateUserPayload, User, UserRole } from "../types/user";
import { roleLabels } from "../types/user";

const pageSize = 20;
const initialForm: CreateUserPayload = {
  full_name: "",
  email: "",
  password: "",
  role: "student",
};

const roleColors: Record<UserRole, string> = {
  student: "bg-emerald-50 text-emerald-700",
  admin: "bg-amber-50 text-amber-700",
};

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [form, setForm] = useState(initialForm);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [editingUser, setEditingUser] = useState<User | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setUsers(await getUsers(pageSize, page * pageSize));
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể tải danh sách người dùng."));
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { void load(); }, [load]);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const user = await createUser(form);
      if (page === 0) setUsers((current) => [user, ...current].slice(0, pageSize));
      setForm(initialForm);
      setSuccess(`Đã tạo tài khoản ${user.email}.`);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể tạo người dùng."));
    } finally {
      setSaving(false);
    }
  }

  async function handleUpdate(event: FormEvent) {
    event.preventDefault();
    if (!editingUser) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload: UpdateUserPayload = {
        full_name: editingUser.full_name,
        role: editingUser.role,
        is_active: editingUser.is_active,
      };
      const updated = await updateUser(editingUser.id, payload);
      setUsers((current) => current.map((u) => (u.id === updated.id ? updated : u)));
      setSuccess(`Đã cập nhật thông tin tài khoản ${updated.email}.`);
      setEditingUser(null);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể cập nhật thông tin."));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(user: User) {
    setError("");
    setSuccess("");
    try {
      await deleteUser(user.id);
      setUsers((current) => current.filter((u) => u.id !== user.id));
      setSuccess(`Đã xóa tài khoản ${user.email}.`);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể xóa người dùng."));
    }
  }

  return (
    <div className="space-y-7">
      <PageHeader
        title="Quản lý người dùng"
        description="Tạo tài khoản và gán vai trò hệ thống."
        actions={<Button variant="secondary" onClick={() => void load()}><RefreshCw className="size-4" /> Làm mới</Button>}
      />
      {error && <Notice>{error}</Notice>}
      {success && <Notice tone="success" onClose={() => setSuccess("")}>{success}</Notice>}

      <section className="grid gap-8 xl:grid-cols-[360px_minmax(0,1fr)]">
        <form className="h-fit rounded-lg border border-slate-200 bg-white p-5" onSubmit={handleCreate}>
          <h2 className="flex items-center gap-2 font-bold text-slate-900"><Plus className="size-5 text-emerald-700" /> Tài khoản mới</h2>
          <div className="mt-5 space-y-4">
            <Field label="Họ và tên">
              <Input value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} minLength={2} maxLength={150} required />
            </Field>
            <Field label="Email">
              <Input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required />
            </Field>
            <Field label="Mật khẩu" hint="Tối thiểu 8 ký tự">
              <Input type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} minLength={8} maxLength={128} required autoComplete="new-password" />
            </Field>
            <Field label="Vai trò">
              <Select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value as UserRole })}>
                <option value="student">Học sinh</option>
                <option value="admin">Quản trị viên</option>
              </Select>
            </Field>
            <Button className="w-full" type="submit" isLoading={saving}><Plus className="size-4" /> Tạo người dùng</Button>
          </div>
        </form>

        <div className="min-w-0">
          {loading ? <LoadingState /> : users.length === 0 ? (
            <EmptyState>Không có người dùng trong trang này.</EmptyState>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Người dùng</th>
                    <th className="px-4 py-3 font-semibold">Vai trò</th>
                    <th className="px-4 py-3 font-semibold">Trạng thái</th>
                    <th className="px-4 py-3 font-semibold">Ngày tạo</th>
                    <th className="px-4 py-3 font-semibold text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {users.map((user) => (
                    <tr key={user.id} className="hover:bg-slate-50">
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          <div className="grid size-9 shrink-0 place-items-center rounded-full bg-slate-100 font-bold text-slate-600">{user.full_name.charAt(0).toUpperCase()}</div>
                          <div className="min-w-0">
                            <p className="truncate font-semibold text-slate-800">{user.full_name}</p>
                            <p className="truncate text-xs text-slate-500">{user.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-4"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${roleColors[user.role]}`}>{roleLabels[user.role]}</span></td>
                      <td className="px-4 py-4"><span className="flex items-center gap-2 text-slate-600"><span className={`size-2 rounded-full ${user.is_active ? "bg-emerald-500" : "bg-red-500"}`} />{user.is_active ? "Hoạt động" : "Đã khóa"}</span></td>
                      <td className="px-4 py-4 text-slate-500">{new Date(user.created_at).toLocaleDateString("vi-VN")}</td>
                      <td className="px-4 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => setEditingUser(user)}
                            className="text-xs font-semibold text-amber-600 hover:text-amber-800 bg-amber-50 px-2 py-1 rounded"
                          >
                            Sửa
                          </button>
                          <button
                            onClick={() => void handleDelete(user)}
                            className="text-xs font-semibold text-red-600 hover:text-red-800 bg-red-50 px-2 py-1 rounded"
                          >
                            Xóa
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-4 flex items-center justify-between">
            <p className="text-sm text-slate-500">Trang {page + 1}</p>
            <div className="flex gap-2">
              <Button variant="secondary" className="px-3" disabled={page === 0 || loading} onClick={() => setPage((current) => current - 1)} aria-label="Trang trước"><ChevronLeft className="size-4" /></Button>
              <Button variant="secondary" className="px-3" disabled={users.length < pageSize || loading} onClick={() => setPage((current) => current + 1)} aria-label="Trang sau"><ChevronRight className="size-4" /></Button>
            </div>
          </div>
        </div>
      </section>

      {/* Modal Sửa User */}
      {editingUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h3 className="mb-4 text-lg font-bold text-slate-900">Sửa thông tin người dùng</h3>
            <form onSubmit={handleUpdate} className="space-y-4">
              <Field label="Họ và tên">
                <Input value={editingUser.full_name} onChange={(e) => setEditingUser({ ...editingUser, full_name: e.target.value })} required />
              </Field>
              <Field label="Vai trò">
                <Select value={editingUser.role} onChange={(e) => setEditingUser({ ...editingUser, role: e.target.value as UserRole })}>
                  <option value="student">Học sinh</option>
                  <option value="admin">Quản trị viên</option>
                </Select>
              </Field>
              <Field label="Trạng thái">
                <Select value={editingUser.is_active ? "true" : "false"} onChange={(e) => setEditingUser({ ...editingUser, is_active: e.target.value === "true" })}>
                  <option value="true">Hoạt động</option>
                  <option value="false">Đã khóa</option>
                </Select>
              </Field>
              <div className="mt-6 flex justify-end gap-3">
                <Button variant="ghost" onClick={() => setEditingUser(null)} type="button">Hủy</Button>
                <Button type="submit" isLoading={saving}>Lưu thay đổi</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
