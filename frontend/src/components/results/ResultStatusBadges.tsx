import { AlertTriangle, CheckCircle2, Clock3, ShieldCheck, ShieldX } from 'lucide-react';
import { qaLabel, statusLabel, type NormalizedResultItem } from '../../utils/resultStatus';
import GlassBadge, { type GlassBadgeVariant } from '../glass/GlassBadge';

export default function ResultStatusBadges({ item }: { item: NormalizedResultItem }) {
  const healthVariant: GlassBadgeVariant =
    item.health === 'failed'
      ? 'failed'
      : item.health === 'warning' || item.health === 'needs_review'
        ? 'warning'
        : item.health === 'processing'
          ? 'processing'
          : item.health === 'ready'
            ? 'success'
            : 'neutral';
  const QAIcon = item.qaStatus === 'failed' ? ShieldX : item.qaStatus === 'passed' ? ShieldCheck : AlertTriangle;

  return (
    <div className="flex flex-wrap gap-1.5">
      <GlassBadge variant={healthVariant} className="gap-1.5">
        {item.health === 'ready' ? <CheckCircle2 size={13} /> : item.health === 'processing' ? <Clock3 size={13} /> : <AlertTriangle size={13} />}
        {statusLabel(item.health)}
      </GlassBadge>
      <GlassBadge variant={item.qaStatus === 'failed' ? 'failed' : item.qaStatus === 'passed' ? 'success' : item.qaStatus === 'warning' ? 'warning' : 'neutral'} className="gap-1.5">
        <QAIcon size={13} />
        {qaLabel(item.qaStatus)}
      </GlassBadge>
      {item.warningCount ? <GlassBadge variant="warning">{item.warningCount} cảnh báo</GlassBadge> : null}
    </div>
  );
}
