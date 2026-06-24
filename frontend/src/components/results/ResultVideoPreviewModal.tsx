import { Captions, CheckSquare, Clipboard, FolderOpen, Square } from 'lucide-react';
import { videoFileUrl } from '../../api/client';
import { captionBundle, type NormalizedResultItem } from '../../utils/resultStatus';
import GlassButton from '../glass/GlassButton';
import GlassModal from '../glass/GlassModal';
import ResultStatusBadges from './ResultStatusBadges';

export default function ResultVideoPreviewModal({
  item,
  selected,
  selectionMode,
  selectionLabel = 'Chọn xuất',
  canSelectItem = (result) => result.exportEligible,
  onClose,
  onToggleSelected,
  onCopyPath,
  onRevealFile,
  onCopyCaption,
  onShowLog,
}: {
  item: NormalizedResultItem | null;
  selected: boolean;
  selectionMode: boolean;
  selectionLabel?: string;
  canSelectItem?: (item: NormalizedResultItem) => boolean;
  onClose: () => void;
  onToggleSelected: (item: NormalizedResultItem) => void;
  onCopyPath: (item: NormalizedResultItem) => void;
  onRevealFile: (item: NormalizedResultItem) => void;
  onCopyCaption: (item: NormalizedResultItem) => void;
  onShowLog: (item: NormalizedResultItem) => void;
}) {
  const hasCaption = Boolean(item && captionBundle(item));
  return (
    <GlassModal open={Boolean(item)} title={item?.filename ?? 'Xem trước'} onClose={onClose}>
      {item ? (
        <div className="grid gap-4">
          <div className="overflow-hidden rounded-md border border-white/10 bg-black">
            {item.path ? (
              <video className="max-h-[68vh] w-full bg-black object-contain" controls preload="metadata" src={videoFileUrl(item.path)} />
            ) : (
              <div className="grid aspect-video place-items-center text-slate-500">Không có video preview</div>
            )}
          </div>

          <div className="grid gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <ResultStatusBadges item={item} />
              <div className="text-sm font-semibold text-cyan-100">{item.qaScorePercent == null ? 'Chưa kiểm tra' : `${item.qaScorePercent}% điểm kiểm tra`}</div>
            </div>
            <div className="grid gap-2 text-sm text-slate-300 sm:grid-cols-2">
              <PathLine label="Video" value={item.path} />
              <PathLine label="Phụ đề" value={item.subtitleFile} />
              <PathLine label="Giọng đọc" value={item.voiceFile} />
              <PathLine label="Nhật ký xử lý" value={item.logFile} />
            </div>
            {item.caption ? <p className="rounded-md border border-white/10 bg-white/5 p-3 text-sm leading-6 text-slate-200">{item.caption}</p> : null}
          </div>

          <div className="flex flex-wrap gap-2">
            {selectionMode ? (
              <GlassButton variant={selected ? 'primary' : 'secondary'} disabled={!canSelectItem(item)} onClick={() => onToggleSelected(item)}>
                {selected ? <CheckSquare size={16} /> : <Square size={16} />}
                {selected ? `Đã ${selectionLabel.toLowerCase()}` : selectionLabel}
              </GlassButton>
            ) : null}
            <GlassButton variant="secondary" disabled={!item.path} onClick={() => onCopyPath(item)}>
              <Clipboard size={16} />
              Copy đường dẫn
            </GlassButton>
            <GlassButton variant="secondary" disabled={!item.path} onClick={() => onRevealFile(item)}>
              <FolderOpen size={16} />
              Mở vị trí
            </GlassButton>
            <GlassButton variant="ghost" disabled={!hasCaption} onClick={() => onCopyCaption(item)}>
              <Captions size={16} />
              Copy lời bình
            </GlassButton>
            <GlassButton variant="ghost" onClick={() => onShowLog(item)}>
              <FolderOpen size={16} />
              Nhật ký xử lý
            </GlassButton>
          </div>
        </div>
      ) : null}
    </GlassModal>
  );
}

function PathLine({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="min-w-0 rounded-md border border-white/10 bg-white/5 px-3 py-2">
      <div className="text-xs font-semibold uppercase tracking-normal text-slate-500">{label}</div>
      <div className="mt-1 truncate text-xs text-slate-200" title={value}>{value}</div>
    </div>
  );
}
