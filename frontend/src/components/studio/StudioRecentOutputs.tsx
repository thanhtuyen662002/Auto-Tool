import { Copy, FolderOpen, Play } from 'lucide-react';
import { Link } from 'react-router-dom';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';
import GlassEmptyState from '../glass/GlassEmptyState';

type RecentOutput = {
  id: string;
  filename: string;
  qaStatus: string;
  outputFolder: string;
  resultUrl?: string;
};

export default function StudioRecentOutputs() {
  const outputs = readRecentOutputs();

  return (
    <GlassCard strong className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold text-white">Video đầu ra gần đây</h2>
          <p className="mt-1 text-sm text-slate-400">Video render xong sẽ nằm trong Kết quả, kèm kiểm tra cuối và gói xuất bản.</p>
        </div>
        <Link to="/results">
          <GlassButton variant="secondary" className="min-h-9 px-3 text-xs">Mở Kết quả</GlassButton>
        </Link>
      </div>

      {outputs.length ? (
        <div className="mt-4 grid gap-2">
          {outputs.map((output) => (
            <div className="rounded-md border border-white/10 bg-black/15 p-3" key={output.id}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-white">{output.filename}</div>
                  <div className="mt-1 text-xs text-slate-500">{output.qaStatus} · {output.outputFolder}</div>
                </div>
                <div className="flex gap-2">
                  {output.resultUrl ? (
                    <Link to={output.resultUrl} className="inline-flex min-h-9 items-center gap-2 rounded-md border border-white/15 px-3 text-xs font-semibold text-slate-200 hover:bg-white/8">
                      <Play size={13} />
                      Xem trước
                    </Link>
                  ) : null}
                  <button className="inline-flex min-h-9 items-center gap-2 rounded-md border border-white/15 px-3 text-xs font-semibold text-slate-200 hover:bg-white/8" type="button" onClick={() => void navigator.clipboard?.writeText(output.outputFolder)}>
                    <Copy size={13} />
                    Sao chép đường dẫn
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4">
          <GlassEmptyState
            title="Chưa có video đầu ra gần đây"
            message="Sau khi chạy lô, mở Kết quả để xem video, trạng thái kiểm tra, gói xuất bản và nhật ký kỹ thuật khi cần."
            action={
              <Link to="/results">
                <GlassButton variant="secondary">
                  <FolderOpen size={15} />
                  Xem kết quả gần đây
                </GlassButton>
              </Link>
            }
          />
        </div>
      )}
    </GlassCard>
  );
}

function readRecentOutputs(): RecentOutput[] {
  try {
    const parsed = JSON.parse(localStorage.getItem('auto-tool.recentOutputs') || '[]') as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item): item is RecentOutput => Boolean(item) && typeof item === 'object' && 'id' in item && 'filename' in item)
      .slice(0, 5);
  } catch {
    return [];
  }
}
