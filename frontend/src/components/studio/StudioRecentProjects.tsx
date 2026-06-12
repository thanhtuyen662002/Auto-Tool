import { ArrowRight, FolderOpen } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { ProjectListItem } from '../../types/project';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';
import GlassEmptyState from '../glass/GlassEmptyState';

export default function StudioRecentProjects({ projects }: { projects: ProjectListItem[] }) {
  return (
    <GlassCard strong className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold text-white">Tiếp tục công việc gần đây</h2>
          <p className="mt-1 text-sm text-slate-400">Mở lại project hoặc bắt đầu batch mới nếu chưa có dữ liệu.</p>
        </div>
        <Link to="/douyin-reup">
          <GlassButton variant="secondary" className="min-h-9 px-3 text-xs">Tạo batch mới</GlassButton>
        </Link>
      </div>

      {projects.length ? (
        <div className="mt-4 grid gap-2">
          {projects.map((project) => (
            <Link
              key={project.id}
              to={`/settings/${project.id}`}
              className="flex items-center gap-3 rounded-md border border-white/10 bg-black/15 p-3 transition hover:border-cyan-300/30 hover:bg-white/6"
            >
              <FolderOpen size={17} className="text-cyan-200" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold text-white">{project.project_name}</div>
                <div className="mt-0.5 text-xs text-slate-500">{new Date(project.created_at).toLocaleString('vi-VN')}</div>
              </div>
              <ArrowRight size={15} className="text-slate-500" />
            </Link>
          ))}
        </div>
      ) : (
        <div className="mt-4">
          <GlassEmptyState
            title="Chưa có project gần đây"
            message="Hãy chạy Video có thoại hoặc Video không thoại để tạo project và kết quả đầu tiên."
            action={
              <Link to="/douyin-reup">
                <GlassButton variant="primary">Tạo batch đầu tiên</GlassButton>
              </Link>
            }
          />
        </div>
      )}
    </GlassCard>
  );
}
