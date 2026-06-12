import { Check, RotateCcw, Save, Sparkles } from 'lucide-react';
import { memo, useLayoutEffect, useRef } from 'react';
import type { SubtitleReviewLine, SubtitleReviewStatus } from '../../types/project';
import GlassBadge from '../glass/GlassBadge';
import GlassButton from '../glass/GlassButton';
import { formatSubtitleTime, hasChinese, lineText, qualityLabel, sourceLabel } from './subtitleUi';

interface Props {
  line: SubtitleReviewLine;
  active: boolean;
  unsaved: boolean;
  sourceType?: string | null;
  busy: boolean;
  onSelect: (line: SubtitleReviewLine) => void;
  onChange: (lineIndex: number, text: string) => void;
  onStatusChange: (lineIndex: number, status: SubtitleReviewStatus) => void;
  onSave: (lineIndex: number) => void;
  onSuggestRewrite: (lineIndex: number) => void;
  onUseTranslated: (lineIndex: number) => void;
}

function SubtitleLineCard({ line, active, unsaved, sourceType, busy, onSelect, onChange, onStatusChange, onSave, onSuggestRewrite, onUseTranslated }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const value = lineText(line);
  useLayoutEffect(() => { const area = textareaRef.current; if (!area) return; area.style.height = '0px'; area.style.height = `${Math.min(220, Math.max(84, area.scrollHeight))}px`; }, [value]);
  const validation = validate(value);
  return <article data-line-index={line.index} className={`subtitle-line-card rounded-md border p-4 transition ${active ? 'border-cyan-300/45 bg-cyan-300/10 shadow-[0_0_28px_rgba(34,211,238,0.08)]' : line.quality_severity === 'critical' ? 'border-rose-300/30 bg-rose-400/8' : line.quality_needs_review ? 'border-amber-300/25 bg-amber-400/7' : 'border-white/10 bg-black/12'}`} onClick={() => onSelect(line)}>
    <div className="flex flex-wrap items-center gap-2"><button className="rounded-md border border-white/12 bg-white/6 px-2.5 py-1 text-xs font-semibold text-white hover:border-cyan-300/40" type="button" onClick={(event) => { event.stopPropagation(); onSelect(line); }}>#{line.index}</button><span className="text-xs font-medium text-slate-400">{formatSubtitleTime(line.start_ms)} → {formatSubtitleTime(line.end_ms)}</span><GlassBadge variant="neutral">{sourceLabel(sourceType)}</GlassBadge><div className="ml-auto flex flex-wrap gap-1.5"><GlassBadge variant={line.quality_severity === 'critical' ? 'failed' : line.quality_needs_review ? 'warning' : 'success'}>{qualityLabel(line)}</GlassBadge>{line.edited_text != null ? <GlassBadge variant="approved">Đã sửa</GlassBadge> : null}{unsaved ? <GlassBadge variant="warning">Chưa lưu</GlassBadge> : null}</div></div>
    <details className="mt-3" open={active && Boolean(line.source_text)}><summary className="cursor-pointer text-xs font-semibold text-slate-500">Xem nguồn và bản dịch</summary><div className="mt-2 grid gap-2 text-sm"><TextBlock label="Gốc" value={line.source_text || 'Nguồn: tạo từ cảnh quay'} /><TextBlock label="Bản dịch" value={line.translated_text} /></div></details>
    <label className="mt-3 block"><span className="mb-1.5 block text-xs font-semibold uppercase text-slate-500">Bản đang dùng</span><textarea ref={textareaRef} className="glass-editor w-full resize-none overflow-hidden rounded-md border px-3 py-2.5 text-[15px] leading-6 text-white" value={value} onFocus={() => onSelect(line)} onClick={(event) => event.stopPropagation()} onChange={(event) => onChange(line.index, event.target.value)} /></label>
    {validation.length ? <div className="mt-2 grid gap-1 text-xs text-amber-200">{validation.map((item) => <div key={item}>{item}</div>)}</div> : null}
    {line.quality_issues.length || line.warnings.length ? <div className="mt-3 rounded-md border border-white/8 bg-black/15 p-3 text-xs leading-5"><div className="font-semibold text-slate-300">Điểm cần chú ý</div>{line.quality_issues.map((issue, index) => <div className="mt-1 text-amber-100/85" key={`${issue.issue_type}-${index}`}>{issue.message}{issue.suggestion ? ` · ${issue.suggestion}` : ''}</div>)}{line.warnings.map((warning) => <div className="mt-1 text-amber-100/85" key={warning}>{warning}</div>)}</div> : null}
    <div className="mt-3 flex flex-wrap items-center gap-2"><GlassButton className="min-h-8 px-3 py-1.5 text-xs" variant="primary" disabled={!unsaved || !value.trim()} loading={busy && unsaved} onClick={(event) => { event.stopPropagation(); onSave(line.index); }}><Save size={14} /> Lưu dòng</GlassButton><GlassButton className="min-h-8 px-3 py-1.5 text-xs" variant="secondary" disabled={busy} onClick={(event) => { event.stopPropagation(); onSuggestRewrite(line.index); }}><Sparkles size={14} /> Gợi ý rút gọn</GlassButton><GlassButton className="min-h-8 px-3 py-1.5 text-xs" variant="ghost" onClick={(event) => { event.stopPropagation(); onUseTranslated(line.index); }}><RotateCcw size={14} /> Dùng bản dịch</GlassButton><label className="ml-auto"><span className="sr-only">Trạng thái dòng</span><select className="h-8 rounded-md border border-white/12 bg-slate-950/85 px-2 text-xs" value={line.status} onClick={(event) => event.stopPropagation()} onChange={(event) => onStatusChange(line.index, event.target.value as SubtitleReviewStatus)}><option value="pending">Chờ kiểm tra</option><option value="reviewed">Đã kiểm tra</option><option value="needs_fix">Cần sửa</option><option value="approved">Đã duyệt</option></select></label>{line.status === 'reviewed' ? <Check className="text-emerald-300" size={16} /> : null}</div>
  </article>;
}

function TextBlock({ label, value }: { label: string; value: string }) { return <div className="rounded-md bg-black/15 p-3"><div className="text-[11px] font-semibold uppercase text-slate-500">{label}</div><div className="mt-1 leading-6 text-slate-300">{value}</div></div>; }
function validate(value: string) { const messages: string[] = []; if (!value.trim()) messages.push('Dòng phụ đề đang trống.'); if (value.length > 56) messages.push('Dòng này hơi dài, người xem có thể đọc không kịp.'); if (value.split(/\r?\n/).length > 3) messages.push('Nên giữ phụ đề trong tối đa 3 dòng.'); if (hasChinese(value)) messages.push('Bản đang dùng vẫn còn ký tự tiếng Trung.'); return messages; }
export default memo(SubtitleLineCard);
