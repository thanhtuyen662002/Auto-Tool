import { MessageCircle, VolumeX } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { StartWorkflowMode } from '../../types/startWorkflow';

export default function StartModeToggle({ mode }: { mode: StartWorkflowMode }) {
  const options = [
    { value: 'douyin_voice', label: 'Video có thoại', href: '/douyin-reup', icon: MessageCircle },
    { value: 'silent_immersive', label: 'Không thoại / immersive', href: '/silent-mode', icon: VolumeX },
  ] as const;
  return (
    <div className="grid gap-2 sm:min-w-[260px]">
      {options.map((item) => {
        const Icon = item.icon;
        const active = item.value === mode;
        return (
          <Link
            className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-semibold transition ${
              active
                ? 'border-cyan-300/55 bg-cyan-300/12 text-cyan-100'
                : 'border-white/10 bg-white/5 text-slate-300 hover:bg-white/10'
            }`}
            key={item.value}
            to={item.href}
          >
            <Icon size={16} />
            {item.label}
          </Link>
        );
      })}
    </div>
  );
}
