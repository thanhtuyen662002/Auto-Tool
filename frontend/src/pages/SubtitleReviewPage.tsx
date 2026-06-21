import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  approveSubtitleReviewDocument, applySubtitleRewrite, generateSubtitleRewriteSuggestions, getSubtitleQualityReport,
  getSubtitleReviewDocument, getVisualStyles, listSubtitleReviewDocuments, refreshSubtitleQualityReport,
  renderApprovedSubtitleReviewDocuments, renderSubtitleReviewDocument, saveSubtitleReviewDocument,
  updateSubtitleReviewLine, videoFileUrl,
} from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import GlassButton from '../components/glass/GlassButton';
import GlassModal from '../components/glass/GlassModal';
import NotifyOnChange from '../components/notifications/NotifyOnChange';
import SubtitleApproveModal from '../components/subtitle/SubtitleApproveModal';
import SubtitleEditorPanel from '../components/subtitle/SubtitleEditorPanel';
import SubtitleLineList from '../components/subtitle/SubtitleLineList';
import SubtitleQualityPanel from '../components/subtitle/SubtitleQualityPanel';
import SubtitleReviewLayout from '../components/subtitle/SubtitleReviewLayout';
import SubtitleReviewListPage from '../components/subtitle/SubtitleReviewListPage';
import SubtitleReviewSkeleton from '../components/subtitle/SubtitleReviewSkeleton';
import SubtitleReviewToolbar from '../components/subtitle/SubtitleReviewToolbar';
import SubtitleRewritePanel from '../components/subtitle/SubtitleRewritePanel';
import SubtitleShortcutHint from '../components/subtitle/SubtitleShortcutHint';
import SubtitleTechnicalLogDrawer from '../components/subtitle/SubtitleTechnicalLogDrawer';
import SubtitleVideoPanel from '../components/subtitle/SubtitleVideoPanel';
import { DEFAULT_REVIEW_RENDER_SETTINGS } from '../components/subtitle/subtitleReviewDefaults';
import type { SubtitleLineFilter, SubtitleLineSort } from '../components/subtitle/subtitleUi';
import type { SubtitleDocumentQualityReport, SubtitleReviewDocument, SubtitleReviewLine, SubtitleReviewStatus, SubtitleRewriteSuggestion, VisualStylePreset } from '../types/project';

