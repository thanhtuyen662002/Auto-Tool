import { Captions, Clapperboard, FolderCheck, HelpCircle, Waves } from 'lucide-react';
import { Link } from 'react-router-dom';
import GlassCard from '../glass/GlassCard';

const actions = [
  { label: 'Video có thoại', detail: 'Dịch và render Douyin Reup', to: '/douyin-reup', icon: Clapperboard },
  { label: 'Video không thoại', detail: 'Caption immersive', to: '/silent-mode', icon: Waves },
  { label: 'Sửa phụ đề', detail: 'Review, rút gọn, approve', to: '/subtitle-review', icon: Captions },
  { label: 'Kết quả gần đây', detail: 'Gallery và export pack', to: '/results', icon: FolderCheck },
  { label: 'Trợ giúp', detail: 'Chọn workflow phù hợp', to: '/help', icon: HelpCircle },
];

export default function StudioQuickActions() {
  return (
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5" aria-label="Thao tác nhanh">
      {actions.map(({ icon: Icon, ...action }) => (
        <Link to={action.to} key={action.to}>
          <GlassCard hover className="h-full p-4">
            <div className="flex items-start gap-3">
              <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-cyan-300/25 bg-cyan-300/10 text-cyan-200">
                <Icon size={17} />
              </div>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-white">{action.label}</div>
                <div className="mt-1 text-xs leading-5 text-slate-400">{action.detail}</div>
              </div>
            </div>
          </GlassCard>
        </Link>
      ))}
    </section>
  );
}
