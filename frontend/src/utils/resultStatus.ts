import type { FinalOutputQASummary, JobOutput } from '../types/project';
import { basenameSafe, compactTextList, getSafePath, getSafeText } from './safeText';
import { getStatusLabel } from './statusLabels';

export type ResultFilter = 'all' | 'ready' | 'warnings' | 'failed' | 'qa_failed' | 'needs_review';
export type ResultSort = 'index_asc' | 'index_desc' | 'status' | 'duration_desc';
export type ResultViewMode = 'grid' | 'compact';
export type ResultHealth = 'ready' | 'warning' | 'failed' | 'needs_review' | 'processing' | 'skipped';
export type ResultQAState = 'passed' | 'warning' | 'failed' | 'not_checked';

type ExtendedResultOutput = JobOutput & {
  bgm_file?: string | null;
  can_retry?: boolean;
  corrected_ass_file?: string | null;
  corrected_srt_file?: string | null;
  error_message?: string | null;
  failed_step?: string | null;
  final_output_qa?: FinalOutputQASummary | null;
  overlay_file?: string | null;
  preset_id?: string | null;
  preset_name?: string | null;
  reup_mode?: string | null;
  silent_plan_file?: string | null;
  silent_strategy?: string | null;
  source_srt_file?: string | null;
  source_video?: string | null;
  subtitle_review_document_id?: string | null;
  translated_srt_file?: string | null;
  voiceover_file?: string | null;
};

export interface ResultFileRef {
  label: string;
  path: string;
}

export interface NormalizedResultItem {
  id: string;
  index: number;
  filename: string;
  path: string;
  rawStatus: string;
  health: ResultHealth;
  qaStatus: ResultQAState;
  qa?: FinalOutputQASummary | null;
  qaScorePercent?: number | null;
  durationSeconds?: number | null;
  durationLabel: string;
  caption: string;
  hashtags: string[];
  warningCount: number;
  errorCount: number;
  warnings: string[];
  errors: string[];
  errorText: string;
  logFile?: string | null;
  subtitleFile?: string | null;
  voiceFile?: string | null;
  sourceVideo?: string | null;
  presetName?: string | null;
  failedStep?: string | null;
  reupMode?: string | null;
  silentStrategy?: string | null;
  canRetry: boolean;
  exportEligible: boolean;
  files: ResultFileRef[];
  searchText: string;
  raw: JobOutput;
}

export interface ResultSummary {
  total: number;
  ready: number;
  warnings: number;
  failed: number;
  needsReview: number;
  qaFailed: number;
  qaChecked: number;
  selected: number;
  exportEligible: number;
  averageQaScore: number | null;
}

