import { PackageSearch } from 'lucide-react';
import { useState } from 'react';
import GlassCard from '../glass/GlassCard';

export type ProductContextValue = {
  product_name: string;
  industry: string;
  features: string;
  cta: string;
};

export default function ProductContextCard({
  value,
  industries,
  tone,
  onChange,
  onToneChange,
  onPreview,
  onRegenerate,
  onCreateReview,
  hasPreview,
  busy,
}: {
  value: ProductContextValue;
  industries: Array<{ id: string; name: string }>;
  tone: string;
  onChange: (value: Partial<ProductContextValue>) => void;
  onToneChange: (value: string) => void;
  onPreview: () => void;
  onRegenerate: () => void;
  onCreateReview: () => void;
  hasPreview: boolean;
  busy: boolean;
}) {
  const [open, setOpen] = useState(false);
  return (
    <GlassCard className="grid gap-4 p-5" strong>
      <div className="flex items-start gap-3">
        <PackageSearch className="mt-1 shrink-0 text-amber-200" size={22} />
        <div className="min-w-0">
          <h2 className="font-semibold text-white">Thông tin sản phẩm optional</h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">Điền thêm nếu muốn caption/voiceover cụ thể hơn. Có thể bỏ trống.</p>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-200">Ngành hàng</span>
          <select className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white" value={value.industry} onChange={(event) => onChange({ industry: event.target.value })}>
            {industries.map((industry) => <option key={industry.id} value={industry.id}>{industry.name}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-200">Tone caption</span>
          <select className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white" value={tone} onChange={(event) => onToneChange(event.target.value)}>
            <option value="natural">Natural</option>
            <option value="cute">Cute</option>
            <option value="clean_review">Clean Review</option>
            <option value="sales_light">Sales Light</option>
            <option value="chill">Chill</option>
          </select>
        </label>
      </div>

      <button className="text-left text-sm font-semibold text-cyan-200 hover:text-cyan-100" type="button" onClick={() => setOpen((current) => !current)}>
        {open ? 'Ẩn thông tin sản phẩm' : 'Mở thông tin sản phẩm optional'}
      </button>

      {open ? (
        <div className="grid gap-3">
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-200">Tên sản phẩm</span>
            <input className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white" placeholder="Kệ để đồ nhà bếp" value={value.product_name} onChange={(event) => onChange({ product_name: event.target.value })} />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-200">3-5 điểm nổi bật</span>
            <textarea className="min-h-24 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 py-2 text-sm text-white" placeholder="Gọn, dễ lắp, tiết kiệm không gian" value={value.features} onChange={(event) => onChange({ features: event.target.value })} />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-200">CTA</span>
            <input className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white" placeholder="Xem chi tiết sản phẩm" value={value.cta} onChange={(event) => onChange({ cta: event.target.value })} />
          </label>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <button className="rounded-md border border-emerald-300/30 bg-emerald-300/10 px-3 py-2 text-sm font-semibold text-emerald-100 hover:bg-emerald-300/15 disabled:opacity-50" type="button" disabled={busy} onClick={onPreview}>
          Tạo caption preview
        </button>
        {hasPreview ? (
          <>
            <button className="rounded-md border border-white/15 bg-white/8 px-3 py-2 text-sm font-semibold text-white hover:bg-white/12 disabled:opacity-50" type="button" disabled={busy} onClick={onRegenerate}>
              Tạo lại captions
            </button>
            <button className="rounded-md border border-cyan-300/50 bg-cyan-300 px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-200 disabled:opacity-50" type="button" disabled={busy} onClick={onCreateReview}>
              Tạo review document
            </button>
          </>
        ) : null}
      </div>
    </GlassCard>
  );
}
