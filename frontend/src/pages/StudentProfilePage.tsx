import axios from "axios";
import { Save, UserRound } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { getApiErrorMessage } from "../api/client";
import {
  createStudentProfile,
  getStudentProfile,
  updateStudentProfile,
} from "../api/student";
import {
  Button,
  Field,
  Input,
  LoadingState,
  Notice,
  PageHeader,
  Select,
  Textarea,
} from "../components/ui";
import type { StudentProfilePayload } from "../types/student";

const initialProfile: StudentProfilePayload = {
  date_of_birth: null,
  grade_level: 10,
  school_name: null,
  city: null,
  preferred_learning_mode: "balanced",
  explanation_depth: "medium",
  preferred_session_minutes: 30,
  study_days_per_week: 4,
  study_minutes_per_day: 45,
  favourite_subjects: null,
  difficult_subjects: null,
  learning_notes: null,
};

export function StudentProfilePage() {
  const [form, setForm] = useState<StudentProfilePayload>(initialProfile);
  const [exists, setExists] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    void getStudentProfile()
      .then((profile) => {
        setForm(profile);
        setExists(true);
      })
      .catch((requestError) => {
        if (!axios.isAxiosError(requestError) || requestError.response?.status !== 404) {
          setError(getApiErrorMessage(requestError));
        }
      })
      .finally(() => setLoading(false));
  }, []);

  function update<K extends keyof StudentProfilePayload>(
    key: K,
    value: StudentProfilePayload[K],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const profile = exists
        ? await updateStudentProfile(form)
        : await createStudentProfile(form);
      setForm(profile);
      setExists(true);
      setSuccess("Đã lưu hồ sơ học sinh.");
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể lưu hồ sơ."));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-7">
      <PageHeader
        title="Hồ sơ học sinh"
        description="Thông tin học tập và nhịp học hằng tuần."
      />
      {error && <Notice>{error}</Notice>}
      {success && <Notice tone="success" onClose={() => setSuccess("")}>{success}</Notice>}

      <form onSubmit={handleSubmit} className="space-y-8">
        <section>
          <div className="mb-4 flex items-center gap-2">
            <UserRound className="size-5 text-emerald-700" />
            <h2 className="text-lg font-bold text-slate-900">Thông tin cơ bản</h2>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="Khối lớp">
              <Input
                type="number"
                min={1}
                max={12}
                value={form.grade_level}
                onChange={(event) => update("grade_level", Number(event.target.value))}
                required
              />
            </Field>
            <Field label="Ngày sinh">
              <Input
                type="date"
                value={form.date_of_birth ?? ""}
                onChange={(event) => update("date_of_birth", event.target.value || null)}
              />
            </Field>
            <Field label="Thành phố">
              <Input
                value={form.city ?? ""}
                onChange={(event) => update("city", event.target.value || null)}
                maxLength={100}
              />
            </Field>
            <Field label="Trường học" >
              <Input
                value={form.school_name ?? ""}
                onChange={(event) => update("school_name", event.target.value || null)}
                maxLength={255}
              />
            </Field>
            <Field label="Cách học ưu tiên">
              <Select
                value={form.preferred_learning_mode}
                onChange={(event) => update("preferred_learning_mode", event.target.value as StudentProfilePayload["preferred_learning_mode"])}
              >
                <option value="balanced">Cân bằng</option>
                <option value="visual">Trực quan</option>
                <option value="reading">Đọc tài liệu</option>
                <option value="practice">Thực hành</option>
              </Select>
            </Field>
            <Field label="Độ chi tiết giải thích">
              <Select
                value={form.explanation_depth}
                onChange={(event) => update("explanation_depth", event.target.value as StudentProfilePayload["explanation_depth"])}
              >
                <option value="short">Ngắn gọn</option>
                <option value="medium">Vừa đủ</option>
                <option value="detailed">Chi tiết</option>
              </Select>
            </Field>
          </div>
        </section>

        <section className="border-t border-slate-200 pt-7">
          <h2 className="mb-4 text-lg font-bold text-slate-900">Lịch học</h2>
          <div className="grid gap-5 sm:grid-cols-3">
            <Field label="Thời lượng mỗi phiên (phút)">
              <Input
                type="number" min={10} max={180}
                value={form.preferred_session_minutes}
                onChange={(event) => update("preferred_session_minutes", Number(event.target.value))}
              />
            </Field>
            <Field label="Số ngày mỗi tuần">
              <Input
                type="number" min={1} max={7}
                value={form.study_days_per_week}
                onChange={(event) => update("study_days_per_week", Number(event.target.value))}
              />
            </Field>
            <Field label="Số phút mỗi ngày">
              <Input
                type="number" min={10} max={600}
                value={form.study_minutes_per_day}
                onChange={(event) => update("study_minutes_per_day", Number(event.target.value))}
              />
            </Field>
          </div>
        </section>

        <section className="border-t border-slate-200 pt-7">
          <h2 className="mb-4 text-lg font-bold text-slate-900">Môn học và ghi chú</h2>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Môn học yêu thích">
              <Input value={form.favourite_subjects ?? ""} onChange={(event) => update("favourite_subjects", event.target.value || null)} />
            </Field>
            <Field label="Môn học còn khó">
              <Input value={form.difficult_subjects ?? ""} onChange={(event) => update("difficult_subjects", event.target.value || null)} />
            </Field>
            <div className="sm:col-span-2">
              <Field label="Ghi chú học tập">
                <Textarea value={form.learning_notes ?? ""} onChange={(event) => update("learning_notes", event.target.value || null)} />
              </Field>
            </div>
          </div>
        </section>

        <div className="sticky bottom-0 flex justify-end border-t border-slate-200 bg-slate-50/95 py-4 backdrop-blur">
          <Button type="submit" isLoading={saving}>
            <Save className="size-4" /> {exists ? "Lưu thay đổi" : "Tạo hồ sơ"}
          </Button>
        </div>
      </form>
    </div>
  );
}
