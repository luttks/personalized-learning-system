import { Loader2, MessageCircle, Send, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { getApiErrorMessage } from "../api/client";
import {
  sendDocumentChatMessage,
  type DocumentChatMessage,
} from "../api/document_chat";
import { Notice } from "./ui";

type ChatBubble = {
  role: "user" | "assistant" | "system";
  content: string;
};

const MAX_HISTORY_TURNS = 6;

export function DocumentChatWidget({
  roadmapId,
  subject,
}: {
  roadmapId: string;
  subject: string;
}) {
  const [open, setOpen] = useState(false);
  const [bubbles, setBubbles] = useState<ChatBubble[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [bubbles, sending]);

  async function handleSend(questionOverride?: string) {
    const question = (questionOverride ?? input).trim();
    if (!question || sending) return;

    setError("");
    setInput("");
    const history: DocumentChatMessage[] = bubbles
      .filter((b) => b.role !== "system")
      .slice(-MAX_HISTORY_TURNS)
      .map((b) => ({ role: b.role as "user" | "assistant", content: b.content }));

    setBubbles((prev) => [...prev, { role: "user", content: question }]);
    setSending(true);
    try {
      const res = await sendDocumentChatMessage(roadmapId, question, history);
      if (res.status === "answered") {
        setBubbles((prev) => [...prev, { role: "assistant", content: res.answer ?? "" }]);
      } else {
        setBubbles((prev) => [
          ...prev,
          { role: "system", content: res.message ?? "Chưa thể trả lời câu hỏi này." },
        ]);
      }
    } catch (err) {
      setError(getApiErrorMessage(err, "Gửi câu hỏi thất bại. Vui lòng thử lại."));
      setBubbles((prev) => prev.slice(0, -1)); // bỏ tin nhắn user vừa thêm vì gửi thất bại
    } finally {
      setSending(false);
    }
  }

  function handleRetryLast() {
    const lastUser = [...bubbles].reverse().find((b) => b.role === "user");
    if (lastUser) void handleSend(lastUser.content);
  }

  return (
    <>
      <button
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-6 right-6 z-40 flex size-14 items-center justify-center rounded-full bg-indigo-600 text-white shadow-lg transition-transform hover:scale-105 hover:bg-indigo-700"
        title="Hỏi đáp về tài liệu gốc"
      >
        {open ? <X className="size-6" /> : <MessageCircle className="size-6" />}
      </button>

      {open && (
        <div className="fixed bottom-24 right-6 z-40 flex h-[30rem] w-[calc(100vw-3rem)] max-w-sm flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
          <div className="flex items-center justify-between border-b border-slate-200 bg-indigo-600 p-3.5 text-white">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wider text-indigo-200">Hỏi đáp tài liệu</p>
              <h3 className="truncate text-sm font-bold">{subject}</h3>
            </div>
            <button onClick={() => setOpen(false)} className="shrink-0 rounded-lg p-1.5 hover:bg-white/10">
              <X className="size-4" />
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-3.5">
            {bubbles.length === 0 && (
              <p className="mt-6 text-center text-xs text-slate-400">
                Hỏi bất cứ điều gì về tài liệu gốc bạn đã tải lên — câu trả lời được lấy trực tiếp
                từ nội dung tài liệu.
              </p>
            )}
            {bubbles.map((b, i) =>
              b.role === "system" ? (
                <div key={i} className="rounded-lg bg-amber-50 p-2.5 text-center text-xs text-amber-700">
                  {b.content}
                  {b.content.includes("thử lại") && (
                    <button
                      onClick={handleRetryLast}
                      className="ml-2 font-semibold underline hover:text-amber-900"
                    >
                      Thử lại
                    </button>
                  )}
                </div>
              ) : (
                <div key={i} className={`flex ${b.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
                      b.role === "user"
                        ? "bg-indigo-600 text-white"
                        : "bg-slate-100 text-slate-800"
                    }`}
                  >
                    {b.content}
                  </div>
                </div>
              )
            )}
            {sending && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-xl bg-slate-100 px-3 py-2 text-sm text-slate-500">
                  <Loader2 className="size-3.5 animate-spin" /> Đang trả lời...
                </div>
              </div>
            )}
          </div>

          {error && (
            <div className="px-3 pb-2">
              <Notice tone="error" onClose={() => setError("")}>{error}</Notice>
            </div>
          )}

          <div className="flex items-center gap-2 border-t border-slate-200 p-2.5">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void handleSend();
                }
              }}
              placeholder="Nhập câu hỏi..."
              disabled={sending}
              className="min-h-9 flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-100"
            />
            <button
              onClick={() => void handleSend()}
              disabled={sending || !input.trim()}
              className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send className="size-4" />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
