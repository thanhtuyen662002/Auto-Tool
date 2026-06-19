import { ArrowRight, Clock3, FolderOpen, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { StartWorkflowMode } from '../../types/startWorkflow';
import GlassBadge from '../glass/GlassBadge';
import GlassButton from '../glass/GlassButton';
import StartModeToggle from './StartModeToggle';

export default function WorkflowHero({
  mode,
  onFocusStart,
}: {
  mode: StartWorkflowMode;
  onFocusStart: () => void;
}) {
  const silent = mode === 'silent_immersive';
  return (
    <section className="glass-card-strong overflow-hidden p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 max-w-3xl">
          <div className="flex flex-wrap items-center gap-2">
            <GlassBadge variant={silent ? 'success' : 'ready'}>{silent ? 'Video không thoại' : 'Reup Douyin'}</GlassBadge>
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-slate-400">
              <Clock3 size={13} />
              Quy trình hàng loạt
            </span>
          </div>
          <h1 className="mt-3 text-2xl font-semibold text-white">
            {silent ? 'Tạo video immersive không thoại' : 'Dịch và dựng lại video Douyin'}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
            {silent
              ? 'Phù hợp video mở hộp, review đồ gia dụng, setup phòng, chỉ có nhạc hoặc tiếng thao tác.'
              : 'Chọn folder video, chọn preset phù hợp, Auto Tool sẽ tạo phụ đề Việt và video output cho bạn.'}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <GlassButton variant="primary" onClick={onFocusStart}>
              <Sparkles size={16} />
              Bắt đầu lô mới
            </GlassButton>
            <Link
              className="inline-flex min-h-10 items-center gap-2 rounded-md border border-white/15 bg-white/8 px-4 py-2 text-sm font-semibold text-white hover:border-cyan-300/45"
              to="/results"
            >
              <FolderOpen size={16} />
              Xem kết quả gần đây
            </Link>
          </div>
        </div>
        <div className="grid gap-3">
          <StartModeToggle mode={mode} />
          <div className="hidden items-center gap-2 text-xs text-slate-400 sm:flex">
            <span>Thư mục</span>
            <ArrowRight size={13} />
            <span>Mẫu</span>
            <ArrowRight size={13} />
            <span>Chạy</span>
          </div>
        </div>
      </div>
    </section>
  );
}
