import axios from "axios";
import {
  BrainCircuit,
  MessageSquareText,
  Save,
  Sparkles,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { getApiErrorMessage } from "../api/client";
import {
  getLearnerProfile,
  understandInput,
  updateLearnerProfile,
} from "../api/learner";
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
import type {
  LearnerProfile,
  LearnerProfilePayload,
  UnderstandingResponse,
} from "../types/learner";

interface LearningForm {
  educationLevel: string;
  subject: string;
  goalType: string;
  goalDescription: string;
  goalTarget: string;
  deadline: string;
  currentLevel: string;
  knownConcepts: string;
  weakConcepts: string;
  misconceptions: string;
  minutesPerDay: number;
  daysPerWeek: number;
  availablePeriods: string;
  preferredSequence: string;
  contentFormats: string;
  preferredDifficulty: string;
}

const initialForm: LearningForm = {
  educationLevel: "",
  subject: "",
  goalType: "exam",
  goalDescription: "",
  goalTarget: "",
  deadline: "",
  currentLevel: "",
  knownConcepts: "",
  weakConcepts: "",
  misconceptions: "",
  minutesPerDay: 45,
  daysPerWeek: 4,
  availablePeriods: "",
  preferredSequence: "",
  contentFormats: "",
  preferredDifficulty: "",
};

const join = (items?: string[]) => items?.join(", ") ?? "";
const split = (value: string) => value.split(",").map((item) => item.trim()).filter(Boolean);

function formFromProfile(profile: LearnerProfile): LearningForm {
  return {
    educationLevel: profile.education_level ?? "",
    subject: profile.subject ?? "",
    goalType: profile.learning_goal?.type ?? "exam",
    goalDescription: profile.learning_goal?.description ?? "",
    goalTarget: String(profile.learning_goal?.target ?? ""),
    deadline: profile.deadline ?? "",
    currentLevel: profile.current_level ?? "",
    knownConcepts: join(profile.known_concepts),
    weakConcepts: join(profile.weak_concepts),
    misconceptions: join(profile.misconceptions),
    minutesPerDay: profile.minutes_per_day ?? 45,
    daysPerWeek: profile.days_per_week ?? 4,
    availablePeriods: join(profile.available_periods),
    preferredSequence: join(profile.learning_preferences?.preferred_sequence),
    contentFormats: join(profile.learning_preferences?.content_formats),
    preferredDifficulty: profile.learning_preferences?.preferred_difficulty ?? "",
  };
}

export function LearningProfilePage() {
  const [mode, setMode] = useState<"profile" | "analysis">("profile");
  const [form, setForm] = useState(initialForm);
  const [profile, setProfile] = useState<LearnerProfile | null>(null);
  const [message, setMessage] = useState("");
  const [context, setContext] = useState("");
  const [analysis, setAnalysis] = useState<UnderstandingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    void getLearnerProfile()
      .then((data) => {
        setProfile(data);
        setForm(formFromProfile(data));
      })
      .catch((requestError) => {
        if (!axios.isAxiosError(requestError) || requestError.response?.status !== 404) {
          setError(getApiErrorMessage(requestError));
        }
      })
      .finally(() => setLoading(false));
  }, []);

  function payloadFromForm(): LearnerProfilePayload {
    return {
      education_level: form.educationLevel || null,
      subject: form.subject || null,
      learning_goal: {
        type: form.goalType || null,
        description: form.goalDescription || null,
        target: form.goalTarget || null,
      },
      deadline: form.deadline || null,
      current_level: form.currentLevel || null,
      known_concepts: split(form.knownConcepts),
      weak_concepts: split(form.weakConcepts),
      misconceptions: split(form.misconceptions),
      minutes_per_day: form.minutesPerDay,
      days_per_week: form.daysPerWeek,
      available_periods: split(form.availablePeriods),
      learning_preferences: {
        preferred_sequence: split(form.preferredSequence),
        content_formats: split(form.contentFormats),
        preferred_difficulty: form.preferredDifficulty || null,
      },
    };
  }

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const updated = await updateLearnerProfile(payloadFromForm());
      setProfile(updated);
      setForm(formFromProfile(updated));
      setSuccess("Đã lưu hồ sơ học tập.");
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể lưu hồ sơ học tập."));
    } finally {
      setSaving(false);
    }
  }

  async function analyze(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setAnalysis(null);
    try {
      const result = await understandInput(message, context);
      setAnalysis(result);
      setProfile(result.profile);
      setForm(formFromProfile(result.profile));
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể phân tích đầu vào."));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-7">
      <PageHeader
        title="Hồ sơ học tập"
        description={profile ? `Phiên bản ${profile.profile_version}` : "Chưa có dữ liệu hồ sơ"}
      />

      <div className="inline-flex rounded-lg border border-slate-300 bg-white p-1">
        <button
          className={`flex min-h-9 items-center gap-2 rounded-md px-3 text-sm font-semibold ${mode === "profile" ? "bg-slate-900 text-white" : "text-slate-600"}`}
          onClick={() => setMode("profile")}
        >
          <BrainCircuit className="size-4" /> Hồ sơ
        </button>
        <button
          className={`flex min-h-9 items-center gap-2 rounded-md px-3 text-sm font-semibold ${mode === "analysis" ? "bg-slate-900 text-white" : "text-slate-600"}`}
          onClick={() => setMode("analysis")}
        >
          <Sparkles className="size-4" /> Phân tích đầu vào
        </button>
      </div>

      {error && <Notice>{error}</Notice>}
      {success && <Notice tone="success" onClose={() => setSuccess("")}>{success}</Notice>}

      {mode === "profile" ? (
        <form onSubmit={saveProfile} className="space-y-8">
          <section className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="Bậc học">
              <Input value={form.educationLevel} onChange={(event) => setForm({ ...form, educationLevel: event.target.value })} />
            </Field>
            <Field label="Môn học">
              <Input value={form.subject} onChange={(event) => setForm({ ...form, subject: event.target.value })} />
            </Field>
            <Field label="Trình độ hiện tại">
              <Input value={form.currentLevel} onChange={(event) => setForm({ ...form, currentLevel: event.target.value })} />
            </Field>
            <Field label="Loại mục tiêu">
              <Select value={form.goalType} onChange={(event) => setForm({ ...form, goalType: event.target.value })}>
                <option value="exam">Kỳ thi</option>
                <option value="skill">Kỹ năng</option>
                <option value="grade">Điểm số</option>
                <option value="project">Dự án</option>
              </Select>
            </Field>
            <Field label="Mục tiêu cụ thể">
              <Input value={form.goalDescription} onChange={(event) => setForm({ ...form, goalDescription: event.target.value })} />
            </Field>
            <Field label="Chỉ tiêu">
              <Input value={form.goalTarget} onChange={(event) => setForm({ ...form, goalTarget: event.target.value })} />
            </Field>
            <Field label="Hạn hoàn thành">
              <Input type="date" value={form.deadline} onChange={(event) => setForm({ ...form, deadline: event.target.value })} />
            </Field>
            <Field label="Phút mỗi ngày">
              <Input type="number" min={10} max={600} value={form.minutesPerDay} onChange={(event) => setForm({ ...form, minutesPerDay: Number(event.target.value) })} />
            </Field>
            <Field label="Ngày mỗi tuần">
              <Input type="number" min={1} max={7} value={form.daysPerWeek} onChange={(event) => setForm({ ...form, daysPerWeek: Number(event.target.value) })} />
            </Field>
          </section>

          <section className="grid gap-5 border-t border-slate-200 pt-7 sm:grid-cols-2">
            <Field label="Khái niệm đã biết" hint="Phân tách bằng dấu phẩy">
              <Textarea value={form.knownConcepts} onChange={(event) => setForm({ ...form, knownConcepts: event.target.value })} />
            </Field>
            <Field label="Khái niệm còn yếu" hint="Phân tách bằng dấu phẩy">
              <Textarea value={form.weakConcepts} onChange={(event) => setForm({ ...form, weakConcepts: event.target.value })} />
            </Field>
            <Field label="Nhận thức sai" hint="Phân tách bằng dấu phẩy">
              <Textarea value={form.misconceptions} onChange={(event) => setForm({ ...form, misconceptions: event.target.value })} />
            </Field>
            <Field label="Khung giờ có thể học" hint="Ví dụ: 19:00-20:00, cuối tuần">
              <Textarea value={form.availablePeriods} onChange={(event) => setForm({ ...form, availablePeriods: event.target.value })} />
            </Field>
          </section>

          <section className="grid gap-5 border-t border-slate-200 pt-7 sm:grid-cols-3">
            <Field label="Thứ tự nội dung" hint="Ví dụ: lý thuyết, ví dụ, bài tập">
              <Input value={form.preferredSequence} onChange={(event) => setForm({ ...form, preferredSequence: event.target.value })} />
            </Field>
            <Field label="Định dạng nội dung" hint="Ví dụ: video, văn bản">
              <Input value={form.contentFormats} onChange={(event) => setForm({ ...form, contentFormats: event.target.value })} />
            </Field>
            <Field label="Độ khó ưu tiên">
              <Select value={form.preferredDifficulty} onChange={(event) => setForm({ ...form, preferredDifficulty: event.target.value })}>
                <option value="">Chưa chọn</option>
                <option value="easy">Cơ bản</option>
                <option value="medium">Trung bình</option>
                <option value="hard">Nâng cao</option>
              </Select>
            </Field>
          </section>

          {profile?.missing_fields.length ? (
            <Notice tone="info">Còn thiếu: {profile.missing_fields.join(", ")}</Notice>
          ) : null}
          <div className="flex justify-end border-t border-slate-200 pt-4">
            <Button type="submit" isLoading={saving}><Save className="size-4" /> Lưu hồ sơ</Button>
          </div>
        </form>
      ) : (
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
          <form onSubmit={analyze} className="space-y-5">
            <Field label="Nội dung học tập">
              <Textarea
                className="min-h-48"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                minLength={3}
                maxLength={10000}
                required
              />
            </Field>
            <Field label="Bối cảnh hội thoại">
              <Textarea value={context} onChange={(event) => setContext(event.target.value)} maxLength={20000} />
            </Field>
            <Button type="submit" isLoading={saving}><Sparkles className="size-4" /> Phân tích</Button>
          </form>

          <aside className="border-l-0 border-slate-200 lg:border-l lg:pl-7">
            <h2 className="flex items-center gap-2 font-bold text-slate-900">
              <MessageSquareText className="size-5 text-emerald-700" /> Kết quả
            </h2>
            {analysis ? (
              <div className="mt-4 space-y-4 text-sm">
                <div>
                  <p className="font-semibold text-slate-700">Trường còn thiếu</p>
                  <p className="mt-1 text-slate-500">{analysis.missing_fields.join(", ") || "Không có"}</p>
                </div>
                <div>
                  <p className="font-semibold text-slate-700">Cần chẩn đoán</p>
                  <p className="mt-1 text-slate-500">{analysis.diagnostic_required ? "Có" : "Không"}</p>
                </div>
                {analysis.clarification_question && (
                  <Notice tone="info">{analysis.clarification_question}</Notice>
                )}
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500">Chưa có kết quả.</p>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
