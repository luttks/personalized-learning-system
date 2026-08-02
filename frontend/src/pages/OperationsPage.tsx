import { Activity, Database, Play, Search, ServerCog } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { getApiErrorMessage } from "../api/client";
import {
  createTestJob,
  getDatabaseHealth,
  getHealth,
  getJob,
  type HealthStatus,
  type JobStatus,
} from "../api/system";
import { Button, Field, Input, Notice, PageHeader } from "../components/ui";

export function OperationsPage() {
  const [apiHealth, setApiHealth] = useState<HealthStatus | null>(null);
  const [databaseHealth, setDatabaseHealth] = useState<HealthStatus | null>(null);
  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState<JobStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void Promise.all([getHealth(), getDatabaseHealth()])
      .then(([api, database]) => {
        setApiHealth(api);
        setDatabaseHealth(database);
      })
      .catch((requestError) => setError(getApiErrorMessage(requestError)));
  }, []);

  async function startJob() {
    setLoading(true);
    setError("");
    try {
      const result = await createTestJob();
      setJob(result);
      setJobId(result.job_id);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể tạo job."));
    } finally {
      setLoading(false);
    }
  }

  async function inspectJob(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      setJob(await getJob(jobId));
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Không thể đọc trạng thái job."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-7">
      <PageHeader title="Vận hành hệ thống" description="Health check và tác vụ nền Celery." />
      {error && <Notice>{error}</Notice>}

      <section className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <Activity className="size-5 text-emerald-700" />
            <span className={`size-2.5 rounded-full ${apiHealth?.status === "ok" ? "bg-emerald-500" : "bg-amber-400"}`} />
          </div>
          <p className="mt-4 font-bold text-slate-900">Backend API</p>
          <p className="mt-1 text-sm text-slate-500">{apiHealth?.service ?? "Đang kiểm tra"}</p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <Database className="size-5 text-sky-700" />
            <span className={`size-2.5 rounded-full ${databaseHealth?.status === "ok" ? "bg-emerald-500" : "bg-amber-400"}`} />
          </div>
          <p className="mt-4 font-bold text-slate-900">PostgreSQL</p>
          <p className="mt-1 text-sm text-slate-500">{databaseHealth?.database === 1 ? "Kết nối sẵn sàng" : "Đang kiểm tra"}</p>
        </div>
      </section>

      <section className="grid gap-8 border-t border-slate-200 pt-7 lg:grid-cols-[360px_minmax(0,1fr)]">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-bold text-slate-900"><ServerCog className="size-5 text-emerald-700" /> Celery job</h2>
          <Button className="mt-5 w-full" onClick={() => void startJob()} isLoading={loading}>
            <Play className="size-4" /> Chạy test job
          </Button>
          <form className="mt-5 space-y-3" onSubmit={inspectJob}>
            <Field label="Job ID">
              <Input value={jobId} onChange={(event) => setJobId(event.target.value)} required />
            </Field>
            <Button variant="secondary" className="w-full" type="submit" isLoading={loading}>
              <Search className="size-4" /> Kiểm tra trạng thái
            </Button>
          </form>
        </div>

        <div className="min-w-0 border-l-0 border-slate-200 lg:border-l lg:pl-8">
          <h2 className="text-lg font-bold text-slate-900">Kết quả</h2>
          {job ? (
            <dl className="mt-4 divide-y divide-slate-200 border-y border-slate-200 text-sm">
              <div className="flex justify-between gap-4 py-3"><dt className="text-slate-500">Job ID</dt><dd className="break-all text-right font-mono text-xs text-slate-800">{job.job_id}</dd></div>
              <div className="flex justify-between gap-4 py-3"><dt className="text-slate-500">Trạng thái</dt><dd className="font-semibold text-emerald-700">{job.status}</dd></div>
              {job.result !== undefined && <div className="py-3"><dt className="text-slate-500">Kết quả</dt><dd className="mt-2 overflow-auto rounded-lg bg-slate-950 p-3 font-mono text-xs text-slate-100">{JSON.stringify(job.result, null, 2)}</dd></div>}
              {job.error && <div className="py-3 text-red-700">{job.error}</div>}
            </dl>
          ) : (
            <p className="mt-4 text-sm text-slate-500">Chưa có job được chọn.</p>
          )}
        </div>
      </section>
    </div>
  );
}
