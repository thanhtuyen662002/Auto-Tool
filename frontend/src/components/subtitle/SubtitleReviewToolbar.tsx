import { Check, ChevronDown, Ellipsis, Save, Video } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { SubtitleReviewDocument } from '../../types/project';
import GlassBadge from '../glass/GlassBadge';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';
import { statusLabel } from './subtitleUi';

interface Props {
  document: SubtitleReviewDocument;
  qualityScore: number;
  needsReview: number;
  critical: number;
  unsavedCount: number;
  saving: boolean;
  onSaveAll: () => void;
  onApprove: () => void;
  onRender: () => void;
  onRefreshQuality: () => void;
  onOpenLog: () => void;
  onOpenShortcuts: () => void;
  onOpenPath: (path?: string | null) => void;
}

export default function SubtitleReviewToolbar(props: Props) {
  const { document, qualityScore, needsReview, critical, unsavedCount, saving } = props;
  const [menuOpen, setMenuOpen] = useState(false);
  function runMenuAction(action: () => void) {
    setMenuOpen(false);
    action();
  }
  return (
    <GlassCard className="relative z-[90] p-4 sm:p-5" strong>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h1 className="truncate text-xl font-semibold text-white sm:text-2xl" title={fileName(document.video_path)}>{fileName(document.video_path)}</h1><GlassBadge variant={document.status === 'approved' ? 'approved' : document.status === 'needs_fix' ? 'warning' : 'needs_review'}>{statusLabel(document.status)}</GlassBadge>{unsavedCount ? <GlassBadge variant="warning">{unsavedCount} chưa lưu</GlassBadge> : null}</div><p className="mt-1 text-sm text-slate-400">Không gian chỉnh sửa phụ đề</p></div>
        <div className="relative z-[80] flex flex-wrap items-center gap-2"><GlassButton variant="secondary" loading={saving} disabled={!unsavedCount} onClick={props.onSaveAll}><Save size={16} /> Lưu tất cả</GlassButton><GlassButton variant="secondary" disabled={saving} onClick={props.onApprove}><Check size={16} /> Duyệt phụ đề</GlassButton><GlassButton variant="primary" disabled={saving || document.status !== 'approved'} title={document.status === 'approved' ? 'Render video' : 'Cần duyệt phụ đề trước khi render'} onClick={props.onRender}><Video size={16} /> Render video</GlassButton><div className="relative"><button className="grid h-10 w-10 place-items-center rounded-md border border-white/15 bg-white/8 text-slate-200 hover:bg-white/12" type="button" aria-label="Tác vụ khác" onClick={() => setMenuOpen((current) => !current)}><Ellipsis size={18} /></button>{menuOpen ? <div className="absolute right-0 z-[100] mt-2 grid w-56 gap-1 rounded-md border border-white/12 bg-[#0b1020] p-2 shadow-2xl"><MenuButton label="Làm mới chất lượng" onClick={() => runMenuAction(props.onRefreshQuality)} /><MenuButton label="Mở file SRT" disabled={!document.corrected_srt_path && !document.translated_srt_path} onClick={() => runMenuAction(() => props.onOpenPath(document.corrected_srt_path || document.translated_srt_path))} /><MenuButton label="Mở file ASS" disabled={!document.corrected_ass_path} onClick={() => runMenuAction(() => props.onOpenPath(document.corrected_ass_path))} /><MenuButton label="Xem log kỹ thuật" onClick={() => runMenuAction(props.onOpenLog)} /><MenuButton label="Phím tắt" onClick={() => runMenuAction(props.onOpenShortcuts)} /><Link className="rounded px-3 py-2 text-sm text-slate-300 hover:bg-white/8 hover:text-white" to="/subtitle-review">Quay lại danh sách</Link></div> : null}</div></div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4"><Metric label="Chất lượng" value={`${qualityScore}%`} accent="text-cyan-200" /><Metric label="Cần kiểm tra" value={String(needsReview)} accent="text-amber-200" /><Metric label="Lỗi nặng" value={String(critical)} accent="text-rose-200" /><Metric label="Đã sửa" value={String(document.edited_count + unsavedCount)} accent="text-emerald-200" /></div>
    </GlassCard>
  );
}

function Metric({ label, value, accent }: { label: string; value: string; accent: string }) { return <div className="rounded-md border border-white/8 bg-black/15 px-3 py-2"><div className={`text-lg font-semibold ${accent}`}>{value}</div><div className="text-xs text-slate-500">{label}</div></div>; }
function MenuButton({ label, onClick, disabled }: { label: string; onClick: () => void; disabled?: boolean }) { return <button className="flex items-center justify-between rounded px-3 py-2 text-left text-sm text-slate-300 hover:bg-white/8 hover:text-white disabled:opacity-40" type="button" disabled={disabled} onClick={onClick}>{label}<ChevronDown className="rotate-[-90deg]" size={14} /></button>; }
function fileName(path: string) { return path.split(/[\\/]/).pop() || path; }
