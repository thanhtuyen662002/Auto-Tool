import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  approveSubtitleReviewDocument,
  applySubtitleRewrite,
  generateSubtitleRewriteSuggestions,
  getSubtitleReviewDocument,
  getSubtitleQualityReport,
  getVisualStyles,
  listSubtitleReviewDocuments,
  renderApprovedSubtitleReviewDocuments,
  renderSubtitleReviewDocument,
  refreshSubtitleQualityReport,
  rewriteFlaggedSubtitleLines,
  saveSubtitleReviewDocument,
  updateSubtitleReviewLine,
  videoFileUrl,
} from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import type {
  DouyinReupSettings,
  SubtitleDocumentQualityReport,
  SubtitleReviewDocument,
  SubtitleReviewLine,
  SubtitleReviewStatus,
  SubtitleRewriteStyle,
  SubtitleRewriteSuggestion,
  VisualStylePreset,
} from '../types/project';

const STATUS_FILTERS: Array<'all' | SubtitleReviewStatus> = ['all', 'pending', 'needs_fix', 'reviewed', 'approved'];
type QualityLineFilter = 'all' | 'needs_review' | 'critical' | 'warning' | 'edited' | 'unedited';

const DEFAULT_RENDER_SETTINGS: DouyinReupSettings = {
  enabled: true,
  preset_id: 'safe_review',
  preset_name: 'Safe Review',
  source_language: 'zh',
  target_language: 'vi',
  translation_style: 'sat_nghia_troi_chay',
  subtitle_position: 'bottom_overlay',
  translation_provider: 'gemini',
  subtitle_source_priority: ['sidecar_srt', 'embedded_subtitle', 'asr', 'ocr_hardsub'],
  use_sidecar_srt: true,
  use_embedded_subtitle: true,
  use_asr_if_no_subtitle: true,
  asr_provider: 'faster_whisper',
  asr_model_size: 'medium',
  asr_device: 'auto',
  asr_vad_filter: false,
  asr_subtitle_offset_seconds: -0.25,
  use_ocr_if_asr_failed: true,
  use_ocr_if_no_subtitle: true,
  ocr_provider: 'easyocr',
  ocr_language: 'ch',
  ocr_sample_fps: 2.0,
  ocr_region_mode: 'bottom_auto',
  ocr_manual_region: null,
  ocr_min_confidence: 0.55,
  ocr_dedupe_similarity: 0.86,
  ocr_min_text_length: 2,
  ocr_merge_gap_ms: 600,
  ocr_min_duration_ms: 500,
  ocr_max_duration_ms: 6000,
  prefer_ocr_over_asr_when_text_visible: false,
  visual_style_preset_id: 'clean_review_light',
  burn_subtitle: true,
  add_overlay: true,
  keep_original_audio: true,
  add_bgm: true,
  music_folder: '',
  bgm_volume: 0.16,
  original_audio_volume: 0.85,
  duck_bgm_when_voice: false,
  resolution: '1080x1920',
  fps: 30,
  process_mode: 'all',
  max_videos: null,
  selected_video_paths: [],
  keep_temp: false,
  review_subtitles_before_render: false,
  auto_render_after_translation: true,
  auto_mark_low_quality_lines: true,
  enable_subtitle_rewrite_suggestions: true,
  auto_generate_rewrite_for_flagged_lines: false,
  auto_apply_safe_rewrites: false,
  default_rewrite_style: 'short_natural',
};