export function normalizeResultOutput(output: JobOutput): NormalizedResultItem {
  const extended = output as ExtendedResultOutput;
  const rawStatus = getSafeText(output.status, 'unknown').toLowerCase();
  const warnings = compactTextList(output.warnings);
  const errors = compactStrings([extended.error_message, output.error, ...(output.errors ?? [])]);
  const qa = extended.final_output_qa ?? null;
  const health = getResultHealth(rawStatus, warnings, errors, qa);
  const qaStatus = getQAState(qa);
  const qaScorePercent = typeof qa?.score === 'number' ? normalizeScore(qa.score) : null;
  const filename = basenameSafe(output.path, basenameSafe(extended.source_video, `video-${String(output.index).padStart(3, '0')}`));
  const subtitleFile = firstString(extended.corrected_ass_file, output.subtitle_ass_file, extended.corrected_srt_file, output.subtitle_file, extended.translated_srt_file);
  const voiceFile = firstString(output.normalized_voice_file, output.voice_file, extended.voiceover_file);
  const logFile = firstString(output.log_file, qa?.report_path);
  const durationSeconds = typeof output.duration === 'number' ? output.duration : null;
  const canRetry = Boolean(extended.can_retry || health === 'failed' || qaStatus === 'failed');
  const files = buildFileRefs(output, extended, subtitleFile, voiceFile, logFile);
  const searchText = [
    filename,
    output.path,
    output.caption,
    ...(output.hashtags ?? []),
    rawStatus,
    extended.preset_name,
    extended.source_video,
    extended.failed_step,
    ...warnings,
    ...errors,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  return {
    id: `result-${output.index}-${output.path || filename}`,
    index: output.index,
    filename,
    path: getSafePath(output.path),
    rawStatus,
    health,
    qaStatus,
    qa,
    qaScorePercent,
    durationSeconds,
    durationLabel: durationSeconds == null ? '-' : formatDuration(durationSeconds),
    caption: getSafeText(output.caption, ''),
    hashtags: compactTextList(output.hashtags),
    warningCount: warnings.length + (qaStatus === 'warning' ? Math.max(1, qa?.issues?.length ?? 0) : 0),
    errorCount: errors.length + (qaStatus === 'failed' ? Math.max(1, qa?.issues?.length ?? 0) : 0),
    warnings,
    errors,
    errorText: errors[0] ?? '',
    logFile,
    subtitleFile,
    voiceFile,
    sourceVideo: extended.source_video ?? output.visual_video ?? null,
    presetName: extended.preset_name ?? extended.preset_id ?? output.timeline_template ?? null,
    failedStep: extended.failed_step ?? null,
    reupMode: extended.reup_mode ?? null,
    silentStrategy: extended.silent_strategy ?? null,
    canRetry,
    exportEligible: Boolean(output.path && health !== 'failed' && health !== 'processing'),
    files,
    searchText,
    raw: output,
  };
}

export function summarizeResults(items: NormalizedResultItem[], selectedCount = 0): ResultSummary {
  const qaScores = items
    .map((item) => item.qaScorePercent)
    .filter((score): score is number => typeof score === 'number');
  return {
    total: items.length,
    ready: items.filter((item) => item.health === 'ready').length,
    warnings: items.filter((item) => item.health === 'warning' || item.qaStatus === 'warning').length,
    failed: items.filter((item) => item.health === 'failed').length,
    needsReview: items.filter((item) => item.health === 'needs_review').length,
    qaFailed: items.filter((item) => item.qaStatus === 'failed').length,
    qaChecked: items.filter((item) => item.qaStatus !== 'not_checked').length,
    selected: selectedCount,
    exportEligible: items.filter((item) => item.exportEligible).length,
    averageQaScore: qaScores.length ? Math.round(qaScores.reduce((sum, score) => sum + score, 0) / qaScores.length) : null,
  };
}

export function filterAndSortResults(
  items: NormalizedResultItem[],
  filter: ResultFilter,
  query: string,
  sort: ResultSort,
): NormalizedResultItem[] {
  const normalizedQuery = query.trim().toLowerCase();
  return [...items]
    .filter((item) => matchesFilter(item, filter))
    .filter((item) => !normalizedQuery || item.searchText.includes(normalizedQuery))
    .sort((a, b) => compareResults(a, b, sort));
}

export function statusLabel(health: ResultHealth): string {
  return getStatusLabel(health === 'ready' ? 'ready' : health);
}

export function qaLabel(status: ResultQAState): string {
  const labels: Record<ResultQAState, string> = {
    passed: 'QA ổn',
    warning: 'Cần kiểm tra',
    failed: 'QA lỗi',
    not_checked: 'Chưa QA',
  };
  return labels[status];
}

export function copyText(value?: string | null): Promise<void> {
  if (!value) return Promise.resolve();
  if (navigator.clipboard?.writeText) {
    return navigator.clipboard.writeText(value).catch(() => fallbackCopyText(value));
  }
  return fallbackCopyText(value);
}

export function captionBundle(item: NormalizedResultItem): string {
  const hashtags = item.hashtags.join(' ').trim();
  return [item.caption, hashtags].filter(Boolean).join('\n\n');
}

function getResultHealth(
  status: string,
  warnings: string[],
  errors: string[],
  qa?: FinalOutputQASummary | null,
): ResultHealth {
  if (['failed', 'error'].includes(status) || errors.length || qa?.status === 'failed') return 'failed';
  if (['queued', 'running', 'processing', 'pending'].includes(status)) return 'processing';
  if (['needs_review', 'review'].includes(status)) return 'needs_review';
  if (warnings.length || qa?.status === 'passed_with_warnings' || status === 'warning') return 'warning';
  if (['skipped', 'cancelled', 'canceled'].includes(status)) return 'skipped';
  return 'ready';
}

function getQAState(qa?: FinalOutputQASummary | null): ResultQAState {
  if (!qa) return 'not_checked';
  if (qa.status === 'passed') return 'passed';
  if (qa.status === 'failed') return 'failed';
  return 'warning';
}

function matchesFilter(item: NormalizedResultItem, filter: ResultFilter): boolean {
  if (filter === 'all') return true;
  if (filter === 'ready') return item.health === 'ready';
  if (filter === 'warnings') return item.health === 'warning' || item.qaStatus === 'warning';
  if (filter === 'failed') return item.health === 'failed';
  if (filter === 'qa_failed') return item.qaStatus === 'failed';
  return item.health === 'needs_review';
}

function compareResults(a: NormalizedResultItem, b: NormalizedResultItem, sort: ResultSort): number {
  if (sort === 'index_desc') return b.index - a.index;
  if (sort === 'status') return healthRank(a.health) - healthRank(b.health) || a.index - b.index;
  if (sort === 'duration_desc') return (b.durationSeconds ?? -1) - (a.durationSeconds ?? -1) || a.index - b.index;
  return a.index - b.index;
}

function healthRank(health: ResultHealth): number {
  const ranks: Record<ResultHealth, number> = {
    failed: 0,
    warning: 1,
    needs_review: 2,
    processing: 3,
    ready: 4,
    skipped: 5,
  };
  return ranks[health];
}

function buildFileRefs(
  output: JobOutput,
  extended: ExtendedResultOutput,
  subtitleFile?: string | null,
  voiceFile?: string | null,
  logFile?: string | null,
): ResultFileRef[] {
  const refs: ResultFileRef[] = [
    { label: 'Video', path: output.path },
    { label: 'Source', path: extended.source_video ?? output.visual_video ?? '' },
    { label: 'Subtitle', path: subtitleFile ?? '' },
    { label: 'Voice', path: voiceFile ?? '' },
    { label: 'Music', path: output.music_file ?? extended.bgm_file ?? '' },
    { label: 'Overlay', path: extended.overlay_file ?? '' },
    { label: 'Script', path: output.script_file ?? '' },
    { label: 'Silent plan', path: extended.silent_plan_file ?? '' },
    { label: 'Log', path: logFile ?? '' },
  ];
  const seen = new Set<string>();
  return refs.filter((ref) => {
    if (!ref.path || seen.has(ref.path)) return false;
    seen.add(ref.path);
    return true;
  });
}

function firstString(...values: Array<string | null | undefined>): string | null {
  return values.find((value) => Boolean(value && value.trim())) ?? null;
}

function compactStrings(values?: Array<string | null | undefined>): string[] {
  return (values ?? [])
    .map((value) => (value ?? '').trim())
    .filter(Boolean);
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const rounded = Math.round(seconds);
  const minutes = Math.floor(rounded / 60);
  return `${minutes}:${String(rounded % 60).padStart(2, '0')}`;
}

function normalizeScore(score: number): number {
  return Math.max(0, Math.min(100, Math.round(score <= 1 ? score * 100 : score)));
}

function fallbackCopyText(value: string): Promise<void> {
  try {
    const textarea = document.createElement('textarea');
    textarea.value = value;
    textarea.setAttribute('readonly', 'true');
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
  } catch {
    return Promise.resolve();
  }
  return Promise.resolve();
}
