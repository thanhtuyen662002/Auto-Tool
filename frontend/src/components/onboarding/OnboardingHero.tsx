import { ArrowRight, CheckCircle2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import GlassBadge from '../glass/GlassBadge';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';

export default function OnboardingHero({ onSkip }: { onSkip?: () => void }) {
  return (
    <GlassCard strong className="overflow-hidden p-6 sm:p-7">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-center">
        <div>
          <GlassBadge variant="ready">Bắt đầu nhanh</GlassBadge>
          <h1 className="mt-4 max-w-3xl text-3xl font-semibold leading-tight text-white sm:text-4xl">
            Bắt đầu tạo video đầu tiên của bạn
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-300">
            Chọn workflow phù hợp, kiểm tra hệ thống, chọn output folder mặc định rồi chạy một batch nhỏ để làm quen.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/douyin-reup">
              <GlassButton variant="primary">
                Video có thoại
                <ArrowRight size={16} />
              </GlassButton>
            </Link>
            <Link to="/silent-mode">
              <GlassButton variant="secondary">Video không thoại</GlassButton>
            </Link>
            {onSkip ? (
              <GlassButton variant="ghost" onClick={onSkip}>
                Bỏ qua
              </GlassButton>
            ) : null}
          </div>
        </div>
        <div className="grid gap-3 rounded-md border border-white/10 bg-black/18 p-4">
          {['Chọn workflow', 'Kiểm tra Backend và FFmpeg', 'Chọn output folder', 'Chạy batch test nhỏ'].map((item, index) => (
            <div className="flex items-center gap-3 text-sm text-slate-200" key={item}>
              <span className="grid h-7 w-7 place-items-center rounded-full border border-cyan-300/30 bg-cyan-300/10 text-xs font-semibold text-cyan-100">
                {index + 1}
              </span>
              <span className="flex-1">{item}</span>
              <CheckCircle2 size={15} className="text-slate-500" />
            </div>
          ))}
        </div>
      </div>
    </GlassCard>
  );
}
