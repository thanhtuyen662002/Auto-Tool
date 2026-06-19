export type UserFacingTermKey =
  | 'ocr'
  | 'asr'
  | 'tts'
  | 'vad'
  | 'ffmpeg'
  | 'ffprobe'
  | 'provider'
  | 'fps'
  | 'confidence'
  | 'region'
  | 'fallback'
  | 'batch'
  | 'overlay'
  | 'render'
  | 'preset'
  | 'workflow';

export type UserFacingTerm = {
  key: UserFacingTermKey;
  label: string;
  technical?: string;
  description: string;
};

export const USER_FACING_TERMS: Record<UserFacingTermKey, UserFacingTerm> = {
  ocr: {
    key: 'ocr',
    label: 'Đọc chữ trên video',
    technical: 'OCR',
    description: 'Tool nhìn vào khung hình để đọc chữ dính sẵn trên video, ví dụ phụ đề Trung.',
  },
  asr: {
    key: 'asr',
    label: 'Nghe lời thoại',
    technical: 'ASR',
    description: 'Tool nghe âm thanh trong video để nhận ra người trong video đang nói gì.',
  },
  tts: {
    key: 'tts',
    label: 'Giọng đọc tiếng Việt',
    technical: 'TTS',
    description: 'Tool tạo file giọng đọc tiếng Việt từ nội dung phụ đề hoặc kịch bản.',
  },
  vad: {
    key: 'vad',
    label: 'Bỏ qua đoạn im lặng',
    technical: 'VAD',
    description: 'Tool lọc các đoạn không có tiếng người để nghe lời thoại chính xác hơn.',
  },
  ffmpeg: {
    key: 'ffmpeg',
    label: 'Bộ dựng video',
    technical: 'FFmpeg',
    description: 'Thành phần dùng để cắt, ghép, gắn phụ đề, trộn nhạc và xuất video cuối.',
  },
  ffprobe: {
    key: 'ffprobe',
    label: 'Bộ đọc thông tin video',
    technical: 'ffprobe',
    description: 'Thành phần dùng để kiểm tra độ dài, kích thước, âm thanh và lỗi của video.',
  },
  provider: {
    key: 'provider',
    label: 'Bộ xử lý',
    technical: 'Provider',
    description: 'Dịch vụ hoặc thư viện mà tool dùng cho một việc cụ thể, ví dụ đọc chữ hoặc tạo giọng.',
  },
  fps: {
    key: 'fps',
    label: 'Số lần quét mỗi giây',
    technical: 'FPS',
    description: 'Càng cao thì tool kiểm tra nhiều khung hình hơn, nhưng xử lý sẽ chậm hơn.',
  },
  confidence: {
    key: 'confidence',
    label: 'Độ chắc chắn',
    technical: 'Confidence',
    description: 'Mức tin cậy của kết quả nhận diện. Số cao hơn thường ít sai hơn nhưng có thể bỏ sót nhiều hơn.',
  },
  region: {
    key: 'region',
    label: 'Vùng quét',
    technical: 'Region',
    description: 'Khu vực trên video mà tool sẽ tập trung đọc chữ hoặc che phụ đề gốc.',
  },
  fallback: {
    key: 'fallback',
    label: 'Phương án dự phòng',
    technical: 'Fallback',
    description: 'Cách xử lý thay thế khi cách chính không hoạt động hoặc không đủ dữ liệu.',
  },
  batch: {
    key: 'batch',
    label: 'Lô video',
    technical: 'Batch',
    description: 'Một nhóm nhiều video được đưa vào tool để xử lý hàng loạt.',
  },
  overlay: {
    key: 'overlay',
    label: 'Khung phủ',
    technical: 'Overlay',
    description: 'Lớp ảnh hoặc nền đặt lên video, thường dùng để trang trí hoặc che phụ đề gốc.',
  },
  render: {
    key: 'render',
    label: 'Xuất video',
    technical: 'Render',
    description: 'Bước tạo file MP4 cuối cùng sau khi đã cắt, dịch, gắn phụ đề, trộn nhạc và giọng đọc.',
  },
  preset: {
    key: 'preset',
    label: 'Mẫu cấu hình',
    technical: 'Preset',
    description: 'Bộ thiết lập có sẵn để chọn nhanh theo kiểu video cần làm.',
  },
  workflow: {
    key: 'workflow',
    label: 'Quy trình xử lý',
    technical: 'Workflow',
    description: 'Chuỗi bước tool sẽ chạy từ lúc quét video đến khi xuất kết quả.',
  },
};

export function friendlyTermLabel(key: UserFacingTermKey, includeTechnical = true): string {
  const term = USER_FACING_TERMS[key];
  if (!includeTechnical || !term.technical) return term.label;
  return `${term.label} (${term.technical})`;
}
