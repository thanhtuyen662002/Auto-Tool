import { Clipboard, FolderOpen, PackageCheck } from 'lucide-react';
import type { PlatformExportPack } from '../../types/project';
import GlassButton from '../glass/GlassButton';

export default function ExportPackCreatedCard({
  exportPack,
  onCopy,
  onOpen,
}: {
  exportPack: PlatformExportPack;
  onCopy: () => void;
  onOpen: () => void;
}) {
  const items = Array.isArray(exportPack.items) ? exportPack.items : [];
  const existing = items.filter((item) => item.exists).length;
  return (
    <div className="rounded-md border border-emerald-300/25 bg-emerald-300/10 p-4">
      <div className="flex items-start gap-3">
        <PackageCheck className="mt-0.5 shrink-0 text-emerald-300" size={20} />
        <div className="min-w-0">
          <div className="font-semibold text-emerald-100">Gói xuất bản đã tạo</div>
          <div className="mt-1 break-all text-xs leading-5 text-emerald-100/80">{exportPack.output_dir || 'Chưa có output path'}</div>
          <div className="mt-1 text-xs text-emerald-100/75">{existing}/{items.length} file sẵn sàng</div>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <GlassButton className="px-3" variant="secondary" onClick={onCopy}>
          <Clipboard size={15} />
          Copy đường dẫn
        </GlassButton>
        <GlassButton className="px-3" variant="ghost" onClick={onOpen}>
          <FolderOpen size={15} />
          Mở thư mục
        </GlassButton>
      </div>
    </div>
  );
}
