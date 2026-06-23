import {
  createDouyinExportPack,
  getDouyinExportPack,
  getDouyinReupJobResults,
  getJobResults,
  getJobStatus,
  openDouyinExportPack,
  retryFailedDouyinReupJob,
  runFinalOutputQAForJob,
} from '../api/client';
import type {
  CreateExportPackRequest,
  DouyinReupSummary,
  FinalOutputQAJobResponse,
  JobOutput,
  JobStatus,
  PlatformExportPack,
  PlatformExportPackResponse,
  PlatformTarget,
} from '../types/project';
import { arrayField, objectField, unwrapApiResponse } from '../utils/apiResponse';

export interface ResultsViewData {
  outputs: JobOutput[];
  jobStatus: JobStatus | null;
  douyinSummary: DouyinReupSummary | null;
  exportPack: PlatformExportPack | null;
  isDouyinReup: boolean;
}

export async function fetchResultsView(jobId: string): Promise<ResultsViewData> {
  const [jobResults, jobStatus, douyinResults, exportPack] = await Promise.allSettled([
    getJobResults(jobId),
    getJobStatus(jobId),
    getDouyinReupJobResults(jobId),
    getDouyinExportPack(jobId),
  ]);

  if (jobResults.status === 'rejected' && douyinResults.status === 'rejected') {
    throw jobResults.reason instanceof Error ? jobResults.reason : new Error('Could not load job results.');
  }

  const genericPayload = jobResults.status === 'fulfilled' ? unwrapApiResponse(jobResults.value) ?? jobResults.value : null;
  const douyinPayload = douyinResults.status === 'fulfilled' ? unwrapApiResponse(douyinResults.value) ?? douyinResults.value : null;
  const statusPayload = jobStatus.status === 'fulfilled' ? unwrapApiResponse(jobStatus.value) ?? jobStatus.value : null;
  const exportPayload = exportPack.status === 'fulfilled' ? unwrapApiResponse(exportPack.value) ?? exportPack.value : null;
  const genericOutputs = arrayField<JobOutput>(genericPayload && 'outputs' in genericPayload ? genericPayload.outputs : []);
  const douyinOutputs = arrayField<JobOutput>(douyinPayload && 'outputs' in douyinPayload ? douyinPayload.outputs : []);
  const douyinSummary = objectField<DouyinReupSummary>(douyinPayload && 'summary' in douyinPayload ? douyinPayload.summary : null);
  const hasDouyinOutputShape = douyinOutputs.some((output) => {
    const item = output as unknown as Record<string, unknown>;
    return Boolean(
      item.source_video
        || item.reup_mode
        || item.silent_strategy
        || item.subtitle_source
        || item.ocr_frame_count,
    );
  });

  return {
    outputs: douyinOutputs.length ? douyinOutputs : genericOutputs,
    jobStatus: objectField<JobStatus>(statusPayload),
    douyinSummary,
    exportPack: objectField<PlatformExportPack>(exportPayload && 'export_pack' in exportPayload ? exportPayload.export_pack : null),
    isDouyinReup: Boolean(douyinSummary || hasDouyinOutputShape),
  };
}

export function runFinalQA(jobId: string, platformTarget: PlatformTarget): Promise<FinalOutputQAJobResponse> {
  return runFinalOutputQAForJob(jobId, platformTarget);
}

export function createResultsExportPack(
  jobId: string,
  payload: CreateExportPackRequest,
): Promise<PlatformExportPackResponse> {
  return createDouyinExportPack(jobId, payload);
}

export function openResultsExportPack(jobId: string): Promise<{ success: boolean; path: string }> {
  return openDouyinExportPack(jobId);
}

export function retryFailedResults(jobId: string) {
  return retryFailedDouyinReupJob(jobId, {
    retry_steps: ['asr', 'translation', 'render'],
    settings: {},
  });
}