export default function SubtitleReviewPage() {
  const { documentId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [documents, setDocuments] = useState<SubtitleReviewDocument[]>([]);
  const [document, setDocument] = useState<SubtitleReviewDocument | null>(null);
  const [quality, setQuality] = useState<SubtitleDocumentQualityReport | null>(null);
  const [visualStyles, setVisualStyles] = useState<VisualStylePreset[]>([]);
  const [visualStyleId, setVisualStyleId] = useState('clean_review_light');
  const [outputFolder, setOutputFolder] = useState(() => localStorage.getItem('auto-tool.default-output-folder') || './examples/outputs');
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<'all' | SubtitleReviewStatus>('all');
  const [lineFilter, setLineFilter] = useState<SubtitleLineFilter>('all');
  const [lineSort, setLineSort] = useState<SubtitleLineSort>('timeline');
  const [search, setSearch] = useState('');
  const [unsaved, setUnsaved] = useState<Set<number>>(new Set());
  const [rewriteLineIndex, setRewriteLineIndex] = useState<number | null>(null);
  const [rewriteSuggestions, setRewriteSuggestions] = useState<Record<number, SubtitleRewriteSuggestion[]>>({});
  const [approveOpen, setApproveOpen] = useState(false);
  const [logOpen, setLogOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const jobId = searchParams.get('job_id');

  const activeLine = useMemo(() => document?.lines.find((line) => line.index === selectedIndex) ?? document?.lines[0] ?? null, [document, selectedIndex]);
  const flaggedLines = useMemo(() => document?.lines.filter((line) => line.quality_needs_review) ?? [], [document]);
  const visibleDocuments = useMemo(() => documents.filter((item) => statusFilter === 'all' || item.status === statusFilter), [documents, statusFilter]);
  const visibleLines = useMemo(() => {
    if (!document) return [];
    const query = search.trim().toLowerCase();
    const source = (document.source_type || '').toLowerCase();
    const filtered = document.lines.filter((line) => {
      const text = `${line.source_text || ''} ${line.translated_text} ${line.edited_text || ''}`.toLowerCase();
      if (query && !text.includes(query)) return false;
      if (lineFilter === 'needs_review' && !line.quality_needs_review) return false;
      if (lineFilter === 'critical' && line.quality_severity !== 'critical') return false;
      if (lineFilter === 'edited' && line.edited_text == null) return false;
      if (lineFilter === 'unedited' && line.edited_text != null) return false;
      if (lineFilter === 'ocr' && !source.includes('ocr')) return false;
      if (lineFilter === 'asr' && !source.includes('asr')) return false;
      if (lineFilter === 'visual' && !source.includes('visual') && !source.includes('template')) return false;
      return true;
    });
    return [...filtered].sort((a, b) => lineSort === 'quality' ? (a.quality_score ?? 1) - (b.quality_score ?? 1) : lineSort === 'edited' ? Number(b.edited_text != null) - Number(a.edited_text != null) : lineSort === 'critical' ? Number(b.quality_severity === 'critical') - Number(a.quality_severity === 'critical') : a.start_ms - b.start_ms);
  }, [document, lineFilter, lineSort, search]);
  const rewriteLine = useMemo(() => document?.lines.find((line) => line.index === rewriteLineIndex) ?? null, [document, rewriteLineIndex]);

  const loadList = useCallback(async () => {
    const response = await listSubtitleReviewDocuments({ job_id: jobId, status: statusFilter === 'all' ? null : statusFilter });
    setDocuments(response.items);
  }, [jobId, statusFilter]);
  const loadDocument = useCallback(async () => {
    if (!documentId) return;
    const [next, report] = await Promise.all([getSubtitleReviewDocument(documentId), getSubtitleQualityReport(documentId)]);
    setDocument(next); setQuality(report); setSelectedIndex((current) => current ?? next.lines[0]?.index ?? null); setUnsaved(new Set());
  }, [documentId]);

  useEffect(() => { getVisualStyles().then((response) => setVisualStyles(response.presets)).catch(() => setVisualStyles([])); }, []);
  useEffect(() => { let active = true; setLoading(true); setError(null); const task = documentId ? loadDocument() : loadList(); task.catch((err) => active && setError(messageFromError(err, 'Không thể tải phụ đề.'))).finally(() => active && setLoading(false)); return () => { active = false; }; }, [documentId, loadDocument, loadList]);
  useEffect(() => { if (!toast) return; const timeout = window.setTimeout(() => setToast(null), 2600); return () => window.clearTimeout(timeout); }, [toast]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (!document) return;
      const target = event.target as HTMLElement | null;
      const typing = target?.tagName === 'TEXTAREA' || target?.tagName === 'INPUT' || target?.tagName === 'SELECT' || target?.isContentEditable;
      if (event.key === 'Escape') { setApproveOpen(false); setLogOpen(false); setShortcutsOpen(false); setSettingsOpen(false); setRewriteLineIndex(null); }
      if (event.ctrlKey && event.key.toLowerCase() === 's') { event.preventDefault(); void saveAll(); }
      if (event.altKey && event.key === 'ArrowDown') { event.preventDefault(); selectRelative(1); }
      if (event.altKey && event.key === 'ArrowUp') { event.preventDefault(); selectRelative(-1); }
      if (event.altKey && event.key.toLowerCase() === 'n') { event.preventDefault(); selectFlagged(1); }
      if (event.altKey && event.key.toLowerCase() === 'r' && activeLine) { event.preventDefault(); void suggestRewrite(activeLine.index); }
      if (!typing && event.code === 'Space') { event.preventDefault(); const video = videoRef.current; if (video) video.paused ? void video.play() : video.pause(); }
    }
    window.addEventListener('keydown', onKeyDown); return () => window.removeEventListener('keydown', onKeyDown);
  });

  function selectLine(line: SubtitleReviewLine) { setSelectedIndex(line.index); if (videoRef.current) videoRef.current.currentTime = Math.max(0, line.start_ms / 1000); window.requestAnimationFrame(() => documentQueryLine(line.index)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })); }
  function selectRelative(offset: number) { if (!document || !activeLine) return; const index = document.lines.findIndex((line) => line.index === activeLine.index); const next = document.lines[Math.max(0, Math.min(document.lines.length - 1, index + offset))]; if (next) selectLine(next); }
  function selectFlagged(offset: number) { if (!flaggedLines.length) return; const current = flaggedLines.findIndex((line) => line.index === activeLine?.index); const next = flaggedLines[current < 0 ? 0 : (current + offset + flaggedLines.length) % flaggedLines.length]; selectLine(next); }
  function patchLine(index: number, patch: Partial<SubtitleReviewLine>, markUnsaved = true) { setDocument((current) => current ? { ...current, lines: current.lines.map((line) => line.index === index ? { ...line, ...patch } : line) } : current); if (markUnsaved) setUnsaved((current) => new Set(current).add(index)); }
  function changeLine(index: number, text: string) { patchLine(index, { edited_text: text, status: 'reviewed' }); }

  async function saveLine(index: number) {
    if (!document) return; const line = document.lines.find((item) => item.index === index); if (!line || !(line.edited_text ?? line.translated_text).trim()) return;
    setSaving(true); setError(null);
    try { const updated = await updateSubtitleReviewLine(document.id, index, { edited_text: line.edited_text ?? line.translated_text, status: line.status, user_note: line.user_note ?? null }); patchLine(index, updated, false); setUnsaved((current) => { const next = new Set(current); next.delete(index); return next; }); setToast('Đã lưu dòng phụ đề'); }
    catch (err) { setError(messageFromError(err, 'Không lưu được dòng này. Nội dung bạn nhập vẫn được giữ lại.')); }
    finally { setSaving(false); }
  }
  async function saveAll(markReviewed = false) {
    if (!document) return; setSaving(true); setError(null);
    try { const saved = await saveSubtitleReviewDocument(document.id, { lines: document.lines, mark_as_reviewed: markReviewed }); setDocument(saved); setQuality(await getSubtitleQualityReport(document.id)); setUnsaved(new Set()); setToast('Đã lưu tất cả thay đổi'); await loadList(); }
    catch (err) { setError(messageFromError(err, 'Không thể lưu phụ đề. Nội dung bạn nhập vẫn được giữ lại.')); }
    finally { setSaving(false); }
  }
  async function refreshQuality() { if (!document) return; setSaving(true); try { setQuality(await refreshSubtitleQualityReport(document.id)); setDocument(await getSubtitleReviewDocument(document.id)); setToast('Đã làm mới chất lượng'); } catch (err) { setError(messageFromError(err, 'Không thể làm mới chất lượng.')); } finally { setSaving(false); } }
  async function suggestRewrite(index: number) { if (!document) return; setRewriteLineIndex(index); setSaving(true); setError(null); try { const response = await generateSubtitleRewriteSuggestions(document.id, index, { style: 'short_natural', suggestion_count: 3, max_chars: null, preserve_keywords: [], use_ai: true }); setRewriteSuggestions((current) => ({ ...current, [index]: response.items })); } catch (err) { setError(messageFromError(err, 'Không thể tạo gợi ý rút gọn.')); } finally { setSaving(false); } }
  async function applyRewrite(suggestion: SubtitleRewriteSuggestion) { if (!document || rewriteLineIndex == null) return; if (suggestion.safety_warnings.some((item) => item.startsWith('critical:')) && !window.confirm('Gợi ý này có cảnh báo nghiêm trọng. Bạn vẫn muốn áp dụng?')) return; setSaving(true); try { const response = await applySubtitleRewrite(document.id, rewriteLineIndex, suggestion.id); patchLine(rewriteLineIndex, response.line, false); setUnsaved((current) => { const next = new Set(current); next.delete(rewriteLineIndex); return next; }); setRewriteLineIndex(null); setToast('Đã áp dụng gợi ý rút gọn'); setQuality(await getSubtitleQualityReport(document.id)); } catch (err) { setError(messageFromError(err, 'Không thể áp dụng gợi ý.')); } finally { setSaving(false); } }
  async function approve() { if (!document) return; setSaving(true); setError(null); try { const approved = await approveSubtitleReviewDocument(document.id, { generate_ass: true, visual_style_preset_id: visualStyleId }); setDocument(approved); setQuality(await getSubtitleQualityReport(document.id)); setApproveOpen(false); setUnsaved(new Set()); setToast('Đã duyệt phụ đề'); await loadList(); } catch (err) { setError(messageFromError(err, 'Không thể duyệt phụ đề.')); } finally { setSaving(false); } }
  async function renderCurrent() { if (!document) return; setSaving(true); setError(null); try { const response = await renderSubtitleReviewDocument(document.id, { output_folder: outputFolder, settings: { ...DEFAULT_REVIEW_RENDER_SETTINGS, visual_style_preset_id: visualStyleId } }); setToast('Đang render video'); navigate(`/queue/${document.project_id ?? 'subtitle-review'}/${response.job_id}`); } catch (err) { setError(messageFromError(err, 'Không thể đưa video vào hàng đợi render.')); } finally { setSaving(false); } }
  async function renderApproved() { setSaving(true); setError(null); try { const response = await renderApprovedSubtitleReviewDocuments({ job_id: jobId, output_folder: outputFolder, settings: { ...DEFAULT_REVIEW_RENDER_SETTINGS, visual_style_preset_id: visualStyleId } }); navigate(`/queue/subtitle-review/${response.job_id}`); } catch (err) { setError(messageFromError(err, 'Không thể render các bản đã duyệt.')); } finally { setSaving(false); } }

  if (loading) return <main className="studio-page"><SubtitleReviewSkeleton editor={Boolean(documentId)} /></main>;
  return <main className="studio-page grid gap-5">
    <ApiErrorBox error={error} />
    <NotifyOnChange value={toast} variant="success" />
    {!document ? <><div><h1 className="text-2xl font-semibold text-white">Sửa phụ đề</h1><p className="mt-1 text-sm text-slate-400">Chọn tài liệu để sửa, duyệt và render phụ đề.</p></div><SubtitleReviewListPage documents={visibleDocuments} status={statusFilter} saving={saving} onStatus={setStatusFilter} onRenderApproved={() => void renderApproved()} /></> : <SubtitleReviewLayout
      toolbar={<SubtitleReviewToolbar document={document} qualityScore={Math.round((quality?.average_score ?? document.quality_average_score ?? 0) * 100)} needsReview={quality?.needs_review_count ?? document.quality_needs_review_count} critical={quality?.critical_count ?? document.quality_critical_count} unsavedCount={unsaved.size} saving={saving} onSaveAll={() => void saveAll()} onApprove={() => setApproveOpen(true)} onRender={() => void renderCurrent()} onRefreshQuality={() => void refreshQuality()} onOpenLog={() => setLogOpen(true)} onOpenShortcuts={() => setShortcutsOpen(true)} onOpenPath={openLocalPath} />}
      video={<div className="grid gap-4"><SubtitleVideoPanel videoRef={videoRef} videoUrl={videoFileUrl(document.video_path)} activeLine={activeLine} onPrevious={() => selectRelative(-1)} onNext={() => selectRelative(1)} onNextFlagged={() => selectFlagged(1)} hasFlagged={Boolean(flaggedLines.length)} /><SubtitleQualityPanel report={quality} busy={saving} onNextFlagged={() => selectFlagged(1)} onCriticalOnly={() => setLineFilter('critical')} onRefresh={() => void refreshQuality()} /><button className="text-left text-xs font-semibold text-slate-500 hover:text-cyan-200" type="button" onClick={() => setSettingsOpen(true)}>Visual style và output folder</button></div>}
      editor={<SubtitleEditorPanel title="Dòng phụ đề" count={visibleLines.length}><SubtitleLineList lines={visibleLines} activeIndex={activeLine?.index ?? null} unsaved={unsaved} sourceType={document.source_type} busy={saving} search={search} filter={lineFilter} sort={lineSort} onSearch={setSearch} onFilter={setLineFilter} onSort={setLineSort} onSelect={selectLine} onChange={changeLine} onStatusChange={(index, status) => patchLine(index, { status })} onSave={(index) => void saveLine(index)} onSuggestRewrite={(index) => void suggestRewrite(index)} onUseTranslated={(index) => { const line = document.lines.find((item) => item.index === index); if (line) patchLine(index, { edited_text: line.translated_text, status: 'reviewed' }); }} /></SubtitleEditorPanel>}
      bottom={<SubtitleRewritePanel line={rewriteLine} suggestions={rewriteLineIndex == null ? [] : rewriteSuggestions[rewriteLineIndex] ?? []} loading={saving && rewriteLineIndex != null && !rewriteSuggestions[rewriteLineIndex]?.length} onApply={(suggestion) => void applyRewrite(suggestion)} onClose={() => setRewriteLineIndex(null)} />}
    />}
    {document ? <><SubtitleApproveModal open={approveOpen} critical={quality?.critical_count ?? document.quality_critical_count} needsReview={quality?.needs_review_count ?? document.quality_needs_review_count} saving={saving} onClose={() => setApproveOpen(false)} onReview={(filter) => { setLineFilter(filter); setApproveOpen(false); }} onApprove={() => void approve()} /><SubtitleTechnicalLogDrawer open={logOpen} document={document} quality={quality} error={error} onClose={() => setLogOpen(false)} /><SubtitleShortcutHint open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} /><GlassModal open={settingsOpen} title="Visual style và output" onClose={() => setSettingsOpen(false)}><div className="grid gap-4"><label><span className="mb-1.5 block text-sm font-medium text-slate-200">Visual style</span><select className="h-10 w-full rounded-md border border-white/15 bg-slate-950/90 px-3 text-sm" value={visualStyleId} onChange={(event) => setVisualStyleId(event.target.value)}>{visualStyles.map((style) => <option key={style.id} value={style.id}>{style.name}</option>)}</select></label><label><span className="mb-1.5 block text-sm font-medium text-slate-200">Output folder</span><input className="h-10 w-full rounded-md border border-white/15 bg-slate-950/90 px-3 text-sm" value={outputFolder} onChange={(event) => setOutputFolder(event.target.value)} /></label><div className="flex justify-end"><GlassButton variant="primary" onClick={() => setSettingsOpen(false)}>Xong</GlassButton></div></div></GlassModal></> : null}
    {toast ? <div className="fixed bottom-5 right-5 z-[60] rounded-md border border-emerald-300/25 bg-emerald-950/95 px-4 py-3 text-sm font-semibold text-emerald-100 shadow-2xl">{toast}</div> : null}
  </main>;
}

function messageFromError(error: unknown, fallback: string) { const message = error instanceof Error ? error.message : fallback; const first = message.split(/\r?\n/).find(Boolean)?.trim() || fallback; return first.length > 260 ? `${first.slice(0, 257)}...` : first; }
function documentQueryLine(index: number) { return globalThis.document.querySelector(`[data-line-index="${index}"]`); }
function openLocalPath(path?: string | null) { if (!path) return; window.open(`file:///${encodeURI(path.replace(/\\/g, '/'))}`, '_blank'); }
