import type { DouyinVideoItem, JobStatus } from './project';

export type StartWorkflowMode = 'douyin_voice' | 'silent_immersive';

export type StartChecklistStatus = 'ok' | 'warning' | 'missing';

export type StartPresetViewModel = {
  id: string;
  name: string;
  description: string;
  badge?: string;
  recommended?: boolean;
  reviewRequired?: boolean;
  autoRender?: boolean;
  mode: StartWorkflowMode;
};

export type StartChecklistItem = {
  id: string;
  label: string;
  status: StartChecklistStatus;
  message?: string;
};

export type StartRecentFolder = {
  id: string;
  path: string;
};

export type StartScanSummary = {
  total: number;
  valid: number;
  invalid: number;
  vertical: number;
  square: number;
  horizontal: number;
};

export type StartValidationMessage = {
  id: string;
  tone: 'error' | 'warning' | 'info';
  message: string;
};

export type JobStartedView = {
  jobId: string;
  projectName: string;
  jobStatus: JobStatus | null;
};

export function summarizeStartScan(videos: DouyinVideoItem[], total: number, valid: number, invalid: number): StartScanSummary {
  return videos.reduce<StartScanSummary>(
    (summary, video) => {
      if (video.width > video.height) summary.horizontal += 1;
      else if (video.width === video.height) summary.square += 1;
      else summary.vertical += 1;
      return summary;
    },
    { total, valid, invalid, vertical: 0, square: 0, horizontal: 0 },
  );
}
