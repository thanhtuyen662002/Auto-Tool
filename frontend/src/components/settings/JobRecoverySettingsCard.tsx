import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import GlassButton from '../glass/GlassButton';
import SettingsSection from './SettingsSection';
import { getRecoveryCandidates, type RecoveryCandidate } from '../../services/jobRecoveryApi';

export default function JobRecoverySettingsCard() {
  const navigate = useNavigate();
  const [items, setItems] = useState<RecoveryCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refresh();
  }, []);

  const summary = useMemo(() => ({
    recoverable: items.filter((item) => item.recoverable).length,
    interrupted: items.filter((item) => item.status === 'interrupted' || item.status === 'recoverable').length,
    failed: items.reduce((sum, item) => sum + item.failed_items, 0),
  }), [items]);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const response = await getRecoveryCandidates();
      setItems(response.data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải danh sách job khôi phục.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <SettingsSection title="Job Recovery" description="Theo dõi các batch bị gián đoạn và mở Recovery Center để resume an toàn.">
      <div className="grid gap-3 md:grid-cols-3">
        <Metric label="Recoverable jobs" value={summary.recoverable} />
        <Metric label="Interrupted jobs" value={summary.interrupted} />
        <Metric label="Failed items" value={summary.failed} />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <GlassButton variant="primary" onClick={() => navigate('/recovery')}>Open Recovery Center</GlassButton>
        <GlassButton loading={loading} onClick={() => void refresh()}>Refresh</GlassButton>
      </div>
      {error ? <div className="mt-3 rounded-md border border-rose-400/30 bg-rose-400/10 p-3 text-sm text-rose-100">{error}</div> : null}
    </SettingsSection>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-white/10 bg-black/15 p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-1 text-xl font-semibold text-white">{value}</div>
    </div>
  );
}

