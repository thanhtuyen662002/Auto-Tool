import { FolderSearch } from 'lucide-react';

export default function SourceMediaEmptyState({ message }: { message: string }) {
  return (
    <div className="grid min-h-44 place-items-center rounded-md border border-dashed border-white/15 bg-white/5 p-6 text-center">
      <div>
        <FolderSearch className="mx-auto text-slate-400" size={28} />
        <p className="mt-3 text-sm text-slate-300">{message}</p>
      </div>
    </div>
  );
}
