import { useState } from 'react';
import type { NormalizedSystemStatus } from '../../services/healthApi';
import { getLocalUiSettings } from '../../utils/localSettings';
import GlassCard from '../glass/GlassCard';
import SetupHelpModal, { type SetupHelpTopic } from './SetupHelpModal';
import SetupRequirementCard from './SetupRequirementCard';

type Props = {
  status: NormalizedSystemStatus;
  onRefresh?: () => void;
  prominent?: boolean;
};

export default function FirstRunChecklist({ status, onRefresh, prominent }: Props) {
  const [helpTopic, setHelpTopic] = useState<SetupHelpTopic | null>(null);
  const settings = getLocalUiSettings();

  return (
    <>
      <GlassCard strong className={`p-5 ${prominent ? 'border-cyan-300/35 glow-primary' : ''}`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Checklist trước khi chạy batch đầu tiên</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-300">
              Kiểm tra nhanh những thứ quan trọng. OCR và TTS là optional, nên bạn không cần cấu hình ngay nếu chưa dùng tới.
            </p>
          </div>
        </div>
        <div className="mt-5 grid gap-3 lg:grid-cols-2">
          <SetupRequirementCard
            title="Backend"
            description="Server xử lý local cho scan, render và xuất kết quả."
            status={status.backend === 'connected' ? 'connected' : 'offline'}
            topic="backend"
            onHelp={setHelpTopic}
            onRetry={onRefresh}
          />
          <SetupRequirementCard
            title="FFmpeg"
            description="Tool cần FFmpeg để đọc và render video."
            status={status.ffmpeg}
            topic="ffmpeg"
            onHelp={setHelpTopic}
            onRetry={onRefresh}
          />
          <SetupRequirementCard
            title="Output folder"
            description={settings.defaultOutputFolder ? `Đang dùng: ${settings.defaultOutputFolder}` : 'Chưa chọn nơi lưu video output mặc định.'}
            status={settings.defaultOutputFolder ? 'ready' : 'missing'}
            topic="output"
            onHelp={setHelpTopic}
          />
          <SetupRequirementCard
            title="Music folder"
            description={settings.defaultMusicFolder ? `Đang dùng: ${settings.defaultMusicFolder}` : 'Không bắt buộc. Có thể giữ âm thanh gốc hoặc chọn sau trong batch.'}
            status={settings.defaultMusicFolder ? 'ready' : 'optional'}
            topic="output"
            optional
            onHelp={setHelpTopic}
          />
          <SetupRequirementCard
            title="OCR"
            description="Chỉ cần khi video có chữ Trung hardcoded trên màn hình."
            status={status.ocr}
            topic="ocr"
            optional
            onHelp={setHelpTopic}
            onRetry={onRefresh}
          />
          <SetupRequirementCard
            title="TTS"
            description="Chỉ cần khi tạo voiceover tiếng Việt cho Silent Mode."
            status={status.tts}
            topic="tts"
            optional
            onHelp={setHelpTopic}
            onRetry={onRefresh}
          />
        </div>
      </GlassCard>
      <SetupHelpModal topic={helpTopic} onClose={() => setHelpTopic(null)} />
    </>
  );
}
