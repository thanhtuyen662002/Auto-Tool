import { USER_FACING_TERMS, type UserFacingTermKey } from '../../utils/userFacingTerms';

const DEFAULT_TERMS: UserFacingTermKey[] = ['ocr', 'asr', 'tts', 'vad', 'ffmpeg', 'provider', 'fps', 'confidence', 'fallback', 'batch'];

export default function TerminologyGlossary({ terms = DEFAULT_TERMS }: { terms?: UserFacingTermKey[] }) {
  return (
    <details className="rounded-md border border-cyan-300/20 bg-cyan-300/10 p-3 text-sm text-slate-200">
      <summary className="cursor-pointer select-none font-semibold text-cyan-100">Bảng giải thích thuật ngữ dễ hiểu</summary>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {terms.map((key) => {
          const term = USER_FACING_TERMS[key];
          return (
            <div className="rounded-md border border-white/10 bg-slate-950/55 p-3" key={key}>
              <div className="font-semibold text-white">
                {term.label}
                {term.technical ? <span className="ml-1 text-xs font-medium text-slate-400">({term.technical})</span> : null}
              </div>
              <p className="mt-1 text-xs leading-5 text-slate-400">{term.description}</p>
            </div>
          );
        })}
      </div>
    </details>
  );
}
