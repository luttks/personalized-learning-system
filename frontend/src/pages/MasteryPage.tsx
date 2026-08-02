import axios from "axios";
import { BookOpenCheck, Plus, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { getApiErrorMessage } from "../api/client";
import { createLearningEvent, getMastery } from "../api/learner";
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
import type { LearningEventPayload, Mastery } from "../types/learner";

const initialEvent: LearningEventPayload = {
  topic_id: "",
  correct: true,
  difficulty: 0.5,
  hint_used: false,
  attempt_count: 1,
  source: "quiz",
};

export function MasteryPage() {
  const [items, setItems] = useState<Mastery[]>([]);
  const [form, setForm] = useState(initialEvent);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setItems(await getMastery());
    } catch (requestError) {
      if (axios.isAxiosError(requestError) && requestError.response?.status === 404) {
        setItems([]);
      } else {
        setError(getApiErrorMessage(requestError));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function submitEvent(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const updated = await createLearningEvent(form);
      setItems((current) => [updated, ...current.filter((item) => item.topic_id !== updated.topic_id)]);
      setForm({ ...initialEvent, topic_id: form.topic_id });
      setSuccess("Đã ghi nhận kết quả học tập.");
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể ghi nhận kết quả."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-7">
      <PageHeader
        title="Mức độ thành thạo"
        description={`${items.length} chủ đề đã được đánh giá`}
        actions={
          <Button variant="secondary" onClick={() => void load()} disabled={loading}>
            <RefreshCw className="size-4" /> Làm mới
          </Button>
        }
      />
      {error && <Notice>{error}</Notice>}
      {success && <Notice tone="success" onClose={() => setSuccess("")}>{success}</Notice>}

      <section className="grid gap-8 lg:grid-cols-[360px_minmax(0,1fr)]">
        <form onSubmit={submitEvent} className="h-fit rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="flex items-center gap-2 font-bold text-slate-900">
            <Plus className="size-5 text-emerald-700" /> Kết quả mới
          </h2>
          <div className="mt-5 space-y-5">
            <Field label="Mã chủ đề">
              <Input value={form.topic_id} onChange={(event) => setForm({ ...form, topic_id: event.target.value })} required maxLength={255} />
            </Field>
            <Field label="Nguồn">
              <Select value={form.source} onChange={(event) => setForm({ ...form, source: event.target.value })}>
                <option value="quiz">Bài kiểm tra</option>
                <option value="practice">Bài luyện tập</option>
                <option value="lesson">Bài học</option>
                <option value="diagnostic">Chẩn đoán</option>
              </Select>
            </Field>
            <Field label={`Độ khó: ${Math.round(form.difficulty * 100)}%`}>
              <input
                className="h-2 w-full accent-emerald-700"
                type="range" min={0} max={1} step={0.05}
                value={form.difficulty}
                onChange={(event) => setForm({ ...form, difficulty: Number(event.target.value) })}
              />
            </Field>
            <Field label="Số lần thử">
              <Input type="number" min={1} max={100} value={form.attempt_count} onChange={(event) => setForm({ ...form, attempt_count: Number(event.target.value) })} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <label className="flex min-h-10 items-center gap-2 rounded-lg border border-slate-200 px-3 text-sm text-slate-700">
                <input type="checkbox" checked={form.correct} onChange={(event) => setForm({ ...form, correct: event.target.checked })} className="accent-emerald-700" />
                Trả lời đúng
              </label>
              <label className="flex min-h-10 items-center gap-2 rounded-lg border border-slate-200 px-3 text-sm text-slate-700">
                <input type="checkbox" checked={form.hint_used} onChange={(event) => setForm({ ...form, hint_used: event.target.checked })} className="accent-emerald-700" />
                Đã dùng gợi ý
              </label>
            </div>
            <Button className="w-full" type="submit" isLoading={saving}>
              <BookOpenCheck className="size-4" /> Ghi nhận
            </Button>
          </div>
        </form>

        <div className="min-w-0">
          {loading ? <LoadingState /> : items.length === 0 ? (
            <EmptyState>Chưa có dữ liệu thành thạo.</EmptyState>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full min-w-[680px] text-left text-sm">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Chủ đề</th>
                    <th className="px-4 py-3 font-semibold">Thành thạo</th>
                    <th className="px-4 py-3 font-semibold">Độ tin cậy</th>
                    <th className="px-4 py-3 font-semibold">Cấp độ</th>
                    <th className="px-4 py-3 text-right font-semibold">Lỗi lặp lại</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {items.map((item) => (
                    <tr key={item.topic_id} className="hover:bg-slate-50">
                      <td className="px-4 py-4 font-semibold text-slate-800">{item.topic_id}</td>
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-200">
                            <div className="h-full bg-emerald-600" style={{ width: `${item.mastery_score * 100}%` }} />
                          </div>
                          <span>{Math.round(item.mastery_score * 100)}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-slate-600">{Math.round(item.confidence * 100)}%</td>
                      <td className="px-4 py-4"><span className="rounded-full bg-sky-50 px-2 py-1 text-xs font-semibold text-sky-700">{item.level}</span></td>
                      <td className="px-4 py-4 text-right text-slate-600">{item.repeated_errors}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
