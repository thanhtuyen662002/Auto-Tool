interface WarningBoxProps {
  warnings?: string[] | null;
  title?: string;
}

export default function WarningBox({ warnings, title = 'Cảnh báo' }: WarningBoxProps) {
  const cleanWarnings = Array.from(new Set((warnings ?? [])
    .map((warning) => friendlyWarning(warning.trim()))
    .filter((warning): warning is string => Boolean(warning))
  )).slice(0, 6);

  if (!cleanWarnings.length) return null;

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
      <div className="font-semibold">{title}</div>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {cleanWarnings.map((warning, index) => (
          <li key={`${warning}-${index}`}>{warning}</li>
        ))}
      </ul>
    </div>
  );
}

export function friendlyWarning(value: string): string {
  const normalized = normalizeForMatch(value);

  if (value.includes('Voiceover duration') || value.includes('voice_longer_than_video')) {
    return 'Giọng đọc dài hơn video, audio đã được cắt theo thời lượng video.';
  }
  if (value.includes('voice_shorter_than_video') || normalized.includes('voice ngan hon video')) {
    return 'Giọng đọc ngắn hơn video, phần cuối video sẽ giữ im lặng.';
  }
  if (normalized.includes('subtitle') || normalized.includes('phu de')) {
    return 'Phụ đề đã được tự điều chỉnh để phù hợp với thời lượng video.';
  }
  if (value.includes('voice_timing_gap_compressed') || normalized.includes('khoang nghi giua cac cau voice')) {
    return 'Khoảng nghỉ giữa các câu giọng đọc đã được rút ngắn để nghe liền mạch hơn.';
  }
  if (value.includes('script_shortened_for_tts')) {
    return 'Nội dung giọng đọc đã được rút gọn để phù hợp với thời lượng video.';
  }
  if (value.includes('Silent TTS fallback')) {
    return 'Hệ thống tạo giọng đọc đã dùng âm thanh im lặng để tránh làm hỏng batch render.';
  }
  if (value.includes('voice_normalization_failed')) {
    return 'Không thể chuẩn hoá giọng đọc, hệ thống đã dùng âm thanh dự phòng.';
  }
  if (value.includes('tts_provider_changed') || normalized.includes('tts provider changed inside one voiceover')) {
    return 'Hệ thống đã giữ một giọng đọc thống nhất cho toàn bộ phần đọc.';
  }
  if (normalized.includes('edge tts succeeded on retry')) {
    return 'Edge TTS đã tạo giọng đọc thành công sau khi thử lại.';
  }
  if (normalized.includes('edge tts da tao giong doc thanh cong')) {
    return 'Edge TTS đã tạo giọng đọc thành công sau khi thử lại.';
  }
  if (normalized.includes('too few high-quality segments')) {
    return 'Có quá ít cảnh chất lượng cao, hệ thống đã dùng thêm cảnh dự phòng để đủ dòng thời gian.';
  }
  if (normalized.includes('subtitle burn failed')) {
    return 'Không burn được phụ đề, video vẫn được xuất với bản dự phòng.';
  }
  return value.replace(/\s+/g, ' ');
}

function normalizeForMatch(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}
