import GlassModal from '../glass/GlassModal';

export type SetupHelpTopic = 'backend' | 'ffmpeg' | 'ocr' | 'tts' | 'translation' | 'output';

const helpContent: Record<SetupHelpTopic, { title: string; problem: string; why: string; fix: string; link?: string }> = {
  backend: {
    title: 'Backend',
    problem: 'Frontend chưa nhận được phản hồi từ server xử lý local.',
    why: 'Backend chịu trách nhiệm quét video, xuất video, đọc chữ trên video, tạo giọng đọc và lưu kết quả.',
    fix: 'Mở terminal backend và chạy lệnh khởi động theo README của dự án, sau đó bấm kiểm tra lại.',
  },
  ffmpeg: {
    title: 'Bộ dựng video',
    problem: 'Tool chưa xác định được bộ dựng video FFmpeg.',
    why: 'Thành phần này cần để đọc, ghép, gắn phụ đề và xuất video cuối.',
    fix: 'Để Auto Tool tự cài lại, hoặc đặt đường dẫn FFmpeg trong cấu hình rồi khởi động lại ứng dụng.',
  },
  ocr: {
    title: 'Đọc chữ trên video',
    problem: 'Bộ đọc chữ trên video chưa sẵn sàng hoặc chưa cấu hình.',
    why: 'Chỉ cần khi video có chữ Trung dính trên màn hình hoặc phụ đề đã dính vào hình.',
    fix: 'Nếu bạn chủ yếu dùng video có thoại rõ, có thể bỏ qua. Khi cần đọc chữ, chọn bộ xử lý trong cài đặt nâng cao rồi kiểm tra lại.',
  },
  tts: {
    title: 'Giọng đọc tiếng Việt',
    problem: 'Dịch vụ tạo giọng đọc chưa sẵn sàng hoặc chưa cấu hình.',
    why: 'Chỉ cần khi bạn muốn tạo lời thoại tiếng Việt cho video không thoại hoặc video affiliate.',
    fix: 'Bạn vẫn có thể xuất video chỉ có caption. Khi cần giọng đọc, cấu hình Piper hoặc Google Cloud TTS.',
  },
  translation: {
    title: 'Dịch sang tiếng Việt',
    problem: 'Tool chưa xác định được dịch vụ dịch.',
    why: 'Dịch vụ này dùng để chuyển phụ đề hoặc caption sang tiếng Việt.',
    fix: 'Kiểm tra API key trong Cài đặt hệ thống hoặc chọn lại dịch vụ dịch trong cài đặt nâng cao.',
  },
  output: {
    title: 'Thư mục đầu ra',
    problem: 'Chưa chọn nơi lưu video sau khi xuất.',
    why: 'Mỗi lô video cần một thư mục đầu ra để lưu video, phụ đề, log và gói xuất bản.',
    fix: 'Vào Cài đặt hệ thống, chọn thư mục đầu ra dễ nhớ, ví dụ D:/auto-tool/outputs.',
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
