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
  
  // Do not show the general health status badge ("Cảnh báo") if we are already showing the warning count badge
  const showHealthBadge = !(
    (item.health === 'warning' || item.health === 'needs_review') &&
    item.warningCount > 0
  );

  return (
    <div className="flex flex-wrap gap-1">
      {showHealthBadge && (
        <GlassBadge variant={healthVariant} size="sm" className="gap-1">
          {item.health === 'ready' ? <CheckCircle2 size={11} /> : item.health === 'processing' ? <Clock3 size={11} /> : <AlertTriangle size={11} />}
          {statusLabel(item.health)}
        </GlassBadge>
      )}
      <GlassBadge variant={item.qaStatus === 'failed' ? 'failed' : item.qaStatus === 'passed' ? 'success' : item.qaStatus === 'warning' ? 'warning' : 'neutral'} size="sm" className="gap-1">
        <QAIcon size={11} />
        {qaLabel(item.qaStatus)}
      </GlassBadge>
      {item.warningCount ? (
        <GlassBadge variant="warning" size="sm" className="gap-1">
          <AlertTriangle size={11} />
          {item.warningCount} cảnh báo
        </GlassBadge>
      ) : null}
    </div>
  );
}
