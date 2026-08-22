import axios from "axios";
import { Save, UserRound } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "../auth/useAuth";

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
} from "../components/ui";
import type { StudentProfilePayload } from "../types/student";

const initialProfile: StudentProfilePayload = {
  education_level: "under_university",
  grade_level: 10,
  preferred_session_minutes: 30,
  study_days_per_week: 4,
  study_minutes_per_day: 45,
};

export function StudentProfilePage() {
  const [form, setForm] = useState<StudentProfilePayload>(initialProfile);
  const [exists, setExists] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const { user, refreshUser } = useAuth();
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
      if (!exists) {
        // Force refresh user to update has_completed_profile status
        void refreshUser();
      }
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
      {user?.role === "student" && !user.has_completed_profile && (
        <Notice tone="error">Vui lòng điền đầy đủ thông tin trước khi sử dụng các chức năng.</Notice>
      )}
      {error && <Notice>{error}</Notice>}
      {success && <Notice tone="success" onClose={() => setSuccess("")}>{success}</Notice>}

      <form onSubmit={handleSubmit} className="space-y-8">
        <section>
          <div className="mb-4 flex items-center gap-2">
            <UserRound className="size-5 text-emerald-700" />
            <h2 className="text-lg font-bold text-slate-900">Thông tin cơ bản</h2>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="Trình độ học vấn">
              <Select
                value={form.education_level}
                onChange={(event) => {
                  const level = event.target.value as "under_university" | "university";
                  update("education_level", level);
                  if (level === "university") {
                    update("grade_level", 1);
                  } else {
                    update("grade_level", 10);
                  }
                }}
              >
                <option value="under_university">Dưới đại học (Cấp 1-12)</option>
                <option value="university">Đại học</option>
              </Select>
            </Field>
            {form.education_level === "under_university" ? (
              <Field label="Khối lớp">
                <Input
                  type="number"
                  min={1}
                  max={12}
                  value={form.grade_level ?? ""}
                  onChange={(event) => update("grade_level", Number(event.target.value))}
                  required
                />
              </Field>
            ) : (
              <Field label="Sinh viên năm">
                <Input
                  type="number"
                  min={1}
                  max={7}
                  value={form.grade_level ?? ""}
                  onChange={(event) => update("grade_level", Number(event.target.value))}
                  required
                />
              </Field>
            )}
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



        <div className="sticky bottom-0 flex justify-end border-t border-slate-200 bg-slate-50/95 py-4 backdrop-blur">
          <Button type="submit" isLoading={saving}>
            <Save className="size-4" /> {exists ? "Lưu thay đổi" : "Tạo hồ sơ"}
          </Button>
        </div>
      </form>
    </div>
  );
}
