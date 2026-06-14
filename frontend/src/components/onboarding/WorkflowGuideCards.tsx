import { ArrowRight, Captions, Clapperboard, Waves, ShoppingBag } from 'lucide-react';
import { Link } from 'react-router-dom';
import GlassBadge from '../glass/GlassBadge';
import GlassCard from '../glass/GlassCard';

const workflows = [
  {
    title: 'Video có thoại',
    subtitle: 'Douyin Reup',
    description: 'Dùng khi video có người nói tiếng Trung. Tool sẽ nhận diện lời thoại, dịch sang tiếng Việt, cho bạn review phụ đề rồi render.',
    preset: 'Safe Review',
    to: '/douyin-reup',
    action: 'Bắt đầu với Video có thoại',
    icon: Clapperboard,
    accent: 'text-cyan-200 bg-cyan-300/10 border-cyan-300/30',
  },
  {
    title: 'Video không thoại',
    subtitle: 'Silent Mode',
    description: 'Dùng cho video chỉ có nhạc, thao tác, mở hộp hoặc demo sản phẩm. Tool sẽ tạo caption Việt theo cảnh quay.',
    preset: 'Chill Immersive',
    to: '/silent-mode',
    action: 'Bắt đầu với Video không thoại',
    icon: Waves,
    accent: 'text-pink-200 bg-pink-300/10 border-pink-300/30',
  },
  {
    title: 'Video tiếp thị liên kết',
    subtitle: 'Dựng video sản phẩm',
    description: '1. Import sản phẩm Shopee/TikTok Shop\n2. Tạo project cấu hình\n3. Thêm video nguồn\n4. Chạy render hàng loạt',
    preset: 'UGC Reviewer Natural',
    to: '/projects/new',
    action: 'Tạo dự án',
    icon: ShoppingBag,
    accent: 'text-purple-200 bg-purple-300/10 border-purple-300/30',
  },
  {
    title: 'Chỉ sửa phụ đề',
    subtitle: 'Subtitle Review',
    description: 'Dùng khi bạn đã có phụ đề hoặc review document và muốn sửa, rút gọn, duyệt rồi render lại.',
    preset: 'Review trước khi render',
    to: '/subtitle-review',
    action: 'Mở danh sách phụ đề',
    icon: Captions,
    accent: 'text-emerald-200 bg-emerald-300/10 border-emerald-300/30',
  },
];

export default function WorkflowGuideCards() {
  return (
    <section className="grid gap-4 xl:grid-cols-4" aria-label="Chọn quy trình">
      {workflows.map(({ icon: Icon, ...workflow }) => (
        <GlassCard hover strong className="flex min-h-[218px] flex-col p-4" key={workflow.title}>
          <div className={`grid h-11 w-11 place-items-center rounded-md border ${workflow.accent}`}>
            <Icon size={21} />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-white">{workflow.title}</h2>
            <span className="text-xs text-slate-500">{workflow.subtitle}</span>
          </div>
          <p className="mt-2 max-h-24 flex-1 overflow-hidden text-sm leading-6 text-slate-300 whitespace-pre-line">{workflow.description}</p>
          <div className="mt-4">
            <GlassBadge variant="neutral">Gợi ý: {workflow.preset}</GlassBadge>
          </div>
          <Link className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-cyan-200 hover:text-cyan-100" to={workflow.to}>
            {workflow.action}
            <ArrowRight size={16} />
          </Link>
        </GlassCard>
      ))}
    </section>
  );
}

