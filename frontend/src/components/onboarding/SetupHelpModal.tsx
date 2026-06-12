import GlassModal from '../glass/GlassModal';

export type SetupHelpTopic = 'backend' | 'ffmpeg' | 'ocr' | 'tts' | 'translation' | 'output';

const helpContent: Record<SetupHelpTopic, { title: string; problem: string; why: string; fix: string; link?: string }> = {
  backend: {
    title: 'Backend',
    problem: 'Frontend chưa nhận được phản hồi từ server xử lý local.',
    why: 'Backend chịu trách nhiệm scan video, render, OCR, TTS và xuất kết quả.',
    fix: 'Mở terminal backend và chạy lệnh khởi động theo README của dự án, sau đó bấm kiểm tra lại.',
  },
  ffmpeg: {
    title: 'FFmpeg',
    problem: 'Tool chưa xác định được FFmpeg.',
    why: 'FFmpeg cần để đọc, ghép, burn subtitle và render video cuối.',
    fix: 'Cài FFmpeg hoặc đặt đường dẫn FFmpeg trong cấu hình backend rồi khởi động lại backend.',
  },
  ocr: {
    title: 'OCR',
    problem: 'OCR chưa sẵn sàng hoặc chưa cấu hình.',
    why: 'OCR chỉ cần khi video có chữ Trung dính trên màn hình hoặc subtitle hardcoded.',
    fix: 'Nếu bạn chủ yếu dùng video có thoại, có thể bỏ qua. Khi cần OCR, cấu hình provider trong backend rồi test lại.',
  },
  tts: {
    title: 'TTS',
    problem: 'TTS chưa sẵn sàng hoặc chưa cấu hình.',
    why: 'TTS chỉ cần khi bạn muốn tạo voiceover tiếng Việt cho Silent Mode.',
    fix: 'Bạn vẫn có thể render caption không thoại. Khi cần voiceover, cấu hình Piper hoặc Google Cloud TTS.',
  },
  translation: {
    title: 'Translation provider',
    problem: 'Tool chưa xác định được provider dịch.',
    why: 'Provider dịch dùng để chuyển phụ đề hoặc caption sang tiếng Việt.',
    fix: 'Kiểm tra file cấu hình backend hoặc mục provider nâng cao nếu dự án cho phép chỉnh từ UI.',
  },
  output: {
    title: 'Output folder',
    problem: 'Chưa chọn nơi lưu video sau khi render.',
    why: 'Mỗi batch cần một thư mục output để lưu video, subtitle, log và export pack.',
    fix: 'Vào Settings > Paths, chọn default output folder dễ nhớ, ví dụ D:/auto-tool/outputs.',
  },
};

export default function SetupHelpModal({ topic, onClose }: { topic: SetupHelpTopic | null; onClose: () => void }) {
  if (!topic) return null;
  const content = helpContent[topic];

  return (
    <GlassModal open title={`Hướng dẫn setup: ${content.title}`} onClose={onClose}>
      <div className="grid gap-4 text-sm leading-6 text-slate-300">
        <section>
          <h3 className="text-sm font-semibold text-white">Vấn đề là gì?</h3>
          <p className="mt-1">{content.problem}</p>
        </section>
        <section>
          <h3 className="text-sm font-semibold text-white">Tại sao cần?</h3>
          <p className="mt-1">{content.why}</p>
        </section>
        <section>
          <h3 className="text-sm font-semibold text-white">Cách xử lý nhanh</h3>
          <p className="mt-1">{content.fix}</p>
        </section>
      </div>
    </GlassModal>
  );
}
