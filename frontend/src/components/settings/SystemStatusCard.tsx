import type { NormalizedSystemStatus } from '../../services/healthApi';
import StudioSystemStatus from '../studio/StudioSystemStatus';

export default function SystemStatusCard({
  status,
  loading,
  onRefresh,
}: {
  status: NormalizedSystemStatus;
  loading?: boolean;
  onRefresh?: () => void;
}) {
  return <StudioSystemStatus status={status} loading={loading} onRefresh={onRefresh} />;
}
