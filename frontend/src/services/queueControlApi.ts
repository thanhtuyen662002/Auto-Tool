import { apiUrl } from './api';
import type {
  QueueActionResult,
  QueueResourceStatusResponse,
  QueueStateResponse,
} from '../types/project';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json; charset=UTF-8',
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === 'string') detail = payload.detail;
      else if (payload.detail) detail = JSON.stringify(payload.detail);
    } catch {
      const text = await response.text();
      if (text) detail = text;
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export function getQueueState(jobId: string): Promise<QueueStateResponse> {
  return request<QueueStateResponse>(`/queue-control/jobs/${encodeURIComponent(jobId)}`);
}

export function pauseQueueJob(jobId: string): Promise<QueueActionResult> {
  return request<QueueActionResult>(`/queue-control/jobs/${encodeURIComponent(jobId)}/pause`, { method: 'POST' });
}

export function resumeQueueJob(jobId: string): Promise<QueueActionResult> {
  return request<QueueActionResult>(`/queue-control/jobs/${encodeURIComponent(jobId)}/resume`, { method: 'POST' });
}

export function cancelQueueJob(jobId: string): Promise<QueueActionResult> {
  return request<QueueActionResult>(`/queue-control/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' });
}

export function retryFailedQueueItems(jobId: string): Promise<QueueActionResult> {
  return request<QueueActionResult>(`/queue-control/jobs/${encodeURIComponent(jobId)}/retry-failed`, { method: 'POST' });
}

export function retrySelectedQueueItems(jobId: string, itemIds: string[]): Promise<QueueActionResult> {
  return queueAction(jobId, 'retry-selected', itemIds);
}

export function skipSelectedQueueItems(jobId: string, itemIds: string[]): Promise<QueueActionResult> {
  return queueAction(jobId, 'skip-selected', itemIds);
}

export function prioritizeSelectedQueueItems(jobId: string, itemIds: string[]): Promise<QueueActionResult> {
  return queueAction(jobId, 'prioritize-selected', itemIds);
}

export function moveQueueItemsToTop(jobId: string, itemIds: string[]): Promise<QueueActionResult> {
  return queueAction(jobId, 'move-to-top', itemIds);
}

export function moveQueueItemsToBottom(jobId: string, itemIds: string[]): Promise<QueueActionResult> {
  return queueAction(jobId, 'move-to-bottom', itemIds);
}

export function getQueueResourceStatus(jobId: string): Promise<QueueResourceStatusResponse> {
  return request<QueueResourceStatusResponse>(`/queue-control/jobs/${encodeURIComponent(jobId)}/resource-status`);
}

function queueAction(jobId: string, actionPath: string, itemIds: string[]): Promise<QueueActionResult> {
  return request<QueueActionResult>(`/queue-control/jobs/${encodeURIComponent(jobId)}/${actionPath}`, {
    method: 'POST',
    body: JSON.stringify({ item_ids: itemIds }),
  });
}
