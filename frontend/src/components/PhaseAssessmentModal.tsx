import { CheckCircle2, Loader2, Sparkles, X, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { getApiErrorMessage } from "../api/client";
import {
  getPhaseAssessmentQuestions,
  submitPhaseAssessment,
  type PhaseAssessmentQuestion,
  type PhaseAssessmentStatus,
  type SubmitPhaseAssessmentResult,
} from "../api/personalized_roadmap";
import { Button, Notice } from "./ui";

const POLL_INTERVAL_MS = 4000;

export function PhaseAssessmentModal({
  roadmapId,
  phaseNumber,
  phaseTitle,
  previousPhaseNotPassed = false,
  onClose,
  onCompleted,
}: {
  roadmapId: string;
  phaseNumber: number;
  phaseTitle: string;
  /** Giai đoạn TRƯỚC đó chưa đạt và người học đã bấm "học xong sớm" để bỏ qua — dùng để hiện
   * thông điệp phù hợp trong màn hình kết quả (đậu vẫn khen nhưng nhắc còn hổng kiến thức cũ). */
  previousPhaseNotPassed?: boolean;
  onClose: () => void;
  onCompleted: () => void;
}) {
  const [status, setStatus] = useState<PhaseAssessmentStatus | "loading">("loading");
  const [questions, setQuestions] = useState<PhaseAssessmentQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SubmitPhaseAssessmentResult | null>(null);

  async function fetchQuestions() {
    try {
      const data = await getPhaseAssessmentQuestions(roadmapId, phaseNumber);
      setStatus(data.status);
      setQuestions(data.questions);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Không thể tải bài kiểm tra."));
      setStatus("failed");
    }
  }

  useEffect(() => {
    void fetchQuestions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roadmapId, phaseNumber]);

  useEffect(() => {
    if (status !== "pending" && status !== "generating") return;
    const timer = setInterval(() => void fetchQuestions(), POLL_INTERVAL_MS);
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
      const res = await submitPhaseAssessment(roadmapId, phaseNumber, payload);
      setResult(res);
      // Đậu hay rớt đều mở khóa giai đoạn tiếp theo (chỉ làm bài 1 lần, không có lượt làm lại) —
      // luôn báo cho trang cha tải lại trạng thái, không chỉ khi đậu như trước.
      onCompleted();
    } catch (err) {
      setError(getApiErrorMessage(err, "Nộp bài thất bại. Vui lòng thử lại."));
    } finally {
      setSubmitting(false);
    }
  }

  function handleRetry() {
    setResult(null);
    setAnswers({});
    setStatus("generating");
    void fetchQuestions();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 p-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600">
              Bài kiểm tra cuối giai đoạn {phaseNumber}
            </p>
            <h3 className="text-lg font-bold text-slate-900">{phaseTitle}</h3>
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
              <p className="font-medium">AI đang chuẩn bị bài kiểm tra cho giai đoạn này...</p>
              <p className="text-xs text-slate-400">Quá trình này diễn ra ngầm, thường chỉ mất vài chục giây.</p>
            </div>
          )}

          {status === "failed" && !error && (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center text-slate-500">
              <XCircle className="size-8 text-red-400" />
              <p className="font-medium">Không thể sinh bài kiểm tra lúc này.</p>
              <Button variant="secondary" onClick={handleRetry}>Thử lại</Button>
            </div>
          )}

          {status === "ready" && !result && (
            <div className="space-y-5">
              {questions.map((q, qi) => (
                <div key={q.id} className="rounded-xl border border-slate-200 p-4">
                  <p className="mb-3 text-sm font-semibold text-slate-800">
                    Câu {qi + 1}. {q.question}
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
              <div
                className={`flex items-center gap-3 rounded-xl p-4 ${
                  result.passed
                    ? "bg-emerald-50 text-emerald-800"
                    : result.status === "locked_for_retry"
                      ? "bg-red-50 text-red-800"
                      : "bg-amber-50 text-amber-800"
                }`}
              >
                {result.passed ? (
                  <CheckCircle2 className="size-6 shrink-0" />
                ) : result.status === "locked_for_retry" ? (
                  <XCircle className="size-6 shrink-0" />
                ) : (
                  <Sparkles className="size-6 shrink-0" />
                )}
                <div>
                  <p className="font-bold">
                    {result.passed
                      ? "Chúc mừng, bạn đã đậu!"
                      : result.status === "locked_for_retry"
                        ? "Giai đoạn tiếp theo đã bị khóa để bạn học lại"
                        : "Bạn đã hoàn thành bài kiểm tra này"}
                  </p>
                  <p className="text-sm">
                    Điểm: {Math.round(result.score_ratio * 100)}% (cần đạt {Math.round(result.pass_threshold * 100)}%)
                    {result.passed && result.unlocked_next_phase && " · Đã mở khóa giai đoạn tiếp theo!"}
                    {!result.passed && result.unlocked_next_phase && " · Bạn vẫn tiếp tục sang giai đoạn tiếp theo."}
                  </p>
                  {result.passed && previousPhaseNotPassed && (
                    <p className="text-xs mt-1">
                      Giai đoạn trước đó bạn từng bị hổng kiến thức, nhưng giai đoạn này bạn đã làm
                      rất tốt! Lộ trình cho các giai đoạn tiếp theo vẫn sẽ được điều chỉnh để bù đắp
                      phần kiến thức còn thiếu trước đó.
                    </p>
                  )}
                  {!result.passed && result.status === "locked_for_retry" && (
                    <p className="text-xs mt-1">
                      Vì bạn đã bỏ qua giai đoạn trước đang hổng kiến thức và bài kiểm tra này cũng
                      chưa đạt, hệ thống tạm khóa giai đoạn tiếp theo để bạn học lại chắc chắn hơn.
                      Lịch học giai đoạn này sẽ được cập nhật lại và bạn sẽ nhận thêm email nhắc nhở
                      cho tới khi bài kiểm tra mở lại.
                    </p>
                  )}
                  {!result.passed && result.status !== "locked_for_retry" && (
                    <p className="text-xs mt-1">
                      Bài kiểm tra chỉ làm một lần nên không có lượt làm lại — nhưng dựa trên kết quả
                      này, nội dung các giai đoạn phía sau đang được xem xét điều chỉnh cho phù hợp
                      hơn (diễn ra ngầm, có thể mất vài phút để cập nhật).
                    </p>
                  )}
                </div>
              </div>

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
            <Button
              onClick={handleSubmit}
              isLoading={submitting}
              className="w-full justify-center"
            >
              Nộp bài
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