export default function SubtitleReviewPage() {
  const { documentId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<SubtitleReviewDocument[]>([]);
  const [document, setDocument] = useState<SubtitleReviewDocument | null>(null);
  const [statusFilter, setStatusFilter] = useState<'all' | SubtitleReviewStatus>('all');
  const [visualStyles, setVisualStyles] = useState<VisualStylePreset[]>([]);
  const [visualStyleId, setVisualStyleId] = useState('clean_review_light');
  const [outputFolder, setOutputFolder] = useState('./examples/outputs');
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [qualityReport, setQualityReport] = useState<SubtitleDocumentQualityReport | null>(null);
  const [lineFilter, setLineFilter] = useState<QualityLineFilter>('all');
  const [rewriteSuggestions, setRewriteSuggestions] = useState<Record<number, SubtitleRewriteSuggestion[]>>({});
  const [bulkRewriteOpen, setBulkRewriteOpen] = useState(false);
  const [bulkRewriteStyle, setBulkRewriteStyle] = useState<SubtitleRewriteStyle>('short_natural');
  const [bulkRewriteMaxLines, setBulkRewriteMaxLines] = useState(20);
  const [bulkRewriteIssueTypes, setBulkRewriteIssueTypes] = useState<string[]>(['too_long', 'reading_speed_too_high']);
  const [bulkRewriteAutoApply, setBulkRewriteAutoApply] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const jobId = searchParams.get('job_id');
  const selectedLine = useMemo(
    () => document?.lines.find((line) => line.index === selectedIndex) ?? document?.lines[0] ?? null,
    [document, selectedIndex],
  );
  const visibleDocuments = useMemo(
    () => documents.filter((item) => (statusFilter === 'all' ? true : item.status === statusFilter)),
    [documents, statusFilter],
  );
  const visibleLines = useMemo(() => {
    if (!document) return [];
    return document.lines.filter((line) => {
      if (lineFilter === 'needs_review') return line.quality_needs_review;
      if (lineFilter === 'critical') return line.quality_severity === 'critical';
      if (lineFilter === 'warning') return line.quality_severity === 'warning';
      if (lineFilter === 'edited') return Boolean(line.edited_text?.trim());
      if (lineFilter === 'unedited') return !line.edited_text?.trim();
      return true;
    });
  }, [document, lineFilter]);
  const flaggedLines = useMemo(
    () => document?.lines.filter((line) => line.quality_needs_review) ?? [],
    [document],
  );

  const refreshList = useCallback(async () => {
    const response = await listSubtitleReviewDocuments({ job_id: jobId, status: statusFilter === 'all' ? null : statusFilter });
    setDocuments(response.items);
  }, [jobId, statusFilter]);

  const refreshDocument = useCallback(async () => {
    if (!documentId) return;
    const [next, quality] = await Promise.all([
      getSubtitleReviewDocument(documentId),
      getSubtitleQualityReport(documentId),
    ]);
    setDocument(next);
    setQualityReport(quality);
    setSelectedIndex((current) => current ?? next.lines[0]?.index ?? null);
    setVisualStyleId(next.corrected_ass_path ? visualStyleId : 'clean_review_light');
  }, [documentId, visualStyleId]);

  const refreshQuality = useCallback(async () => {
    if (!documentId) return;
    const quality = await refreshSubtitleQualityReport(documentId);
    const next = await getSubtitleReviewDocument(documentId);
    setQualityReport(quality);
    setDocument(next);
  }, [documentId]);

  useEffect(() => {
    getVisualStyles()
      .then((response) => setVisualStyles(response.presets))
      .catch(() => setVisualStyles([]));
  }, []);

  useEffect(() => {
    setError(null);
    refreshList().catch((err) => setError(err instanceof Error ? err.message : 'Could not load subtitle reviews.'));
  }, [refreshList]);

  useEffect(() => {
    setError(null);
    if (!documentId) {
      setDocument(null);
      setQualityReport(null);
      return;
    }
    refreshDocument().catch((err) => setError(err instanceof Error ? err.message : 'Could not load subtitle document.'));
  }, [documentId, refreshDocument]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (!document) return;
      if (event.ctrlKey && event.key.toLowerCase() === 's') {
        event.preventDefault();
        void handleSave(false);
      }
      if (event.ctrlKey && event.key === 'Enter' && selectedLine) {
        event.preventDefault();
        void markLine(selectedLine.index, 'reviewed');
      }
      if (event.altKey && event.key === 'ArrowDown') {
        event.preventDefault();
        selectRelativeLine(1);
      }
      if (event.altKey && event.key === 'ArrowUp') {
        event.preventDefault();
        selectRelativeLine(-1);
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  function selectLine(line: SubtitleReviewLine) {
    setSelectedIndex(line.index);
    if (videoRef.current) {
      videoRef.current.currentTime = Math.max(0, line.start_ms / 1000);
    }
  }

  function selectRelativeLine(offset: number) {
    if (!document || !selectedLine) return;
    const current = document.lines.findIndex((line) => line.index === selectedLine.index);
    const next = document.lines[Math.max(0, Math.min(document.lines.length - 1, current + offset))];
    if (next) selectLine(next);
  }

  function selectFlaggedLine(offset: number) {
    if (!flaggedLines.length) return;
    const current = flaggedLines.findIndex((line) => line.index === selectedLine?.index);
    const nextIndex = current < 0
      ? 0
      : (current + offset + flaggedLines.length) % flaggedLines.length;
    selectLine(flaggedLines[nextIndex]);
  }

  function updateLocalLine(lineIndex: number, patch: Partial<SubtitleReviewLine>) {
    setDocument((current) =>
      current
        ? {
            ...current,
            lines: current.lines.map((line) => (line.index === lineIndex ? { ...line, ...patch } : line)),
          }
        : current,
    );
  }

  async function markLine(lineIndex: number, status: SubtitleReviewStatus) {
    if (!document) return;
    setSaving(true);
    setError(null);
    try {
      const line = document.lines.find((item) => item.index === lineIndex);
      const updated = await updateSubtitleReviewLine(document.id, lineIndex, {
        edited_text: line?.edited_text ?? null,
        status,
        user_note: line?.user_note ?? null,
      });
      updateLocalLine(lineIndex, updated);
      await refreshQuality();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update subtitle line.');
    } finally {
      setSaving(false);
    }
  }

  async function handleSuggestRewrite(lineIndex: number) {
    if (!document) return;
    setSaving(true);
    setError(null);
    try {
      const response = await generateSubtitleRewriteSuggestions(document.id, lineIndex, {
        style: 'short_natural',
        suggestion_count: 3,
        max_chars: null,
        preserve_keywords: [],
        use_ai: true,
      });
      setRewriteSuggestions((current) => ({ ...current, [lineIndex]: response.items }));
      setMessage(`Created ${response.items.length} rewrite suggestion(s) for line ${lineIndex}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not suggest a shorter translation.');
    } finally {
      setSaving(false);
    }
  }

  async function handleApplyRewrite(lineIndex: number, suggestion: SubtitleRewriteSuggestion) {
    if (!document) return;
    if (
      suggestion.safety_warnings.some((warning) => warning.startsWith('critical:'))
      && !window.confirm('This suggestion has a critical safety warning. Apply it anyway?')
    ) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await applySubtitleRewrite(document.id, lineIndex, suggestion.id);
      await refreshDocument();
      setRewriteSuggestions((current) => ({ ...current, [lineIndex]: [] }));
      setMessage(`Applied rewrite to line ${lineIndex} and refreshed quality score.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not apply rewrite suggestion.');
    } finally {
      setSaving(false);
    }
  }

  function toggleBulkIssue(issueType: string) {
    setBulkRewriteIssueTypes((current) =>
      current.includes(issueType) ? current.filter((item) => item !== issueType) : [...current, issueType],
    );
  }

  async function handleBulkRewrite() {
    if (!document) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await rewriteFlaggedSubtitleLines(document.id, {
        style: bulkRewriteStyle,
        max_lines: bulkRewriteMaxLines,
        only_issue_types: bulkRewriteIssueTypes,
        auto_apply_safe_suggestions: bulkRewriteAutoApply,
      });
      const grouped: Record<number, SubtitleRewriteSuggestion[]> = {};
      for (const suggestion of response.items) {
        grouped[suggestion.line_index] = [...(grouped[suggestion.line_index] ?? []), suggestion];
      }
      setRewriteSuggestions((current) => ({ ...current, ...grouped }));
      await refreshDocument();
      setLineFilter('needs_review');
      setBulkRewriteOpen(false);
      setMessage(
        `Created ${response.suggestions_created} suggestion(s) for ${response.processed_lines} flagged line(s). `
        + `${response.auto_applied} safely auto-applied.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not generate bulk rewrite suggestions.');
    } finally {
      setSaving(false);
    }
  }

  async function handleSave(markAsReviewed: boolean) {
    if (!document) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const saved = await saveSubtitleReviewDocument(document.id, {
        lines: document.lines,
        mark_as_reviewed: markAsReviewed,
      });
      setDocument(saved);
      setQualityReport(await getSubtitleQualityReport(document.id));
      setMessage('Saved.');
      await refreshList();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save subtitle document.');
    } finally {
      setSaving(false);
    }
  }

  async function handleApprove() {
    if (!document) return;
    const criticalCount = qualityReport?.critical_count ?? document.quality_critical_count;
    const flaggedCount = qualityReport?.needs_review_count ?? document.quality_needs_review_count;
    if (
      criticalCount > 0
      && !window.confirm(`Còn ${criticalCount} dòng phụ đề lỗi nghiêm trọng. Bạn vẫn muốn approve?`)
    ) return;
    if (
      criticalCount === 0
      && flaggedCount > 0
      && !window.confirm(`Còn ${flaggedCount} dòng cần kiểm tra. Bạn vẫn muốn approve?`)
    ) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const approved = await approveSubtitleReviewDocument(document.id, {
        generate_ass: true,
        visual_style_preset_id: visualStyleId,
      });
      setDocument(approved);
      setQualityReport(await getSubtitleQualityReport(document.id));
      setMessage(approved.approval_quality_warning || 'Approved.');
      await refreshList();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not approve subtitle document.');
    } finally {
      setSaving(false);
    }
  }

  async function handleRenderCurrent() {
    if (!document) return;
    setSaving(true);
    setError(null);
    try {
      const response = await renderSubtitleReviewDocument(document.id, {
        output_folder: outputFolder,
        settings: { ...DEFAULT_RENDER_SETTINGS, visual_style_preset_id: visualStyleId },
      });
      navigate(`/queue/${document.project_id ?? 'subtitle-review'}/${response.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not queue render.');
    } finally {
      setSaving(false);
    }
  }

  async function handleRenderAllApproved() {
    setSaving(true);
    setError(null);
    try {
      const response = await renderApprovedSubtitleReviewDocuments({
        job_id: jobId,
        output_folder: outputFolder,
        settings: { ...DEFAULT_RENDER_SETTINGS, visual_style_preset_id: visualStyleId },
      });
      navigate(`/queue/subtitle-review/${response.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not queue approved renders.');
    } finally {
      setSaving(false);
    }
  }

  function resetAllEdits() {
    setDocument((current) =>
      current
        ? {
            ...current,
            lines: current.lines.map((line) => ({ ...line, edited_text: null, status: 'pending' })),
          }
        : current,
    );
  }

  return (
    <main className="mx-auto grid max-w-7xl gap-5 px-6 py-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Subtitle Review</h1>
          <p className="mt-1 text-sm text-muted">Review and correct Vietnamese subtitles before final Douyin render.</p>
        </div>
        <Link className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand" to="/douyin-reup">
          Douyin Reup
        </Link>
      </div>

      <ApiErrorBox error={error} />
      {message ? <div className="rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">{message}</div> : null}

      {!document ? (
        <section className="grid gap-4 rounded-md border border-line bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {STATUS_FILTERS.map((status) => (
                <button
                  key={status}
                  className={`rounded-md px-3 py-2 text-sm font-semibold ${
                    statusFilter === status ? 'bg-brand text-white' : 'border border-line bg-white text-ink hover:border-brand'
                  }`}
                  type="button"
                  onClick={() => setStatusFilter(status)}
                >
                  {status === 'all' ? 'All' : status}
                </button>
              ))}
            </div>
            <button className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white disabled:bg-blue-200" type="button" disabled={saving} onClick={handleRenderAllApproved}>
              Render Approved Videos
            </button>
          </div>
          <div className="overflow-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-line text-xs uppercase text-muted">
                <tr>
                  <th className="py-2 pr-3">Video</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Source</th>
                  <th className="py-2 pr-3">Lines</th>
                  <th className="py-2 pr-3">Edited</th>
                  <th className="py-2 pr-3">Warnings</th>
                  <th className="py-2 pr-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {visibleDocuments.map((item) => (
                  <tr className="border-b border-line last:border-b-0" key={item.id}>
                    <td className="max-w-xl break-all py-3 pr-3">
                      <div className="font-medium text-ink">{fileName(item.video_path)}</div>
                      <div className="text-xs text-muted">{item.video_path}</div>
                    </td>
                    <td className="py-3 pr-3">{item.status}</td>
                    <td className="py-3 pr-3">{formatSourceType(item.source_type)}</td>
                    <td className="py-3 pr-3">{item.line_count}</td>
                    <td className="py-3 pr-3">{item.edited_count}</td>
                    <td className="py-3 pr-3">{item.warning_count}</td>
                    <td className="py-3 pr-3">
                      <Link className="rounded-md bg-brand px-3 py-2 text-xs font-semibold text-white" to={`/subtitle-review/${item.id}`}>
                        Review
                      </Link>
                    </td>
                  </tr>
                ))}
                {!visibleDocuments.length ? (
                  <tr>
                    <td className="py-6 text-muted" colSpan={7}>
                      No subtitle review documents.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <section className="grid gap-5 lg:grid-cols-[minmax(320px,0.42fr)_minmax(0,0.58fr)]">
          <div className="grid gap-4">
            <div className="rounded-md border border-line bg-white p-4">
              <video ref={videoRef} className="aspect-[9/16] max-h-[620px] w-full rounded-md bg-black object-contain" src={videoFileUrl(document.video_path)} controls />
              {selectedLine ? (
                <div className="mt-3 rounded-md bg-black px-4 py-3 text-center text-base font-semibold text-white">
                  {selectedLine.edited_text || selectedLine.translated_text}
                </div>
              ) : null}
            </div>
            <div className="grid gap-3 rounded-md border border-line bg-white p-4 text-sm">
              <div className="grid gap-2 sm:grid-cols-2">
                <Info label="Status" value={document.status} />
                <Info label="Source" value={formatSourceType(document.source_type)} />
                <Info label="Lines" value={`${document.reviewed_count}/${document.line_count}`} />
                <Info label="Edited" value={String(document.edited_count)} />
                <Info label="Warnings" value={String(document.warning_count)} />
              </div>
              {qualityReport ? (
                <div className="grid gap-3 rounded-md border border-line bg-surface p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-ink">Subtitle Quality</div>
                    <button
                      className="rounded-md border border-line bg-white px-2 py-1 text-xs font-semibold text-ink hover:border-brand"
                      type="button"
                      disabled={saving}
                      onClick={() => void refreshQuality()}
                    >
                      Refresh score
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <Info label="Average score" value={String(Math.round(qualityReport.average_score * 100)) + '%'} />
                    <Info label="Needs review" value={String(qualityReport.needs_review_count)} />
                    <Info label="Critical" value={String(qualityReport.critical_count)} />
                    <Info label="Warnings" value={String(qualityReport.warning_count)} />
                  </div>
                  {qualityReport.critical_count > 0 ? (
                    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
                      Có dòng phụ đề lỗi nghiêm trọng. Nên sửa trước khi approve.
                    </div>
                  ) : null}
                </div>
              ) : null}
              <label>
                <span className="mb-1 block text-xs font-semibold uppercase text-muted">Visual style</span>
                <select className="h-10 w-full rounded-md border border-line bg-white px-3" value={visualStyleId} onChange={(event) => setVisualStyleId(event.target.value)}>
                  {visualStyles.map((style) => (
                    <option key={style.id} value={style.id}>
                      {style.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span className="mb-1 block text-xs font-semibold uppercase text-muted">Output folder</span>
                <input className="h-10 w-full rounded-md border border-line px-3" value={outputFolder} onChange={(event) => setOutputFolder(event.target.value)} />
              </label>
              <div className="flex flex-wrap gap-2">
                <button className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand" type="button" disabled={saving} onClick={() => void handleSave(false)}>
                  Save
                </button>
                <button className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand" type="button" disabled={saving} onClick={() => void handleSave(true)}>
                  Mark all reviewed
                </button>
                <button className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand" type="button" disabled={saving} onClick={resetAllEdits}>
                  Reset edits
                </button>
                <button className="rounded-md bg-brand px-3 py-2 text-xs font-semibold text-white disabled:bg-blue-200" type="button" disabled={saving} onClick={() => void handleApprove()}>
                  Approve
                </button>
                <button className="rounded-md bg-brand px-3 py-2 text-xs font-semibold text-white disabled:bg-blue-200" type="button" disabled={saving || document.status !== 'approved'} onClick={() => void handleRenderCurrent()}>
                  Render this video
                </button>
              </div>
              {document.source_type === 'ocr_hardsub' ? (
                <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                  Phụ đề nguồn được nhận diện bằng OCR từ chữ dính trên video. Vui lòng kiểm tra kỹ vì OCR có thể nhận sai chữ.
                </div>
              ) : null}
            </div>
          </div>

          <div className="rounded-md border border-line bg-white p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-semibold text-ink">{fileName(document.video_path)}</h2>
              <Link className="text-sm font-semibold text-brand" to="/subtitle-review">
                Back to list
              </Link>
            </div>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <select
                className="h-9 rounded-md border border-line bg-white px-3 text-xs font-semibold text-ink"
                value={lineFilter}
                onChange={(event) => setLineFilter(event.target.value as QualityLineFilter)}
              >
                <option value="all">All lines</option>
                <option value="needs_review">Needs review</option>
                <option value="critical">Critical only</option>
                <option value="warning">Warnings only</option>
                <option value="edited">Edited</option>
                <option value="unedited">Unedited</option>
              </select>
              <button
                className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand disabled:text-muted"
                type="button"
                disabled={!flaggedLines.length}
                onClick={() => selectFlaggedLine(-1)}
              >
                Previous flagged line
              </button>
              <button
                className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand disabled:text-muted"
                type="button"
                disabled={!flaggedLines.length}
                onClick={() => selectFlaggedLine(1)}
              >
                Next flagged line
              </button>
              <button
                className="rounded-md bg-brand px-3 py-2 text-xs font-semibold text-white disabled:bg-blue-200"
                type="button"
                disabled={!flaggedLines.length || saving}
                onClick={() => setBulkRewriteOpen(true)}
              >
                Suggest rewrites for flagged lines
              </button>
            </div>
            <div className="max-h-[760px] overflow-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="sticky top-0 border-b border-line bg-white text-xs uppercase text-muted">
                  <tr>
                    <th className="py-2 pr-2">Index</th>
                    <th className="py-2 pr-2">Time</th>
                    <th className="py-2 pr-2">Source</th>
                    <th className="py-2 pr-2">Translation / Edit</th>
                    <th className="py-2 pr-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleLines.map((line) => (
                    <tr key={line.index} className={lineRowClass(line, selectedLine?.index === line.index)}>
                      <td className="py-3 pr-2">
                        <button className="rounded-md border border-line bg-white px-2 py-1 text-xs font-semibold" type="button" onClick={() => selectLine(line)}>
                          {line.index}
                        </button>
                      </td>
                      <td className="w-32 py-3 pr-2 text-xs text-muted">{formatMs(line.start_ms)} - {formatMs(line.end_ms)}</td>
                      <td className="max-w-xs py-3 pr-2 text-xs text-muted">{line.source_text || '-'}</td>
                      <td className="min-w-[320px] py-3 pr-2">
                        <div className="mb-2 text-xs text-muted">{line.translated_text}</div>
                        <textarea
                          className="min-h-20 w-full rounded-md border border-line px-3 py-2 text-sm"
                          value={line.edited_text ?? line.translated_text}
                          onChange={(event) => updateLocalLine(line.index, { edited_text: event.target.value, status: 'reviewed' })}
                        />
                        <div className="mt-2 flex flex-wrap gap-2">
                          <button className="rounded-md border border-line bg-white px-2 py-1 text-xs font-semibold" type="button" onClick={() => updateLocalLine(line.index, { edited_text: line.translated_text, status: 'reviewed' })}>
                            Use auto translation
                          </button>
                          <button className="rounded-md border border-line bg-white px-2 py-1 text-xs font-semibold" type="button" onClick={() => updateLocalLine(line.index, { edited_text: null, status: 'pending' })}>
                            Clear edit
                          </button>
                          {line.quality_needs_review ? (
                            <button
                              className="rounded-md border border-line bg-white px-2 py-1 text-xs font-semibold"
                              type="button"
                              disabled={saving}
                              onClick={() => void handleSuggestRewrite(line.index)}
                            >
                              Suggest rewrite
                            </button>
                          ) : null}
                        </div>
                        {line.warnings.length ? <div className="mt-2 text-xs text-amber-700">{line.warnings.join('; ')}</div> : null}
                        {line.quality_issues.length ? (
                          <div className="mt-2 grid gap-1 rounded-md border border-line bg-surface p-2 text-xs">
                            {line.quality_issues.map((issue, issueIndex) => (
                              <div key={issue.issue_type + issueIndex}>
                                <span className="font-semibold text-ink">{issue.message}</span>
                                {issue.suggestion ? <div className="text-muted">Gợi ý: {issue.suggestion}</div> : null}
                              </div>
                            ))}
                          </div>
                        ) : null}
                        {rewriteSuggestions[line.index]?.length ? (
                          <div className="mt-2 grid gap-2 border-t border-line pt-2 text-xs">
                            <div className="font-semibold text-ink">Rewrite suggestions</div>
                            {rewriteSuggestions[line.index].map((suggestion, suggestionIndex) => (
                              <div className="rounded-md border border-line bg-white p-3" key={suggestion.id}>
                                <div className="font-medium text-ink">
                                  {suggestionIndex + 1}. {suggestion.suggested_text}
                                </div>
                                <div className="mt-1 text-muted">{suggestion.reason || 'Shorter and easier to read.'}</div>
                                <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-muted">
                                  <span>Score: {formatPercent(suggestion.quality_score_after)}</span>
                                  <span>{suggestion.char_count_before} → {suggestion.char_count_after} characters</span>
                                  <span>CPS: {formatDecimal(suggestion.estimated_cps_before)} → {formatDecimal(suggestion.estimated_cps_after)}</span>
                                </div>
                                {suggestion.safety_warnings.length ? (
                                  <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-2 text-amber-800">
                                    {suggestion.safety_warnings.map((warning) => <div key={warning}>{warning}</div>)}
                                  </div>
                                ) : null}
                                <button
                                  className="mt-2 rounded-md bg-brand px-3 py-1.5 font-semibold text-white disabled:bg-blue-200"
                                  type="button"
                                  disabled={saving}
                                  onClick={() => void handleApplyRewrite(line.index, suggestion)}
                                >
                                  Apply
                                </button>
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </td>
                      <td className="py-3 pr-2">
                        <div className={qualityBadgeClass(line.quality_severity)}>
                          {qualityBadgeLabel(line)}
                        </div>
                        <select className="rounded-md border border-line bg-white px-2 py-1 text-xs" value={line.status} onChange={(event) => updateLocalLine(line.index, { status: event.target.value as SubtitleReviewStatus })}>
                          <option value="pending">pending</option>
                          <option value="reviewed">reviewed</option>
                          <option value="needs_fix">needs_fix</option>
                          <option value="approved">approved</option>
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
      {bulkRewriteOpen ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label="Bulk subtitle rewrite">
          <div className="w-full max-w-lg rounded-md bg-white p-5 shadow-xl">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-ink">Suggest rewrites for flagged lines</h2>
              <button className="text-xl leading-none text-muted" type="button" aria-label="Close" onClick={() => setBulkRewriteOpen(false)}>×</button>
            </div>
            <div className="mt-4 grid gap-4 text-sm">
              <label>
                <span className="mb-1 block text-xs font-semibold uppercase text-muted">Style</span>
                <select
                  className="h-10 w-full rounded-md border border-line bg-white px-3"
                  value={bulkRewriteStyle}
                  onChange={(event) => setBulkRewriteStyle(event.target.value as SubtitleRewriteStyle)}
                >
                  <option value="short_natural">Short natural</option>
                  <option value="very_short">Very short</option>
                  <option value="casual_tiktok">Casual TikTok</option>
                  <option value="clear_review">Clear review</option>
                  <option value="sales_natural">Sales natural</option>
                </select>
              </label>
              <fieldset>
                <legend className="mb-2 text-xs font-semibold uppercase text-muted">Apply to</legend>
                <div className="grid gap-2 sm:grid-cols-2">
                  {[
                    ['too_long', 'Too long'],
                    ['reading_speed_too_high', 'Reading speed too high'],
                    ['ocr_low_confidence', 'OCR low confidence'],
                    ['untranslated_chinese', 'Untranslated Chinese'],
                  ].map(([value, label]) => (
                    <label className="flex items-center gap-2" key={value}>
                      <input
                        type="checkbox"
                        checked={bulkRewriteIssueTypes.includes(value)}
                        onChange={() => toggleBulkIssue(value)}
                      />
                      <span>{label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <label>
                <span className="mb-1 block text-xs font-semibold uppercase text-muted">Max lines</span>
                <input
                  className="h-10 w-full rounded-md border border-line px-3"
                  type="number"
                  min={1}
                  max={100}
                  value={bulkRewriteMaxLines}
                  onChange={(event) => setBulkRewriteMaxLines(Math.max(1, Math.min(100, Number(event.target.value) || 1)))}
                />
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={bulkRewriteAutoApply}
                  onChange={(event) => setBulkRewriteAutoApply(event.target.checked)}
                />
                <span>Auto apply only safe high-score suggestions</span>
              </label>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold" type="button" onClick={() => setBulkRewriteOpen(false)}>
                Cancel
              </button>
              <button className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white disabled:bg-blue-200" type="button" disabled={saving} onClick={() => void handleBulkRewrite()}>
                Generate Suggestions
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-surface p-3">
      <div className="text-xs font-semibold uppercase text-muted">{label}</div>
      <div className="mt-1 font-semibold text-ink">{value}</div>
    </div>
  );
}

function fileName(path: string): string {
  return path.split(/[\\/]/).pop() || path;
}

function formatMs(ms: number): string {
  const seconds = ms / 1000;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds - minutes * 60;
  return `${minutes}:${rest.toFixed(2).padStart(5, '0')}`;
}

function formatSourceType(source?: string | null): string {
  const labels: Record<string, string> = {
    sidecar_srt: 'Sidecar SRT',
    embedded_subtitle: 'Embedded subtitle',
    asr: 'ASR',
    ocr_hardsub: 'OCR hard-sub',
  };
  return source ? labels[source] ?? source : '-';
}

function formatPercent(value?: number | null): string {
  return value == null ? '-' : `${Math.round(value * 100)}%`;
}

function formatDecimal(value?: number | null): string {
  return value == null ? '-' : value.toFixed(1);
}

function lineRowClass(line: SubtitleReviewLine, selected: boolean): string {
  const base = 'border-b border-line align-top last:border-b-0';
  if (selected) return base + ' bg-blue-50';
  if (line.quality_severity === 'critical') return base + ' bg-red-50';
  if (line.quality_needs_review) return base + ' bg-amber-50';
  return base;
}

function qualityBadgeLabel(line: SubtitleReviewLine): string {
  if (line.quality_severity === 'critical') return 'Critical';
  if (line.quality_needs_review) return 'Needs review';
  return 'Good';
}

function qualityBadgeClass(severity?: string | null): string {
  if (severity === 'critical') return 'mb-2 text-xs font-semibold text-red-700';
  if (severity === 'warning') return 'mb-2 text-xs font-semibold text-amber-700';
  return 'mb-2 text-xs font-semibold text-green-700';
}
