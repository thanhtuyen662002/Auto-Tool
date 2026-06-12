import type { SubtitleReviewLine, SubtitleReviewStatus } from '../../types/project';

export type SubtitleLineFilter = 'all' | 'needs_review' | 'critical' | 'edited' | 'unedited' | 'ocr' | 'asr' | 'visual';
export type SubtitleLineSort = 'timeline' | 'quality' | 'edited' | 'critical';

export function formatSubtitleTime(ms: number) {
  const totalSeconds = ms / 1000;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds - minutes * 60;
  return `${minutes}:${seconds.toFixed(2).padStart(5, '0')}`;
}

export function statusLabel(status: SubtitleReviewStatus) {
  return ({ pending: 'Chờ kiểm tra', reviewed: 'Đã kiểm tra', needs_fix: 'Cần sửa', approved: 'Đã duyệt' } as const)[status];
}

export function sourceLabel(source?: string | null) {
  const labels: Record<string, string> = {
    sidecar_srt: 'Phụ đề SRT', embedded_subtitle: 'Phụ đề trong video', asr: 'Nhận diện giọng nói',
    ocr_hardsub: 'OCR chữ Trung', ocr_translation: 'OCR đã dịch', visual_generated: 'Tạo từ cảnh',
    template: 'Mẫu caption', manual: 'Thủ công',
  };
  return source ? labels[source] ?? source : 'Tạo từ cảnh quay';
}

export function qualityLabel(line: SubtitleReviewLine) {
  if (line.quality_severity === 'critical') return 'Lỗi nặng';
  if (line.quality_needs_review) return 'Cần kiểm tra';
  return 'Ổn';
}

export function lineText(line: SubtitleReviewLine) {
  return line.edited_text ?? line.translated_text;
}

export function hasChinese(value: string) {
  return /[\u3400-\u9fff]/.test(value);
}
