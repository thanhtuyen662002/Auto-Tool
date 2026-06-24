import { Image, PackageSearch, Pencil, RefreshCw } from 'lucide-react';
import type { ReactNode } from 'react';
import { assetFileUrl } from '../../api/client';
import type { SilentReupPlanResponse } from '../../types/project';
import GlassBadge from '../glass/GlassBadge';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';

interface Props {
  preview: SilentReupPlanResponse;
  editingSegmentId: string | null;
  onEditSegment: (segmentId: string | null) => void;
  onRegenerate: () => void;
  renderEditor: (segmentId: string) => ReactNode;
  disabled?: boolean;
}

export default function SilentPlanPreview({ preview, editingSegmentId, onEditSegment, onRegenerate, renderEditor, disabled }: Props) {
  const plan = preview.plan;
  return (
    <section className="grid gap-4 border-t border-white/10 pt-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h4 className="font-semibold text-white">Silent Plan Preview</h4><p className="mt-1 text-xs text-slate-400">Kiểm tra cảnh, visual tags và caption trước khi tạo review document.</p></div>
        <div className="flex flex-wrap gap-2"><GlassBadge variant={plan.caption_generation.average_quality_score < 0.7 ? 'warning' : 'success'}>Quality {Math.round(plan.caption_generation.average_quality_score * 100)}%</GlassBadge><GlassButton className="min-h-8 px-3 py-1 text-xs" variant="ghost" disabled={disabled} onClick={onRegenerate}><RefreshCw size={14} /> Regenerate</GlassButton></div>
      </div>

      {plan.product_detection ? (
        <GlassCard className="p-4" strong>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex min-w-0 items-start gap-3">
              <PackageSearch className="mt-0.5 shrink-0 text-cyan-200" size={20} />
              <div className="min-w-0">
                <div className="text-sm font-semibold text-white">Nhận diện sản phẩm</div>
                <p className="mt-1 text-sm text-slate-200">{productDetectionLabel(plan.product_detection)}</p>
                <p className="mt-1 text-xs text-slate-400">
                  {formatProductDetectionProvider(plan.product_detection.provider)} · {formatCertainty(plan.product_detection.top_candidate?.certainty)} · {formatConfidence(plan.product_detection.average_confidence)}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {plan.product_detection.frame_observations.length || plan.product_detection.frame_paths.length} frame · {plan.product_detection.focus_crop_paths.length} crop giảm nhiễu
                </p>
              </div>
            </div>
            {plan.product_detection.top_candidate?.visible_features.length ? (
              <div className="flex max-w-xl flex-wrap gap-1.5">
                {plan.product_detection.top_candidate.visible_features.slice(0, 4).map((feature) => (
                  <span key={feature} className="rounded border border-white/10 bg-white/8 px-2 py-1 text-[11px] text-slate-200">{feature}</span>
                ))}
              </div>
            ) : null}
          </div>
          {plan.product_detection.warnings.length ? (
            <p className="mt-3 text-xs leading-5 text-amber-200">{plan.product_detection.warnings.slice(0, 2).join(' ')}</p>
          ) : null}
        </GlassCard>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-2">
        {plan.visual_segments.map((segment, index) => {
          const caption = plan.captions.find((item) => item.segment_id === segment.id) ?? plan.captions[index];
          return (
            <GlassCard key={segment.id} className="overflow-hidden" strong>
              <div className="grid min-h-32 grid-cols-[112px_minmax(0,1fr)]">
                <div className="bg-black/35">
                  {segment.representative_frame_path ? <img className="h-full w-full object-cover" src={assetFileUrl(segment.representative_frame_path)} alt={`Khung hình segment ${index + 1}`} /> : <div className="flex h-full items-center justify-center text-slate-500"><Image size={25} /></div>}
                </div>
                <div className="p-3">
                  <div className="flex items-start justify-between gap-2"><div><div className="text-sm font-semibold text-white">Segment {index + 1}</div><div className="mt-1 text-xs text-slate-400">{formatTime(segment.start)} → {formatTime(segment.end)} · {formatTag(segment.segment_type)}</div></div><button className="rounded-md border border-white/10 p-2 text-slate-300 hover:bg-white/10" type="button" title="Sửa visual tags" onClick={() => onEditSegment(editingSegmentId === segment.id ? null : segment.id)}><Pencil size={14} /></button></div>
                  <div className="mt-3 flex flex-wrap gap-1.5">{segment.visual_tags.slice(0, 5).map((tag) => <span key={`${segment.id}-${tag.tag}`} className="rounded border border-cyan-300/15 bg-cyan-300/8 px-2 py-1 text-[11px] text-cyan-100">{tag.tag}</span>)}</div>
                </div>
              </div>
              {caption ? <div className="border-t border-white/10 p-3"><div className="text-xs text-slate-500">Caption · {caption.source || 'visual generated'}</div><p className={`mt-1 text-sm leading-6 ${caption.quality_needs_review ? 'text-amber-200' : 'text-slate-100'}`}>{caption.text}</p></div> : null}
              {editingSegmentId === segment.id ? <div className="border-t border-white/10 p-3">{renderEditor(segment.id)}</div> : null}
            </GlassCard>
          );
        })}
      </div>
    </section>
  );
}

function formatTime(value: number) {
  const minutes = Math.floor(value / 60);
  const seconds = Math.max(0, value - minutes * 60);
  return `${minutes}:${seconds.toFixed(1).padStart(4, '0')}`;
}

function formatTag(value?: string | null) {
  return (value || 'scene').replace(/[_-]+/g, ' ');
}

function productDetectionLabel(report: SilentReupPlanResponse['plan']['product_detection']) {
  const candidate = report?.top_candidate;
  if (!candidate) return 'Chưa có đủ dữ liệu để nhận diện sản phẩm.';
  return candidate.product_name || candidate.product_type || candidate.display_name || 'Sản phẩm trong video';
}

function formatConfidence(value?: number | null) {
  return `Độ chắc ${Math.round((value ?? 0) * 100)}%`;
}

function formatProductDetectionProvider(value?: string | null) {
  if (value === 'gemini_vision') return 'AI vision';
  if (value === 'manual_context') return 'Ngữ cảnh đã khóa';
  if (value === 'heuristic_fallback') return 'Suy luận an toàn';
  return 'Chưa nhận diện';
}

function formatCertainty(value?: string | null) {
  if (value === 'exact_product') return 'Có tên sản phẩm';
  if (value === 'product_type') return 'Chắc loại sản phẩm';
  if (value === 'category_only') return 'Chỉ chắc ngành hàng';
  return 'Chưa chắc';
}
