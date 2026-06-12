import { AudioLines, Captions, ScanText, Sparkles, Waves } from 'lucide-react';
import GlassBadge from '../glass/GlassBadge';
import GlassCard from '../glass/GlassCard';

type Props = {
  id: string;
  name: string;
  description: string;
  badge?: string;
  active?: boolean;
  silent?: boolean;
  review?: boolean;
  ocr?: boolean;
  onClick: () => void;
};

export default function PresetCard({ id, name, description, badge, active, silent, review, ocr, onClick }: Props) {
  const Icon = silent ? Waves : ocr ? ScanText : review ? Captions : id.includes('voice') ? AudioLines : Sparkles;
  return (
    <button className="w-full text-left" type="button" onClick={onClick} aria-pressed={active}>
      <GlassCard active={active} hover className="h-full p-4">
        <div className="flex items-start gap-3">
          <div className={`grid h-10 w-10 shrink-0 place-items-center rounded-md border ${active ? 'border-cyan-200/50 bg-cyan-300/15 text-cyan-100' : 'border-white/12 bg-white/7 text-slate-300'}`}><Icon size={19} /></div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-start justify-between gap-2"><h3 className="font-semibold text-white">{name}</h3>{badge ? <GlassBadge variant={active ? 'ready' : 'neutral'}>{badge}</GlassBadge> : null}</div>
            <p className="mt-2 line-clamp-2 text-sm leading-5 text-slate-300">{description}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">{silent ? <GlassBadge>Silent</GlassBadge> : null}{review ? <GlassBadge variant="needs_review">Review</GlassBadge> : null}{ocr ? <GlassBadge>OCR</GlassBadge> : null}</div>
          </div>
        </div>
      </GlassCard>
    </button>
  );
}
