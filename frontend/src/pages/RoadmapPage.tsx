import { CalendarDays, ChevronLeft, Map, MessageCircle, Send, Trash2 } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { getApiErrorMessage } from "../api/client";
import { type PhaseResources } from "../api/exam";
import { chatWithRoadmap, deletePersonalizedRoadmap, getPersonalizedRoadmaps, type PersonalizedRoadmapResponse } from "../api/personalized_roadmap";
import { Button, Input, Notice, PageHeader } from "../components/ui";
import { RoadmapInlinePanel } from "./PersonalizedLearningPage";

export function RoadmapPage() {
  const [roadmaps, setRoadmaps] = useState<PersonalizedRoadmapResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedRoadmap, setSelectedRoadmap] = useState<PersonalizedRoadmapResponse | null>(null);

  useEffect(() => {
    fetchRoadmaps();
  }, []);

  async function fetchRoadmaps() {
    setLoading(true);
    setError("");
    try {
      const data = await getPersonalizedRoadmaps();
      setRoadmaps(data);
    } catch (err) {
      setError(getApiErrorMessage(err, "Không thể tải danh sách lộ trình."));
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!window.confirm("Bạn có chắc chắn muốn xóa lộ trình này?")) return;
    
    try {
      await deletePersonalizedRoadmap(id);
      setRoadmaps((current) => current.filter((r) => r.id !== id));
      if (selectedRoadmap?.id === id) {
        setSelectedRoadmap(null);
      }
    } catch (err) {
      alert("Xóa thất bại: " + getApiErrorMessage(err));
    }
  }

  if (selectedRoadmap) {
    // Reconstruct phaseResources from the stored data
    const phaseResources: Record<string, PhaseResources> = {};
    selectedRoadmap.roadmap_data.phases?.forEach(p => {
      const pData = p as any;
      if (pData.resources) {
        phaseResources[`phase_${p.phase_number}`] = pData.resources;
      }
    });

    return (
      <div className="space-y-6 max-w-4xl mx-auto">
        <button 
          onClick={() => setSelectedRoadmap(null)}
          className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-800 transition-colors"
        >
          <ChevronLeft className="size-4" /> Quay lại danh sách
        </button>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{selectedRoadmap.title}</h1>
            <p className="mt-1 text-sm text-slate-500">
              Tạo ngày {new Date(selectedRoadmap.created_at).toLocaleDateString("vi-VN")}
            </p>
          </div>
          <Button variant="secondary" onClick={(e) => handleDelete(selectedRoadmap.id, e)} className="text-red-600 hover:bg-red-50 hover:text-red-700 hover:border-red-200">
            <Trash2 className="size-4" /> Xóa lộ trình
          </Button>
        </div>

        <RoadmapInlinePanel 
          roadmap={selectedRoadmap.roadmap_data} 
          phaseResources={phaseResources}
          subject={selectedRoadmap.title}
          goal="Hoàn thành lộ trình"
        />
        <RoadmapDocumentChat roadmap={selectedRoadmap} />
      </div>
    );
  }

  return (
    <div className="space-y-7 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <PageHeader title="Quản lý lộ trình" description="Xem lại các lộ trình học tập cá nhân hóa do AI tạo ra từ kết quả của bạn." />
        <Link to="/personalized">
          <Button>Tạo lộ trình mới</Button>
        </Link>
      </div>

      {error && <Notice>{error}</Notice>}

      {loading ? (
        <div className="py-20 text-center text-slate-500 animate-pulse">
          Đang tải danh sách lộ trình...
        </div>
      ) : roadmaps.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed border-slate-200 py-20 text-center">
          <Map className="mx-auto size-12 text-slate-300" />
          <h3 className="mt-4 text-lg font-semibold text-slate-900">Chưa có lộ trình nào</h3>
          <p className="mt-1 text-sm text-slate-500">Bạn chưa tạo lộ trình học tập nào. Hãy làm một bài kiểm tra để AI thiết kế lộ trình cho bạn.</p>
          <div className="mt-6">
            <Link to="/personalized">
              <Button>Bắt đầu học mới</Button>
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {roadmaps.map((roadmap) => (
            <div 
              key={roadmap.id} 
              onClick={() => setSelectedRoadmap(roadmap)}
              className="group relative flex cursor-pointer flex-col overflow-hidden rounded-xl border border-slate-200 bg-white p-5 text-left transition-all hover:border-emerald-300 hover:shadow-lg hover:shadow-emerald-500/5"
            >
              <div className="mb-3 flex items-start justify-between">
                <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-emerald-50 text-emerald-600">
                  <Map className="size-5" />
                </div>
                <button 
                  onClick={(e) => handleDelete(roadmap.id, e)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg"
                  title="Xóa lộ trình"
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
              <h3 className="font-bold text-slate-900 line-clamp-1 group-hover:text-emerald-700 transition-colors">
                {roadmap.title}
              </h3>
              <p className="mt-1 text-xs text-slate-500">
                Tạo ngày {new Date(roadmap.created_at).toLocaleDateString("vi-VN")}
              </p>
              
              <div className="mt-4 text-sm text-slate-600 line-clamp-2 leading-relaxed">
                {roadmap.overview}
              </div>
              
              <div className="mt-5 flex items-center gap-4 text-sm font-medium text-slate-700">
                <span className="flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1">
                  <CalendarDays className="size-4 text-slate-400" /> 
                  {roadmap.total_weeks} tuần
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function RoadmapDocumentChat({ roadmap }: { roadmap: PersonalizedRoadmapResponse }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<import("../types/course").DocumentChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function ask(event: FormEvent) {
    event.preventDefault();
    const value = question.trim();
    if (!value || !roadmap.source_version_id) return;
    setLoading(true);
    setError("");
    try {
      const result = await chatWithRoadmap(roadmap.id, value, sessionId);
      setSessionId(result.id);
      setMessages((current) => [...current, ...result.messages]);
      setQuestion("");
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể trả lời từ tài liệu nguồn."));
    } finally {
      setLoading(false);
    }
  }

  return <section className="rounded-xl border border-emerald-200 bg-white p-5 shadow-sm"><div className="flex items-center gap-3"><div className="grid size-10 place-items-center rounded-lg bg-emerald-100 text-emerald-700"><MessageCircle className="size-5" /></div><div><h2 className="font-bold text-slate-900">Hỏi đáp theo tài liệu của lộ trình</h2><p className="text-xs text-slate-500">Chatbot dùng tài liệu đã upload trước đó, không cần upload lại.</p></div></div>{!roadmap.source_version_id ? <p className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">Chưa tìm thấy tài liệu nguồn đã lập chỉ mục cho môn học này.</p> : <><div className="mt-4 max-h-80 space-y-3 overflow-y-auto">{messages.map((message) => <div key={message.id} className={`rounded-lg p-3 text-sm ${message.role === "user" ? "ml-8 bg-emerald-50" : "mr-8 bg-slate-100"}`}><p className="whitespace-pre-wrap">{message.content}</p>{message.citations.length > 0 && <p className="mt-2 text-xs text-slate-500">Nguồn: {message.citations.map((citation) => citation.source_label).join(", ")}</p>}</div>)}</div>{error && <Notice>{error}</Notice>}<form className="mt-4 flex gap-2" onSubmit={ask}><Input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Hỏi về nội dung đang học..." maxLength={3000} /><Button type="submit" isLoading={loading} aria-label="Gửi câu hỏi"><Send className="size-4" /></Button></form></>}</section>;
}
