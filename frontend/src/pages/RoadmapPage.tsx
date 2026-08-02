import {
  CalendarDays,
  Clock3,
  Map,
  Plus,
  Trash2,
} from "lucide-react";
import { useState, type FormEvent } from "react";

import { getApiErrorMessage } from "../api/client";
import { createRoadmap } from "../api/learner";
import {
  Button,
  Field,
  Input,
  Notice,
  PageHeader,
  Textarea,
} from "../components/ui";
import type { ConceptInput, Roadmap } from "../types/learner";

interface EditableConcept extends ConceptInput {
  target: boolean;
  prerequisitesText: string;
}

function blankConcept(index: number): EditableConcept {
  return {
    id: `concept-${index}`,
    name: "",
    description: "",
    difficulty: 0.5,
    estimated_minutes: 60,
    prerequisites: [],
    prerequisitesText: "",
    target: true,
  };
}

const today = new Date().toISOString().slice(0, 10);

export function RoadmapPage() {
  const [title, setTitle] = useState("");
  const [startDate, setStartDate] = useState(today);
  const [requiredMastery, setRequiredMastery] = useState(0.7);
  const [concepts, setConcepts] = useState<EditableConcept[]>([blankConcept(1)]);
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function updateConcept(index: number, patch: Partial<EditableConcept>) {
    setConcepts((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setRoadmap(null);
    try {
      const normalizedConcepts: ConceptInput[] = concepts.map(({ target: _target, prerequisitesText, ...concept }) => ({
        ...concept,
        prerequisites: prerequisitesText.split(",").map((item) => item.trim()).filter(Boolean),
      }));
      const result = await createRoadmap({
        title: title || null,
        start_date: startDate,
        required_mastery: requiredMastery,
        target_concept_ids: concepts.filter((item) => item.target).map((item) => item.id),
        concepts: normalizedConcepts,
      });
      setRoadmap(result);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể tạo lộ trình."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-7">
      <PageHeader title="Lộ trình học tập" description="Lập kế hoạch theo đồ thị khái niệm và mức độ thành thạo." />
      {error && <Notice>{error}</Notice>}

      <form onSubmit={handleSubmit} className="space-y-7">
        <section className="grid gap-5 sm:grid-cols-3">
          <Field label="Tên lộ trình">
            <Input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={255} />
          </Field>
          <Field label="Ngày bắt đầu">
            <Input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} required />
          </Field>
          <Field label={`Mức thành thạo yêu cầu: ${Math.round(requiredMastery * 100)}%`}>
            <input className="mt-3 h-2 w-full accent-emerald-700" type="range" min={0.1} max={1} step={0.05} value={requiredMastery} onChange={(event) => setRequiredMastery(Number(event.target.value))} />
          </Field>
        </section>

        <section className="border-t border-slate-200 pt-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Khái niệm</h2>
              <p className="mt-1 text-sm text-slate-500">{concepts.length} mục trong đồ thị kiến thức</p>
            </div>
            <Button type="button" variant="secondary" onClick={() => setConcepts((current) => [...current, blankConcept(current.length + 1)])}>
              <Plus className="size-4" /> Thêm
            </Button>
          </div>

          <div className="mt-5 grid gap-4 xl:grid-cols-2">
            {concepts.map((concept, index) => (
              <div key={index} className="rounded-lg border border-slate-200 bg-white p-5">
                <div className="mb-4 flex items-center justify-between">
                  <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                    <input type="checkbox" className="accent-emerald-700" checked={concept.target} onChange={(event) => updateConcept(index, { target: event.target.checked })} />
                    Khái niệm đích
                  </label>
                  <button
                    type="button"
                    className="grid size-9 place-items-center rounded-lg text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-30"
                    onClick={() => setConcepts((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                    disabled={concepts.length === 1}
                    aria-label="Xóa khái niệm"
                    title="Xóa khái niệm"
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Mã">
                    <Input value={concept.id} onChange={(event) => updateConcept(index, { id: event.target.value })} required maxLength={255} />
                  </Field>
                  <Field label="Tên">
                    <Input value={concept.name} onChange={(event) => updateConcept(index, { name: event.target.value })} required maxLength={255} />
                  </Field>
                  <Field label="Thời lượng (phút)">
                    <Input type="number" min={5} max={10000} value={concept.estimated_minutes} onChange={(event) => updateConcept(index, { estimated_minutes: Number(event.target.value) })} />
                  </Field>
                  <Field label={`Độ khó: ${Math.round(concept.difficulty * 100)}%`}>
                    <input className="mt-3 h-2 w-full accent-emerald-700" type="range" min={0} max={1} step={0.05} value={concept.difficulty} onChange={(event) => updateConcept(index, { difficulty: Number(event.target.value) })} />
                  </Field>
                  <div className="sm:col-span-2">
                    <Field label="Mã kiến thức tiên quyết" hint="Phân tách bằng dấu phẩy">
                      <Input value={concept.prerequisitesText} onChange={(event) => updateConcept(index, { prerequisitesText: event.target.value })} />
                    </Field>
                  </div>
                  <div className="sm:col-span-2">
                    <Field label="Mô tả">
                      <Textarea value={concept.description ?? ""} onChange={(event) => updateConcept(index, { description: event.target.value })} />
                    </Field>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <div className="flex justify-end border-t border-slate-200 pt-4">
          <Button type="submit" isLoading={loading} disabled={!concepts.some((item) => item.target)}>
            <Map className="size-4" /> Tạo lộ trình
          </Button>
        </div>
      </form>

      {roadmap && (
        <section className="border-t border-slate-300 pt-7">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-emerald-700">{roadmap.status}</p>
              <h2 className="mt-1 text-xl font-bold text-slate-900">{roadmap.title}</h2>
              <p className="mt-1 text-sm text-slate-500">{roadmap.subject}</p>
            </div>
            <div className="flex gap-4 text-sm text-slate-600">
              <span className="flex items-center gap-1.5"><Clock3 className="size-4" /> {roadmap.total_estimated_minutes} phút</span>
              <span className="flex items-center gap-1.5"><CalendarDays className="size-4" /> {roadmap.items.length} phiên</span>
            </div>
          </div>
          <ol className="mt-6 border-l-2 border-emerald-200 pl-6">
            {roadmap.items.map((item) => (
              <li key={`${item.sequence}-${item.concept_id}`} className="relative pb-6 last:pb-0">
                <span className="absolute -left-[31px] top-1 grid size-3 rounded-full border-2 border-white bg-emerald-600" />
                <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="font-semibold text-slate-800">{item.title}</p>
                    <p className="text-sm text-slate-500">Phiên {item.session_number} · {item.activity_type}</p>
                  </div>
                  <p className="text-sm text-slate-500">{new Date(item.planned_date).toLocaleDateString("vi-VN")} · {item.estimated_minutes} phút</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
