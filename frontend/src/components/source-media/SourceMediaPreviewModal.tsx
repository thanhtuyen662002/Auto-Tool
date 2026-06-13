import type { SourceBrowserMediaItem } from '../../types/project';
import { videoFileUrl } from '../../api/client';
import GlassModal from '../glass/GlassModal';

export default function SourceMediaPreviewModal({
  item,
  onClose,
}: {
  item: SourceBrowserMediaItem | null;
  onClose: () => void;
}) {
  return (
    <GlassModal open={Boolean(item)} title={item?.filename || 'Preview'} onClose={onClose}>
      {item ? (
        <div className="grid gap-3">
          <video className="max-h-[70vh] w-full rounded-md bg-black" src={videoFileUrl(item.path)} controls />
          <div className="rounded-md border border-white/10 bg-white/5 p-3 text-xs leading-5 text-slate-300">
            <div>{item.path}</div>
            <div>{item.width || 0}x{item.height || 0} · {Math.round(item.duration_seconds || 0)}s · {item.has_audio ? 'Có audio' : 'Không audio'}</div>
          </div>
        </div>
      ) : null}
    </GlassModal>
  );
}
