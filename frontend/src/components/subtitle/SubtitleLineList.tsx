import { Search, SlidersHorizontal } from 'lucide-react';
import type { SubtitleReviewLine, SubtitleReviewStatus } from '../../types/project';
import GlassEmptyState from '../glass/GlassEmptyState';
import SubtitleLineCard from './SubtitleLineCard';
import type { SubtitleLineFilter, SubtitleLineSort } from './subtitleUi';

interface Props {
  lines: SubtitleReviewLine[]; activeIndex: number | null; unsaved: Set<number>; sourceType?: string | null; busy: boolean;
  search: string; filter: SubtitleLineFilter; sort: SubtitleLineSort;
  onSearch: (value: string) => void; onFilter: (value: SubtitleLineFilter) => void; onSort: (value: SubtitleLineSort) => void;
  onSelect: (line: SubtitleReviewLine) => void; onChange: (lineIndex: number, text: string) => void; onStatusChange: (lineIndex: number, status: SubtitleReviewStatus) => void; onSave: (lineIndex: number) => void; onSuggestRewrite: (lineIndex: number) => void; onUseTranslated: (lineIndex: number) => void;
}

const filters: Array<{ value: SubtitleLineFilter; label: string }> = [{ value: 'all', label: 'Tất cả' }, { value: 'needs_review', label: 'Cần kiểm tra' }, { value: 'critical', label: 'Lỗi nặng' }, { value: 'edited', label: 'Đã sửa' }, { value: 'unedited', label: 'Chưa sửa' }, { value: 'ocr', label: 'OCR' }, { value: 'asr', label: 'ASR' }, { value: 'visual', label: 'Từ cảnh' }];

export default function SubtitleLineList(props: Props) {
  return <div className="grid min-w-0 gap-3"><div className="grid gap-3"><label className="relative block"><Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={17} /><input className="h-10 w-full rounded-md border border-white/12 bg-slate-950/85 pl-10 pr-3 text-sm" placeholder="Tìm trong phụ đề..." value={props.search} onChange={(event) => props.onSearch(event.target.value)} /></label><div className="flex flex-wrap items-center gap-2">{filters.map((item) => <button key={item.value} className={`rounded-md border px-2.5 py-1.5 text-xs font-semibold ${props.filter === item.value ? 'border-cyan-300/45 bg-cyan-300/12 text-cyan-100' : 'border-white/10 bg-white/5 text-slate-400 hover:text-white'}`} type="button" onClick={() => props.onFilter(item.value)}>{item.label}</button>)}<label className="ml-auto flex items-center gap-2 text-xs text-slate-400"><SlidersHorizontal size={15} /><select className="h-8 rounded-md border border-white/12 bg-slate-950/85 px-2 text-xs" value={props.sort} onChange={(event) => props.onSort(event.target.value as SubtitleLineSort)}><option value="timeline">Theo thời gian</option><option value="quality">Chất lượng thấp trước</option><option value="edited">Đã sửa trước</option><option value="critical">Lỗi nặng trước</option></select></label></div></div>{props.lines.length ? <div className="grid max-h-[calc(100vh-250px)] min-h-[420px] gap-3 overflow-y-auto overflow-x-hidden pr-1">{props.lines.map((line) => <SubtitleLineCard key={line.index} line={line} active={props.activeIndex === line.index} unsaved={props.unsaved.has(line.index)} sourceType={sourceForLine(line, props.sourceType)} busy={props.busy} onSelect={props.onSelect} onChange={props.onChange} onStatusChange={props.onStatusChange} onSave={props.onSave} onSuggestRewrite={props.onSuggestRewrite} onUseTranslated={props.onUseTranslated} />)}</div> : <GlassEmptyState title="Không có dòng phù hợp" message="Thử đổi bộ lọc hoặc từ khóa tìm kiếm." />}</div>;
}
function sourceForLine(line: SubtitleReviewLine, fallback?: string | null) { const note = `${line.user_note || ''} ${line.warnings.join(' ')}`.toLowerCase(); if (note.includes('visual')) return 'visual_generated'; if (note.includes('ocr')) return 'ocr_hardsub'; if (note.includes('asr')) return 'asr'; return fallback; }
