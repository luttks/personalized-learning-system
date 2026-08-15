import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Edit2, RefreshCw, Trash2 } from "lucide-react";

import { listAllSubjects, renameUserSubject, deleteUserSubject, type SubjectSummaryResponse } from "../api/admin_subjects";
import { getApiErrorMessage } from "../api/client";
import { Button, EmptyState, Input, LoadingState, Notice, PageHeader } from "../components/ui";

export function AdminSubjectsPage() {
  const [subjects, setSubjects] = useState<SubjectSummaryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setSubjects(await listAllSubjects());
    } catch (err) {
      setError(getApiErrorMessage(err, "Không thể tải danh sách môn học."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleRename(e: FormEvent, s: SubjectSummaryResponse) {
    e.preventDefault();
    if (!s.user_id || !editValue.trim() || editValue.trim() === s.subject) {
      setEditingKey(null);
      return;
    }
    setError("");
    setSuccess("");
    try {
      await renameUserSubject(s.user_id, s.subject, editValue.trim());
      setSubjects(subjects.map(item => 
        (item.user_id === s.user_id && item.subject === s.subject) 
          ? { ...item, subject: editValue.trim() } 
          : item
      ));
      setSuccess(`Đã đổi tên môn "${s.subject}" thành "${editValue.trim()}".`);
      setEditingKey(null);
    } catch (err) {
      setError(getApiErrorMessage(err, "Không thể đổi tên môn học."));
    }
  }

  async function handleDelete(s: SubjectSummaryResponse) {
    if (!s.user_id) return;
    setError("");
    setSuccess("");
    try {
      await deleteUserSubject(s.user_id, s.subject);
      setSubjects(subjects.filter(item => !(item.user_id === s.user_id && item.subject === s.subject)));
      setSuccess(`Đã xóa môn "${s.subject}".`);
    } catch (err) {
      setError(getApiErrorMessage(err, "Không thể xóa môn học."));
    }
  }

  return (
    <div className="space-y-7">
      <PageHeader
        title="Quản lý Môn học"
        description="Quản lý toàn bộ môn học trong tính năng Học tập cá nhân hóa của tất cả học sinh."
        actions={<Button variant="secondary" onClick={() => void load()}><RefreshCw className="size-4" /> Làm mới</Button>}
      />
      {error && <Notice>{error}</Notice>}
      {success && <Notice tone="success" onClose={() => setSuccess("")}>{success}</Notice>}

      <section>
        <div className="min-w-0">
          {loading ? (
            <LoadingState />
          ) : subjects.length === 0 ? (
            <EmptyState>Chưa có dữ liệu môn học nào trên hệ thống.</EmptyState>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
              <table className="w-full min-w-[800px] text-left text-sm">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Học sinh (Email)</th>
                    <th className="px-4 py-3 font-semibold">Tên môn học</th>
                    <th className="px-4 py-3 font-semibold text-center">Số bài / Đề</th>
                    <th className="px-4 py-3 font-semibold">Lần cuối sử dụng</th>
                    <th className="px-4 py-3 font-semibold text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {subjects.map((s) => {
                    const rowKey = `${s.user_id}-${s.subject}`;
                    const isEditing = editingKey === rowKey;
                    
                    return (
                      <tr key={rowKey} className="hover:bg-slate-50">
                        <td className="px-4 py-4">
                          <span className="font-medium text-slate-800">{s.user_email || "N/A"}</span>
                        </td>
                        <td className="px-4 py-4">
                          {isEditing ? (
                            <form onSubmit={(e) => handleRename(e, s)} className="flex gap-2">
                              <Input 
                                value={editValue} 
                                onChange={(e) => setEditValue(e.target.value)} 
                                autoFocus 
                                className="h-8 py-1"
                              />
                              <Button type="submit" className="h-8 px-2 py-1 text-xs">Lưu</Button>
                              <Button type="button" variant="ghost" onClick={() => setEditingKey(null)} className="h-8 px-2 py-1 text-xs">Hủy</Button>
                            </form>
                          ) : (
                            <span className="font-semibold text-indigo-700">{s.subject}</span>
                          )}
                        </td>
                        <td className="px-4 py-4 text-center text-slate-500">
                          {s.count}
                        </td>
                        <td className="px-4 py-4 text-slate-500">
                          {s.last_used ? new Date(s.last_used).toLocaleDateString("vi-VN") : "N/A"}
                        </td>
                        <td className="px-4 py-4 text-right">
                          {!isEditing && (
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => { setEditingKey(rowKey); setEditValue(s.subject); }}
                                className="text-xs font-semibold text-amber-600 hover:text-amber-800 bg-amber-50 px-2 py-1 rounded"
                                title="Đổi tên"
                              >
                                <Edit2 className="size-4 inline-block mr-1" /> Sửa
                              </button>
                              <button
                                onClick={() => void handleDelete(s)}
                                className="text-xs font-semibold text-red-600 hover:text-red-800 bg-red-50 px-2 py-1 rounded"
                                title="Xóa môn"
                              >
                                <Trash2 className="size-4 inline-block mr-1" /> Xóa
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
