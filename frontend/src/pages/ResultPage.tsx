import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getJobResults } from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import ResultList from '../components/ResultList';
import type { JobOutput } from '../types/project';

export default function ResultPage() {
  const { projectId, jobId } = useParams<{ projectId?: string; jobId: string }>();
  const [outputs, setOutputs] = useState<JobOutput[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!jobId) return;
    setLoading(true);
    getJobResults(jobId)
      .then((result) => {
        setOutputs(result.outputs);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Không thể tải kết quả.'))
      .finally(() => setLoading(false));
  }, [jobId]);

  return (
    <main className="mx-auto max-w-6xl px-6 py-6">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Kết quả</h1>
          <p className="mt-1 break-all text-sm text-muted">Job render: {jobId}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {projectId ? (
            <>
              <Link
                className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                to={`/projects/${projectId}/content`}
              >
                Quản lý caption
              </Link>
              <Link
                className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
                to={`/projects/${projectId}/review`}
              >
                Kiểm tra chất lượng video
              </Link>
            </>
          ) : null}
          <Link
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
            to="/"
          >
            Tạo dự án mới
          </Link>
        </div>
      </div>

      <ApiErrorBox error={error} />
      {loading ? (
        <div className="rounded-lg border border-line bg-white p-5 text-sm text-muted shadow-panel">
          Đang tải kết quả...
        </div>
      ) : (
        <ResultList outputs={outputs} />
      )}
    </main>
  );
}
