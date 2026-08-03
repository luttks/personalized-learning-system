import {
  AlertCircle,
  BookOpen,
  ChevronRight,
  ExternalLink,
  FileText,
  GraduationCap,
  Lightbulb,
  LoaderCircle,
  Search,
  Upload,
  Video,
  X,
} from "lucide-react";
import { useCallback, useRef, useState } from "react";

function GithubIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="24"
      height="24"
      stroke="currentColor"
      strokeWidth="2"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
      <path d="M9 18c-4.51 2-5-2-7-2" />
    </svg>
  );
}

import {
  crawlResources,
  getRecommendations,
  processFile,
  type CrawlResult,
  type ExamParsedResult,
  type GradebookResult,
  type OCRResult,
  type RecommendationResult,
} from "../api/exam_workflow";
import { getApiErrorMessage } from "../api/client";
import { Button } from "../components/ui";

type ActiveTab = "questions" | "raw" | "gradebook" | "recommend" | "crawl";

export function ExamWorkflowPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<OCRResult | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>("questions");

  // AI Recommendation
  const [recommendLoading, setRecommendLoading] = useState(false);
  const [recommendation, setRecommendation] =
    useState<RecommendationResult | null>(null);

  // Crawler
  const [crawlLoading, setCrawlLoading] = useState(false);
  const [crawlResult, setCrawlResult] = useState<CrawlResult | null>(null);
  const [crawlQuery, setCrawlQuery] = useState("");

  // ---- File handling ----

  const handleFiles = useCallback((files: FileList | null) => {
    const f = files?.[0];
    if (f) setFile(f);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles],
  );

  // ---- OCR Submit ----

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setRecommendation(null);
    setCrawlResult(null);

    try {
      const data = await processFile(file);
      setResult(data);
      setActiveTab(data.loai === 2 ? "gradebook" : "questions");
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  // ---- AI Recommendation ----

  const handleRecommend = async () => {
    if (!result || result.loai !== 1) return;
    const exam = result as ExamParsedResult;
    const questionTexts = exam.questions.map((q) => `${q.id}: ${q.content}`);

    setRecommendLoading(true);
    setActiveTab("recommend");
    try {
      const data = await getRecommendations(questionTexts);
      setRecommendation(data);
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setRecommendLoading(false);
    }
  };

  // ---- Crawler ----

  const handleCrawl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!crawlQuery.trim()) return;

    setCrawlLoading(true);
    setActiveTab("crawl");
    try {
      const data = await crawlResources(crawlQuery.trim());
      setCrawlResult(data);
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setCrawlLoading(false);
    }
  };

  // ---- Helper: cast result ----
  const examResult = result?.loai === 1 ? (result as ExamParsedResult) : null;
  const gradebookResult =
    result?.loai === 2 ? (result as GradebookResult) : null;

  return (
    <div className="space-y-6">
      {/* ---- Page header ---- */}
      <div className="flex flex-col gap-4 border-b border-slate-200 pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-950">
            Bóc Tách &amp; OCR Đề Thi
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">
            Trích xuất tự động câu hỏi, công thức toán học LaTeX từ PDF / Ảnh
            bằng Gemini AI. Hỗ trợ phân tích bảng điểm và tìm kiếm tài liệu.
          </p>
        </div>
      </div>

      {/* ---- Upload Zone ---- */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div
            className={`relative flex min-h-40 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 text-center transition ${
              dragActive
                ? "border-emerald-500 bg-emerald-50"
                : "border-slate-300 hover:border-emerald-400 hover:bg-emerald-50/30"
            }`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.doc,.txt,.html,.htm"
              onChange={(e) => handleFiles(e.target.files)}
            />
            <Upload className="size-10 text-emerald-600" />
            <p className="mt-3 text-sm font-medium text-slate-700">
              {file ? file.name : "Kéo thả hoặc click để tải lên đề thi"}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              PDF, PNG, JPG, WEBP, DOCX, TXT
            </p>
            {file && (
              <button
                type="button"
                className="absolute right-3 top-3 rounded-full p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
                aria-label="Xóa file"
              >
                <X className="size-4" />
              </button>
            )}
          </div>

          <Button
            type="submit"
            disabled={!file || loading}
            isLoading={loading}
            className="w-full"
          >
            <FileText className="size-4" />
            {loading ? "Đang xử lý OCR…" : "Bắt đầu Bóc Tách Đề Thi"}
          </Button>
        </form>
      </div>

      {/* ---- Error banner ---- */}
      {error && (
        <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <AlertCircle className="mt-0.5 size-4 shrink-0" />
          <div className="min-w-0 flex-1">{error}</div>
          <button
            type="button"
            onClick={() => setError(null)}
            aria-label="Đóng"
          >
            <X className="size-4" />
          </button>
        </div>
      )}

      {/* ---- Results section ---- */}
      {result && (
        <div className="space-y-4">
          {/* Metadata summary */}
          <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500">
            <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">
              {result.loai === 1 ? "Đề thi" : "Bảng điểm"}
            </span>
            <span>
              Xử lý trong{" "}
              <strong className="text-slate-700">
                {result.elapsed_seconds}s
              </strong>
            </span>
            <span>
              Engine:{" "}
              <strong className="text-slate-700">{result.ocr_engine}</strong>
            </span>
            {examResult && (
              <>
                <span>
                  {examResult.question_count} câu hỏi •{" "}
                  {examResult.formula_count} công thức
                </span>
              </>
            )}
          </div>

          {/* Tab bar */}
          <div className="flex flex-wrap gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1">
            {examResult && (
              <>
                <TabButton
                  active={activeTab === "questions"}
                  onClick={() => setActiveTab("questions")}
                >
                  Câu hỏi ({examResult.question_count})
                </TabButton>
                <TabButton
                  active={activeTab === "raw"}
                  onClick={() => setActiveTab("raw")}
                >
                  Markdown gốc
                </TabButton>
                <TabButton
                  active={activeTab === "recommend"}
                  onClick={() => setActiveTab("recommend")}
                >
                  <Lightbulb className="size-3.5" /> AI Khuyến nghị
                </TabButton>
              </>
            )}
            {gradebookResult && (
              <TabButton
                active={activeTab === "gradebook"}
                onClick={() => setActiveTab("gradebook")}
              >
                Bảng điểm
              </TabButton>
            )}
            <TabButton
              active={activeTab === "crawl"}
              onClick={() => setActiveTab("crawl")}
            >
              <Search className="size-3.5" /> Tìm tài liệu
            </TabButton>
          </div>

          {/* Tab panels */}
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
            {/* ---- Questions tab ---- */}
            {activeTab === "questions" && examResult && (
              <div className="divide-y divide-slate-100">
                {examResult.questions.map((q, idx) => (
                  <div key={idx} className="p-5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-800">
                        {q.id}
                      </span>
                      {q.points && (
                        <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
                          {q.points}
                        </span>
                      )}
                    </div>
                    <pre className="mt-3 whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-700">
                      {q.content}
                    </pre>
                    {q.sub_questions.length > 0 && (
                      <div className="mt-3 space-y-1 border-l-2 border-emerald-200 pl-4">
                        {q.sub_questions.map((sq, si) => (
                          <p key={si} className="text-sm text-slate-600">
                            <strong className="text-emerald-700">
                              {sq.label})
                            </strong>{" "}
                            {sq.text}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* ---- Raw markdown tab ---- */}
            {activeTab === "raw" && examResult && (
              <pre className="max-h-[600px] overflow-auto p-5 font-mono text-sm leading-relaxed text-slate-600">
                {examResult.raw_markdown}
              </pre>
            )}

            {/* ---- Gradebook tab ---- */}
            {activeTab === "gradebook" && gradebookResult && (
              <div className="p-5 space-y-4">
                <div className="flex flex-wrap gap-3 text-sm">
                  {gradebookResult.metadata.grade && (
                    <span className="rounded bg-sky-100 px-2 py-0.5 text-xs font-semibold text-sky-800">
                      Lớp {gradebookResult.metadata.grade}
                    </span>
                  )}
                  {gradebookResult.metadata.semester && (
                    <span className="rounded bg-violet-100 px-2 py-0.5 text-xs font-semibold text-violet-800">
                      HK {gradebookResult.metadata.semester}
                    </span>
                  )}
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 bg-slate-50">
                        <th className="px-3 py-2 text-left font-semibold text-slate-700">
                          Môn / Học sinh
                        </th>
                        {gradebookResult.columns.map((col) => (
                          <th
                            key={col.key}
                            className="px-3 py-2 text-center font-semibold text-slate-700"
                          >
                            {col.label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {gradebookResult.rows.map((row, ri) => (
                        <tr key={ri} className="hover:bg-slate-50">
                          <td className="px-3 py-2 font-medium text-slate-800">
                            {row.subject}
                          </td>
                          {gradebookResult.columns.map((col) => (
                            <td
                              key={col.key}
                              className="px-3 py-2 text-center text-slate-600"
                            >
                              {row[col.key] || "–"}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {gradebookResult.critic && (
                  <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                    <p className="text-sm font-semibold text-emerald-800">
                      Nhận xét
                    </p>
                    <p className="mt-1 text-sm text-emerald-700">
                      {gradebookResult.critic}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* ---- AI Recommendation tab ---- */}
            {activeTab === "recommend" && (
              <div className="p-5">
                {!recommendation && !recommendLoading && (
                  <div className="flex flex-col items-center gap-3 py-8 text-center">
                    <Lightbulb className="size-10 text-amber-400" />
                    <p className="text-sm text-slate-500">
                      Phân tích mức độ khó và đưa ra lời khuyên cho từng câu hỏi
                    </p>
                    <Button onClick={handleRecommend}>
                      <GraduationCap className="size-4" />
                      Bắt đầu phân tích AI
                    </Button>
                  </div>
                )}
                {recommendLoading && (
                  <div className="flex min-h-40 items-center justify-center">
                    <LoaderCircle className="size-6 animate-spin text-emerald-600" />
                    <span className="ml-2 text-sm text-slate-500">
                      Đang phân tích…
                    </span>
                  </div>
                )}
                {recommendation && (
                  <div className="space-y-6">
                    <RecommendGroup
                      title="Nhóm Cơ Bản"
                      tone="emerald"
                      group={recommendation.nhom_co_ban}
                    />
                    <RecommendGroup
                      title="Nhóm Vận Dụng"
                      tone="amber"
                      group={recommendation.nhom_van_dung}
                    />
                    <RecommendGroup
                      title="Nhóm Vận Dụng Cao"
                      tone="red"
                      group={recommendation.nhom_van_dung_cao}
                    />
                  </div>
                )}
              </div>
            )}

            {/* ---- Crawl resources tab ---- */}
            {activeTab === "crawl" && (
              <div className="p-5 space-y-4">
                <form
                  onSubmit={handleCrawl}
                  className="flex gap-2"
                >
                  <input
                    type="text"
                    className="min-h-10 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                    placeholder="Nhập từ khóa tìm kiếm tài liệu, video, bài tập…"
                    value={crawlQuery}
                    onChange={(e) => setCrawlQuery(e.target.value)}
                  />
                  <Button
                    type="submit"
                    disabled={!crawlQuery.trim() || crawlLoading}
                    isLoading={crawlLoading}
                  >
                    <Search className="size-4" />
                    Tìm
                  </Button>
                </form>

                {crawlLoading && (
                  <div className="flex min-h-40 items-center justify-center">
                    <LoaderCircle className="size-6 animate-spin text-emerald-600" />
                    <span className="ml-2 text-sm text-slate-500">
                      Đang tìm kiếm tài liệu…
                    </span>
                  </div>
                )}

                {crawlResult && !crawlLoading && (
                  <div className="space-y-5">
                    <p className="text-xs text-slate-400">
                      Tìm thấy {crawlResult.total_items} kết quả cho "
                      {crawlResult.search_query}"
                    </p>

                    {/* YouTube */}
                    {crawlResult.youtube_tutorials.length > 0 && (
                      <ResourceSection
                        title="Video bài giảng"
                        icon={<Video className="size-4 text-red-500" />}
                      >
                        {crawlResult.youtube_tutorials.map((v, i) => (
                          <a
                            key={i}
                            href={v.watch_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-start gap-3 rounded-lg border border-slate-100 p-3 transition hover:border-slate-300 hover:bg-slate-50"
                          >
                            {v.thumbnail_url && (
                              <img
                                src={v.thumbnail_url}
                                alt=""
                                className="size-16 shrink-0 rounded object-cover"
                              />
                            )}
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-slate-800 line-clamp-2">
                                {v.title}
                              </p>
                              <p className="mt-0.5 text-xs text-slate-400">
                                {v.channel_title}
                              </p>
                            </div>
                            <ExternalLink className="ml-auto size-4 shrink-0 text-slate-300" />
                          </a>
                        ))}
                      </ResourceSection>
                    )}

                    {/* Quizzes */}
                    {crawlResult.quiz_exercises.length > 0 && (
                      <ResourceSection
                        title="Bài tập trực tuyến"
                        icon={<BookOpen className="size-4 text-emerald-500" />}
                      >
                        {crawlResult.quiz_exercises.map((q, i) => (
                          <a
                            key={i}
                            href={q.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block rounded-lg border border-slate-100 p-3 transition hover:border-slate-300 hover:bg-slate-50"
                          >
                            <p className="text-sm font-medium text-slate-800">
                              {q.title}
                            </p>
                            {q.snippet && (
                              <p className="mt-1 text-xs text-slate-500 line-clamp-2">
                                {q.snippet}
                              </p>
                            )}
                          </a>
                        ))}
                      </ResourceSection>
                    )}

                    {/* Academic */}
                    {crawlResult.academic_papers.length > 0 && (
                      <ResourceSection
                        title="Tài liệu học thuật"
                        icon={
                          <GraduationCap className="size-4 text-violet-500" />
                        }
                      >
                        {crawlResult.academic_papers.map((p, i) => (
                          <a
                            key={i}
                            href={p.pdf_url || p.semantic_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block rounded-lg border border-slate-100 p-3 transition hover:border-slate-300 hover:bg-slate-50"
                          >
                            <p className="text-sm font-medium text-slate-800">
                              {p.title}
                            </p>
                            <p className="mt-1 text-xs text-slate-500">
                              {p.authors.join(", ")}
                              {p.year ? ` (${p.year})` : ""}
                              {" · "}
                              {p.citation_count} citations
                            </p>
                          </a>
                        ))}
                      </ResourceSection>
                    )}

                    {/* GitHub */}
                    {crawlResult.github_repos.length > 0 && (
                      <ResourceSection
                        title="GitHub repositories"
                        icon={<GithubIcon className="size-4 text-slate-700" />}
                      >
                        {crawlResult.github_repos.map((r, i) => (
                          <a
                            key={i}
                            href={r.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block rounded-lg border border-slate-100 p-3 transition hover:border-slate-300 hover:bg-slate-50"
                          >
                            <p className="text-sm font-medium text-slate-800">
                              {r.full_name}
                            </p>
                            <p className="mt-1 text-xs text-slate-500">
                              ⭐ {r.stars}
                              {r.language && ` · ${r.language}`}
                              {r.description && ` — ${r.description}`}
                            </p>
                          </a>
                        ))}
                      </ResourceSection>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition ${
        active
          ? "bg-white text-emerald-700 shadow-sm"
          : "text-slate-500 hover:text-slate-700"
      }`}
    >
      {children}
    </button>
  );
}

function ResourceSection({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-700">
        {icon}
        {title}
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function RecommendGroup({
  title,
  tone,
  group,
}: {
  title: string;
  tone: "emerald" | "amber" | "red";
  group: {
    loi_khuyen_chung: string;
    chi_tiet_tung_cau: Array<{
      id_cau: string;
      kien_thuc_can_hoc: string;
      loi_khuyen_ngan: string;
    }>;
  };
}) {
  const colors = {
    emerald: {
      bg: "bg-emerald-50",
      border: "border-emerald-200",
      badge: "bg-emerald-100 text-emerald-800",
      text: "text-emerald-800",
    },
    amber: {
      bg: "bg-amber-50",
      border: "border-amber-200",
      badge: "bg-amber-100 text-amber-800",
      text: "text-amber-800",
    },
    red: {
      bg: "bg-red-50",
      border: "border-red-200",
      badge: "bg-red-100 text-red-800",
      text: "text-red-800",
    },
  }[tone];

  return (
    <div className={`rounded-lg border ${colors.border} ${colors.bg} p-4`}>
      <h3 className={`font-semibold ${colors.text}`}>{title}</h3>
      <p className="mt-1 text-sm text-slate-600">{group.loi_khuyen_chung}</p>
      {group.chi_tiet_tung_cau.length > 0 && (
        <div className="mt-3 space-y-2">
          {group.chi_tiet_tung_cau.map((item, idx) => (
            <div
              key={idx}
              className="flex items-start gap-2 rounded bg-white/70 p-3 text-sm"
            >
              <ChevronRight className="mt-0.5 size-3.5 shrink-0 text-slate-400" />
              <div>
                <span className={`text-xs font-bold ${colors.badge} rounded px-1.5 py-0.5`}>
                  {item.id_cau}
                </span>
                <p className="mt-1 text-slate-700">
                  <strong>Kiến thức:</strong> {item.kien_thuc_can_hoc}
                </p>
                <p className="mt-0.5 text-slate-500">
                  {item.loi_khuyen_ngan}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
