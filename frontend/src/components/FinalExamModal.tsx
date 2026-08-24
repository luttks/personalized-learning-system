import { Loader2, Trophy, X, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { getApiErrorMessage } from "../api/client";
import {
  getFinalExam,
  submitFinalExam,
  type FinalExamQuestion,
  type RoadmapFinalExamStatus,
  type SubmitFinalExamResult,
} from "../api/personalized_roadmap";
import { Button, Notice } from "./ui";

const POLL_INTERVAL_MS = 4000;

export function FinalExamModal({
  roadmapId,
  onClose,
}: {
  roadmapId: string;
  onClose: () => void;
}) {
  const [status, setStatus] = useState<RoadmapFinalExamStatus | "loading">("loading");
  const [questions, setQuestions] = useState<FinalExamQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SubmitFinalExamResult | null>(null);

  async function fetchExam() {
    try {
      const data = await getFinalExam(roadmapId);
      setStatus(data.status);
      setQuestions(data.questions);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Không thể tải bài thi chốt hạ."));
      setStatus("failed");
    }
  }

  useEffect(() => {
    void fetchExam();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roadmapId]);

  useEffect(() => {
    if (status !== "pending" && status !== "generating") return;
    const timer = setInterval(() => void fetchExam(), POLL_INTERVAL_MS);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  async function handleSubmit() {
    if (Object.keys(answers).length < questions.length) {
      setError("Hãy trả lời hết các câu hỏi trước khi nộp bài.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const payload = Object.entries(answers).map(([question_id, selected]) => ({
        question_id: Number.isNaN(Number(question_id)) ? question_id : Number(question_id),
        selected,
      }));
      const res = await submitFinalExam(roadmapId, payload);
      setResult(res);
    } catch (err) {
      setError(getApiErrorMessage(err, "Nộp bài thất bại. Vui lòng thử lại."));
    } finally {
      setSubmitting(false);
    }
  }

  function handleRetry() {
    setStatus("generating");
    void fetchExam();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 p-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600">Bài thi chốt hạ</p>
            <h3 className="text-lg font-bold text-slate-900">Tổng kết toàn bộ lộ trình</h3>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <X className="size-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {error && <Notice tone="error" onClose={() => setError("")}>{error}</Notice>}

          {(status === "loading" || status === "pending" || status === "generating") && (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center text-slate-500">
              <Loader2 className="size-8 animate-spin text-indigo-500" />
              <p className="font-medium">AI đang tổng hợp bài thi chốt hạ từ toàn bộ nội dung đã học...</p>
              <p className="text-xs text-slate-400">Quá trình này diễn ra ngầm, đề khá dài nên có thể mất một chút thời gian.</p>
            </div>
          )}

          {status === "failed" && !error && (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center text-slate-500">
              <XCircle className="size-8 text-red-400" />
              <p className="font-medium">Không thể sinh bài thi lúc này.</p>
              <Button variant="secondary" onClick={handleRetry}>Thử lại</Button>
            </div>
          )}

          {status === "completed" && !result && (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center text-slate-500">
              <Trophy className="size-8 text-indigo-400" />
              <p className="font-medium">Bạn đã hoàn thành bài thi chốt hạ này rồi.</p>
            </div>
          )}

          {status === "ready" && !result && (
            <div className="space-y-5">
              {questions.map((q, qi) => (
                <div key={q.id} className="rounded-xl border border-slate-200 p-4">
                  <p className="mb-3 text-sm font-semibold text-slate-800">
                    Câu {qi + 1}{q.phase_number ? ` (Giai đoạn ${q.phase_number})` : ""}. {q.question}
                  </p>
                  <div className="space-y-2">
                    {(Object.entries(q.options) as [string, string][]).map(([key, text]) => (
                      <label
                        key={key}
                        className={`flex cursor-pointer items-start gap-2 rounded-lg border p-2.5 text-sm transition-colors
                          ${answers[String(q.id)] === key ? "border-indigo-400 bg-indigo-50" : "border-slate-200 hover:bg-slate-50"}`}
                      >
                        <input
                          type="radio"
                          name={`q-${q.id}`}
                          value={key}
                          checked={answers[String(q.id)] === key}
                          onChange={() => setAnswers((prev) => ({ ...prev, [String(q.id)]: key }))}
                          className="mt-0.5"
                        />
                        <span><b>{key}.</b> {text}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {result && (
            <div className="space-y-5">
              <div className="flex items-center gap-3 rounded-xl bg-indigo-50 p-4 text-indigo-800">
                <Trophy className="size-6 shrink-0" />
                <div>
                  <p className="font-bold">Bạn đã hoàn thành lộ trình!</p>
                  <p className="text-sm">Điểm bài thi chốt hạ: {Math.round(result.score_ratio * 100)}%</p>
                </div>
              </div>

              {result.phase_recap.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 mb-2">Tóm tắt hành trình học</p>
                  <div className="space-y-1.5">
                    {result.phase_recap.map((p) => (
                      <div key={p.phase_number} className="flex items-center justify-between rounded-lg border border-slate-200 p-2.5 text-sm">
                        <span className="text-slate-700">Giai đoạn {p.phase_number}: {p.title}</span>
                        <span className={`text-xs font-semibold ${p.status === "passed" ? "text-emerald-600" : "text-amber-600"}`}>
                          {p.status === "passed" ? "Đã đậu" : p.status === "not_passed" ? "Chưa đạt" : p.status}
                          {p.score_ratio !== null && ` (${Math.round(p.score_ratio * 100)}%)`}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="space-y-3">
                {result.results.map((r, i) => (
                  <div
                    key={r.question_id}
                    className={`rounded-xl border p-3 text-sm ${r.is_correct ? "border-emerald-200 bg-emerald-50/50" : "border-red-200 bg-red-50/50"}`}
                  >
                    <p className="font-medium text-slate-800">Câu {i + 1}. {r.question}</p>
                    <p className="mt-1 text-xs text-slate-600">
                      Bạn chọn: <b>{r.selected ?? "(bỏ trống)"}</b> · Đáp án đúng: <b>{r.correct}</b>
                    </p>
                    {r.explanation && <p className="mt-1 text-xs text-slate-500">{r.explanation}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {status === "ready" && !result && (
          <div className="border-t border-slate-200 p-4">
            <Button onClick={handleSubmit} isLoading={submitting} className="w-full justify-center">
              Nộp bài
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
