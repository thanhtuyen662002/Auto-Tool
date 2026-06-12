import type { GlassBadgeVariant } from '../components/glass/GlassBadge';

export type CommonStatus =
  | 'pending'
  | 'queued'
  | 'running'
  | 'processing'
  | 'needs_review'
  | 'approved'
  | 'rendered'
  | 'ready'
  | 'qa_passed'
  | 'qa_warning'
  | 'qa_failed'
  | 'failed'
  | 'error'
  | 'exported'
  | 'success'
  | 'warning'
  | 'skipped'
  | 'unknown';

const labels: Record<CommonStatus, string> = {
  pending: 'Đang chờ',
  queued: 'Đang chờ',
  running: 'Đang xử lý',
  processing: 'Đang xử lý',
  needs_review: 'Cần review',
  approved: 'Đã duyệt',
  rendered: 'Đã render',
  ready: 'Sẵn sàng',
  qa_passed: 'QA ổn',
  qa_warning: 'Cần kiểm tra',
  qa_failed: 'QA lỗi',
  failed: 'Lỗi',
  error: 'Lỗi',
  exported: 'Đã export',
  success: 'Thành công',
  warning: 'Cảnh báo',
  skipped: 'Bỏ qua',
  unknown: 'Không xác định',
};

export function getStatusLabel(status?: string | null): string {
  const key = normalizeStatus(status);
  return labels[key];
}

export function getStatusBadgeVariant(status?: string | null): GlassBadgeVariant {
  const key = normalizeStatus(status);
  if (key === 'failed' || key === 'error' || key === 'qa_failed') return 'failed';
  if (key === 'warning' || key === 'qa_warning' || key === 'needs_review') return 'warning';
  if (key === 'processing' || key === 'running' || key === 'pending' || key === 'queued') return 'processing';
  if (key === 'approved') return 'approved';
  if (key === 'rendered' || key === 'exported') return 'rendered';
  if (key === 'success' || key === 'ready' || key === 'qa_passed') return 'success';
  return 'neutral';
}

function normalizeStatus(status?: string | null): CommonStatus {
  const normalized = (status || 'unknown').trim().toLowerCase().replace(/-/g, '_');
  if (normalized === 'completed') return 'success';
  if (normalized === 'completed_with_errors') return 'warning';
  if (normalized === 'passed') return 'qa_passed';
  if (normalized === 'passed_with_warnings') return 'qa_warning';
  if (normalized === 'review') return 'needs_review';
  if (normalized in labels) return normalized as CommonStatus;
  return 'unknown';
}
