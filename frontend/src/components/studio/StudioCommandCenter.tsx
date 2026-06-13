import { Captions, Clapperboard, FolderCheck, Server, Waves, FolderPlus } from 'lucide-react';
import { Link } from 'react-router-dom';
import GlassModal from '../glass/GlassModal';

type Action = {
  label: string;
  description: string;
  to?: string;
  icon: typeof Clapperboard;
  onClick?: () => void;
};

export default function StudioCommandCenter({
  open,
  onClose,
  onSystemStatus,
}: {
  open: boolean;
  onClose: () => void;
  onSystemStatus: () => void;
}) {
  const actions: Action[] = [
    { label: 'Douyin Reup', description: 'Dịch thoại Trung sang Việt, review phụ đề rồi render.', to: '/douyin-reup', icon: Clapperboard },
    { label: 'Silent Mode', description: 'Tạo caption Việt cho video mở hộp, thao tác hoặc demo sản phẩm.', to: '/silent-mode', icon: Waves },
    { label: 'Product Video Builder', description: 'Tạo video quảng cáo sản phẩm hàng loạt từ video tư liệu thô.', to: '/projects/new', icon: FolderPlus },
    { label: 'Mở phụ đề cần review', description: 'Sửa, rút gọn và duyệt phụ đề trước khi render.', to: '/subtitle-review', icon: Captions },
    { label: 'Mở kết quả gần đây', description: 'Xem gallery, Final QA và Export Pack.', to: '/results', icon: FolderCheck },
    {
      label: 'Kiểm tra hệ thống',
      description: 'Xem Backend, FFmpeg, OCR, TTS và provider.',
      icon: Server,
      onClick: () => {
        onClose();
        onSystemStatus();
      },
    },
  ];

  return (
    <GlassModal open={open} title="Quick Start" onClose={onClose}>
      <div className="grid gap-3">
        {actions.map(({ icon: Icon, ...action }) => {
          const content = (
            <div className="flex items-start gap-3 rounded-md border border-white/10 bg-black/18 p-4 text-left transition hover:border-cyan-300/35 hover:bg-white/8">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-cyan-300/25 bg-cyan-300/10 text-cyan-200">
                <Icon size={18} />
              </div>
              <div>
                <div className="font-semibold text-white">{action.label}</div>
                <div className="mt-1 text-sm leading-6 text-slate-400">{action.description}</div>
              </div>
            </div>
          );

          if (action.to) {
            return (
              <Link to={action.to} onClick={onClose} key={action.label}>
                {content}
              </Link>
            );
          }

          return (
            <button className="text-left" type="button" onClick={action.onClick} key={action.label}>
              {content}
            </button>
          );
        })}
      </div>
    </GlassModal>
  );
}

