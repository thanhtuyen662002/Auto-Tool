import { AlertTriangle, ChevronDown, ChevronUp, Flag, Pause, Play } from 'lucide-react';
import { useState, type RefObject } from 'react';
import type { SubtitleReviewLine } from '../../types/project';
import GlassBadge from '../glass/GlassBadge';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';
import { formatSubtitleTime, lineText, qualityLabel } from './subtitleUi';

interface Props { videoRef: RefObject<HTMLVideoElement | null>; videoUrl: string; activeLine: SubtitleReviewLine | null; onPrevious: () => void; onNext: () => void; onNextFlagged: () => void; hasFlagged: boolean; }

export default function SubtitleVideoPanel({ videoRef, videoUrl, activeLine, onPrevious, onNext, onNextFlagged, hasFlagged }: Props) {
  const [videoFailed, setVideoFailed] = useState(false);
  const [playing, setPlaying] = useState(false);
  function togglePlayback() { const video = videoRef.current; if (!video || videoFailed) return; if (video.paused) void video.play(); else video.pause(); }
  return <div className="grid gap-4 min-[900px]:sticky min-[900px]:top-20">
    <GlassCard className="overflow-hidden" strong>
      <div className="relative bg-black/70">
        {!videoFailed ? <video ref={videoRef} className="aspect-[9/16] max-h-[58vh] w-full object-contain" src={videoUrl} controls onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onError={() => setVideoFailed(true)} /> : <div className="flex aspect-[9/16] max-h-[58vh] flex-col items-center justify-center gap-3 p-8 text-center text-slate-300"><AlertTriangle className="text-amber-200" size={28} /><div className="font-semibold">Không thể mở video preview</div><p className="text-sm text-slate-500">Bạn vẫn có thể sửa phụ đề bằng danh sách bên phải.</p></div>}
      </div>
      <div className="p-4">
        <div className="flex items-center justify-between gap-3"><div><div className="text-xs font-semibold uppercase text-slate-500">Dòng hiện tại</div>{activeLine ? <div className="mt-1 text-xs text-slate-400">{formatSubtitleTime(activeLine.start_ms)} → {formatSubtitleTime(activeLine.end_ms)}</div> : null}</div>{activeLine ? <GlassBadge variant={activeLine.quality_severity === 'critical' ? 'failed' : activeLine.quality_needs_review ? 'warning' : 'success'}>{qualityLabel(activeLine)}</GlassBadge> : null}</div>
        <div className="mt-3 min-h-20 rounded-md border border-white/10 bg-slate-950/90 p-4 text-center text-base font-semibold leading-7 text-white">{activeLine ? lineText(activeLine) : 'Chọn một dòng phụ đề để bắt đầu.'}</div>
        <div className="mt-3 grid grid-cols-4 gap-2"><IconButton title="Dòng trước" onClick={onPrevious}><ChevronUp size={17} /></IconButton><IconButton title={playing ? 'Tạm dừng' : 'Phát video'} disabled={videoFailed} onClick={togglePlayback}>{playing ? <Pause size={17} /> : <Play size={17} />}</IconButton><IconButton title="Dòng tiếp theo" onClick={onNext}><ChevronDown size={17} /></IconButton><IconButton title="Dòng lỗi tiếp theo" disabled={!hasFlagged} onClick={onNextFlagged}><Flag size={17} /></IconButton></div>
      </div>
    </GlassCard>
  </div>;
}

function IconButton({ title, children, onClick, disabled }: { title: string; children: React.ReactNode; onClick: () => void; disabled?: boolean }) { return <GlassButton className="px-2" variant="ghost" title={title} aria-label={title} disabled={disabled} onClick={onClick}>{children}</GlassButton>; }
