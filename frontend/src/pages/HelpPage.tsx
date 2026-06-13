import { ArrowRight, BookOpen, Captions, CheckCircle2, Clapperboard, FolderCheck, HelpCircle, Waves } from 'lucide-react';
import { Link } from 'react-router-dom';
import GlassBadge from '../components/glass/GlassBadge';
import GlassCard from '../components/glass/GlassCard';
import StudioQuickActions from '../components/studio/StudioQuickActions';

const helpCards = [
  {
    title: 'Workflow nào phù hợp với video của tôi?',
    icon: HelpCircle,
    body: 'Nếu video có người nói tiếng Trung, chọn Video có thoại. Nếu video chỉ có nhạc, thao tác, mở hộp hoặc demo sản phẩm, chọn Video không thoại.',
  },
  {
    title: 'Cần chuẩn bị gì trước khi chạy?',
    icon: CheckCircle2,
    body: 'Bạn cần backend chạy, FFmpeg sẵn sàng và một output folder. OCR/TTS là optional, chỉ cần khi workflow thật sự dùng tới.',
  },
  {
    title: 'Video có thoại dùng gì?',
    icon: Clapperboard,
    body: 'Tool nhận diện giọng nói hoặc subtitle có sẵn, dịch sang tiếng Việt, mở review phụ đề rồi render video mới.',
  },
  {
    title: 'Video không thoại / immersive',
    icon: Waves,
    body: 'Dùng khi video chỉ có nhạc, tiếng thao tác, mở hộp hoặc cảnh sản phẩm. Tool tạo caption Việt từ cảnh quay hoặc OCR chữ Trung nếu có.',
  },
  {
    title: 'Tại sao cần review phụ đề?',
    icon: Captions,
    body: 'Review giúp sửa câu, rút gọn dòng quá dài, tránh lỗi dịch và kiểm tra phụ đề trước khi burn vào video.',
  },
  {
    title: 'Export Pack là gì?',
    icon: FolderCheck,
    body: 'Export Pack gom video, caption, hashtag, QA report và file liên quan để bạn kiểm tra trước khi đăng lên nền tảng.',
  },
  {
    title: 'Các lỗi thường gặp',
    icon: BookOpen,
    body: 'Backend offline, thiếu FFmpeg, folder không tồn tại hoặc video không đọc được. Mỗi lỗi nên bắt đầu bằng kiểm tra System Status.',
  },
];

export default function HelpPage() {
  return (
    <main className="studio-page grid gap-6">
      <section>
        <GlassBadge variant="neutral">Trợ giúp</GlassBadge>
        <h1 className="mt-3 text-3xl font-semibold text-white">Hướng dẫn nhanh</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
          Các câu trả lời ngắn để bạn chọn đúng workflow, chuẩn bị hệ thống và hiểu các bước chính của Auto Tool Studio.
        </p>
      </section>

      <StudioQuickActions />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {helpCards.map(({ icon: Icon, ...card }) => (
          <GlassCard strong className="p-5" key={card.title}>
            <div className="flex items-start gap-3">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-cyan-300/25 bg-cyan-300/10 text-cyan-200">
                <Icon size={18} />
              </div>
              <div>
                <h2 className="font-semibold text-white">{card.title}</h2>
                <p className="mt-2 text-sm leading-6 text-slate-300">{card.body}</p>
              </div>
            </div>
          </GlassCard>
        ))}
      </section>

      <GlassCard strong className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-white">Bạn mới dùng Auto Tool?</h2>
            <p className="mt-1 text-sm text-slate-400">Đi qua onboarding để kiểm tra hệ thống và chọn workflow đầu tiên.</p>
          </div>
          <Link className="inline-flex items-center gap-2 text-sm font-semibold text-cyan-200 hover:text-cyan-100" to="/onboarding">
            Xem onboarding
            <ArrowRight size={16} />
          </Link>
        </div>
      </GlassCard>
    </main>
  );
}
