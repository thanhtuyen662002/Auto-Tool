import { FileArchive, PackagePlus } from 'lucide-react';
import type { PlatformExportPack, PlatformTarget } from '../../types/project';
import type { NormalizedResultItem } from '../../utils/resultStatus';
import GlassBadge from '../glass/GlassBadge';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';
import ExportPackCreatedCard from './ExportPackCreatedCard';

export type ExportScope = 'selected' | 'all_rendered' | 'qa_passed' | 'include_warnings';

export interface ExportPackOptions {
  copy_videos: boolean;
  include_subtitles: boolean;
  include_logs: boolean;
  include_captions: boolean;
  include_posting_checklist: boolean;
}

const optionRows: Array<[keyof ExportPackOptions, string]> = [
  ['copy_videos', 'Video files'],
  ['include_subtitles', 'Subtitle files'],
  ['include_logs', 'Logs'],
  ['include_captions', 'Captions'],
  ['include_posting_checklist', 'Posting checklist'],
];

const scopes: Array<{ value: ExportScope; label: string; hint: string }> = [
  { value: 'selected', label: 'Đang chọn', hint: 'Chỉ các card đã tick' },
  { value: 'all_rendered', label: 'Tất cả sẵn sàng', hint: 'Bỏ qua output lỗi' },
  { value: 'qa_passed', label: 'QA ổn', hint: 'Chỉ video đã qua Final QA' },
  { value: 'include_warnings', label: 'Kèm cảnh báo', hint: 'Sẵn sàng + cảnh báo, không lấy lỗi' },
];

export default function ExportPackPanel({
  items,
  selectedCount,
  outputIndexes,
  exportScope,
  onExportScopeChange,
  platformTarget,
  onPlatformTargetChange,
  options,
  onOptionsChange,
  busy,
  exportPack,
  onCreatePack,
  onCopyPack,
  onOpenPack,
}: {
  items: NormalizedResultItem[];
  selectedCount: number;
  outputIndexes: number[];
  exportScope: ExportScope;
  onExportScopeChange: (value: ExportScope) => void;
  platformTarget: PlatformTarget;
  onPlatformTargetChange: (value: PlatformTarget) => void;
  options: ExportPackOptions;
  onOptionsChange: (options: ExportPackOptions) => void;
  busy: boolean;
  exportPack: PlatformExportPack | null;
  onCreatePack: () => void;
  onCopyPack: () => void;
  onOpenPack: () => void;
}) {
  return (
    <GlassCard className="grid gap-4 p-5" strong>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 font-semibold text-white">
            <FileArchive size={18} className="text-cyan-200" />
            Gói xuất bản
          </h2>
          <p className="mt-1 text-sm text-slate-400">Đóng gói video, subtitle, caption và checklist đăng bài.</p>
        </div>
        <GlassBadge variant={outputIndexes.length ? 'ready' : 'neutral'}>{outputIndexes.length} output</GlassBadge>
      </div>

      <div className="grid gap-3">
        <label>
          <span className="mb-1 block text-xs font-semibold uppercase tracking-normal text-slate-500">Platform</span>
          <select
            className="h-10 w-full rounded-md border border-white/15 bg-slate-950/70 px-3 text-sm"
            value={platformTarget}
            onChange={(event) => onPlatformTargetChange(event.target.value as PlatformTarget)}
          >
            <option value="tiktok">TikTok</option>
            <option value="instagram_reels">Instagram Reels</option>
            <option value="youtube_shorts">YouTube Shorts</option>
            <option value="generic_vertical">Generic Vertical</option>
          </select>
        </label>

        <div className="grid gap-2">
          {scopes.map((scope) => (
            <label className="flex items-start gap-3 rounded-md border border-white/10 bg-white/5 p-3 text-sm" key={scope.value}>
              <input
                className="mt-1"
                type="radio"
                checked={exportScope === scope.value}
                onChange={() => onExportScopeChange(scope.value)}
              />
              <span>
                <span className="block font-semibold text-white">{scope.label}</span>
                <span className="text-xs text-slate-400">{scope.hint}</span>
              </span>
            </label>
          ))}
        </div>
        {exportScope === 'selected' ? <div className="text-xs text-slate-400">{selectedCount} card đang được chọn trong {items.length} output.</div> : null}
      </div>

      <div className="grid gap-2">
        {optionRows.map(([key, label]) => (
          <label className="flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" key={key}>
            <input
              type="checkbox"
              checked={options[key]}
              onChange={(event) => onOptionsChange({ ...options, [key]: event.target.checked })}
            />
            <span>{label}</span>
          </label>
        ))}
      </div>

      <GlassButton variant="primary" loading={busy} disabled={!outputIndexes.length} onClick={onCreatePack}>
        <PackagePlus size={16} />
        Tạo gói xuất bản
      </GlassButton>

      {exportPack ? <ExportPackCreatedCard exportPack={exportPack} onCopy={onCopyPack} onOpen={onOpenPack} /> : null}
    </GlassCard>
  );
}
