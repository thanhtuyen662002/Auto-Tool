import { Clapperboard, FolderOpen } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import ResultsEmptyState from '../components/results/ResultsEmptyState';
import ResultsLayout from '../components/results/ResultsLayout';
import WorkflowStepper from '../components/workflow/WorkflowStepper';

export default function ResultsPage() {
  return (
    <ResultsLayout
      title="Kết quả"
      subtitle="Mở một job cụ thể để xem gallery, kiểm tra video cuối và gói xuất bản."
      actions={
        <>
          <LinkButton to="/douyin-reup" label="Video có thoại" icon={<Clapperboard size={16} />} />
          <LinkButton to="/silent-mode" label="Video không thoại" icon={<FolderOpen size={16} />} />
        </>
      }
      summary={
        <WorkflowStepper
          steps={[
            { label: 'Source', status: 'done' },
            { label: 'Preset', status: 'done' },
            { label: 'Processing', status: 'pending' },
            { label: 'Review', status: 'pending' },
            { label: 'Render', status: 'pending' },
            { label: 'Export', status: 'pending' },
          ]}
        />
      }
    >
      <ResultsEmptyState
        title="Chưa chọn job kết quả"
        message="Mở kết quả từ một batch đã xử lý. Nếu chưa có batch, hãy bắt đầu từ Video có thoại hoặc Video không thoại."
      />
    </ResultsLayout>
  );
}

function LinkButton({ to, label, icon }: { to: string; label: string; icon: ReactNode }) {
  return (
    <Link
      className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-white/15 bg-white/8 px-4 py-2 text-sm font-semibold text-white transition hover:border-cyan-300/45 hover:bg-white/12"
      to={to}
    >
      {icon}
      {label}
    </Link>
  );
}
