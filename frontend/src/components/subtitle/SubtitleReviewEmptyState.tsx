import { Captions, Waves } from 'lucide-react';
import { Link } from 'react-router-dom';
import GlassEmptyState from '../glass/GlassEmptyState';

export default function SubtitleReviewEmptyState() { return <GlassEmptyState title="Chưa có phụ đề cần review" message="Chạy Douyin Reup hoặc Silent Mode để tạo review document đầu tiên." action={<div className="flex flex-wrap justify-center gap-2"><Link className="inline-flex min-h-10 items-center gap-2 rounded-md border border-cyan-300/50 bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950" to="/douyin-reup"><Captions size={16} /> Mở Douyin Reup</Link><Link className="inline-flex min-h-10 items-center gap-2 rounded-md border border-white/15 bg-white/8 px-4 py-2 text-sm font-semibold text-white" to="/silent-mode"><Waves size={16} /> Mở Silent Mode</Link></div>} />; }
