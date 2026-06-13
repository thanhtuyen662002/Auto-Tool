import { backendUrl } from './api';

export type JobRunStatus =
  | 'pending'
  | 'running'
  | 'paused'
  | 'interrupted'
  | 'recoverable'
  | 'completed'
  | 'completed_with_warnings'
  | 'failed'
  | 'cancelled';

export type RecoveryCandidate = {
  job_id: string;
  project_id?: string | null;
  mode: string;
  status: JobRunStatus;
  project_name?: string | null;
  started_at?: string | null;
  last_checkpoint_at?: string | null;
  total_items: number;
  completed_items: number;
  failed_items: number;
  interrupted_items: number;
  recoverable: boolean;
  recommended_action: 'resume' | 'retry_failed' | 'open_results' | 'mark_cancelled' | 'inspect';
  reason: string;
  summary_path?: string | null;
  warnings: string[];
};

export type ResumeMode = 'continue_pending' | 'retry_failed' | 'retry_interrupted' | 'reconcile_then_continue';

export type ResumeJobRequest = {
  resume_mode: ResumeMode;
  skip_completed_outputs: boolean;
  do_not_overwrite_existing_outputs: boolean;
  max_items?: number | null;
};

export type ResumeJobResult = {
  success: boolean;
  new_job_id?: string | null;
  original_job_id: string;
  resumed_items: number;
  skipped_completed_items: number;
  retry_items: number;
  warnings: string[];
  errors: string[];
  resume_manifest_path?: string | null;
  resume_log_path?: string | null;
  resume_plan: Record<string, unknown>;
};

export type RecoveryCandidatesResponse = {
  success: boolean;
  data: { items: RecoveryCandidate[] };
  warnings: string[];
  errors: string[];
};

export type RecoveryJobResponse = {
  success: boolean;
  data: {
    candidate: RecoveryCandidate;
    checkpoint?: Record<string, unknown> | null;
    video_checkpoints: Array<Record<string, unknown>>;
    reconciliation?: Record<string, unknown> | null;
    job?: Record<string, unknown> | null;
  };
  warnings: string[];
  errors: string[];
};

export type RecoveryActionResponse = {
  success: boolean;
  data: Record<string, unknown>;
  warnings: string[];
  errors: string[];
};

export function getRecoveryCandidates(): Promise<RecoveryCandidatesResponse> {
  return request('/api/job-recovery/candidates');
}

export function getRecoveryJob(jobId: string): Promise<RecoveryJobResponse> {
  return request(`/api/job-recovery/jobs/${encodeURIComponent(jobId)}`);
}

export function reconcileJob(jobId: string): Promise<RecoveryActionResponse> {
  return request(`/api/job-recovery/jobs/${encodeURIComponent(jobId)}/reconcile`, { method: 'POST' });
}

export function resumeJob(jobId: string, payload: ResumeJobRequest): Promise<ResumeJobResult> {
  return request(`/api/job-recovery/jobs/${encodeURIComponent(jobId)}/resume`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function markJobCancelled(jobId: string): Promise<RecoveryActionResponse> {
  return request(`/api/job-recovery/jobs/${encodeURIComponent(jobId)}/mark-cancelled`, { method: 'POST' });
}

export function cleanupJobLock(jobId: string): Promise<RecoveryActionResponse> {
  return request(`/api/job-recovery/jobs/${encodeURIComponent(jobId)}/cleanup-lock`, { method: 'POST' });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(backendUrl(path), {
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    ...init,
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === 'string') message = payload.detail;
      else if (payload.detail) message = JSON.stringify(payload.detail);
    } catch {
      // Keep HTTP status when backend response is not JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

