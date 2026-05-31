import { useEffect, useMemo } from 'react';
import type { ProductVideoScript, SubtitleLine, VoiceoverLine } from '../../types/project';
import TextArea from '../TextArea';
import TextInput from '../TextInput';

interface ScriptEditorFormProps {
  script: ProductVideoScript;
  targetDuration?: number;
  onChange: (script: ProductVideoScript) => void;
  onValidationChange?: (valid: boolean, errors: string[]) => void;
}

export default function ScriptEditorForm({
  script,
  targetDuration,
  onChange,
  onValidationChange,
}: ScriptEditorFormProps) {
  const hashtagsText = script.hashtags.join(' ');
  const errors = useMemo(() => validateScript(script, targetDuration), [script, targetDuration]);

  useEffect(() => {
    onValidationChange?.(errors.length === 0, errors);
  }, [errors, onValidationChange]);

  function patch(patchValue: Partial<ProductVideoScript>) {
    onChange({ ...script, ...patchValue });
  }

  function updateVoiceover(index: number, patchValue: Partial<VoiceoverLine>) {
    patch({
      voiceover: script.voiceover.map((line, lineIndex) =>
        lineIndex === index ? { ...line, ...patchValue } : line,
      ),
    });
  }

  function updateSubtitle(index: number, patchValue: Partial<SubtitleLine>) {
    patch({
      subtitles: script.subtitles.map((line, lineIndex) =>
        lineIndex === index ? { ...line, ...patchValue } : line,
      ),
    });
  }

  return (
    <div className="space-y-5">
      {errors.length ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <div className="font-semibold">Cần sửa kịch bản</div>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <TextInput label="Câu mở đầu" value={script.hook} onChange={(hook) => patch({ hook })} required />

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-ink">Dòng giọng đọc</h3>
          <button
            className="rounded-md border border-line bg-white px-3 py-1 text-xs font-semibold text-ink hover:border-brand"
            type="button"
            onClick={() => patch({ voiceover: [...script.voiceover, { time_hint: '', text: '' }] })}
          >
                + Thêm dòng giọng đọc
          </button>
        </div>
        <div className="space-y-3">
          {script.voiceover.map((line, index) => (
            <div key={index} className="grid gap-2 rounded-md bg-surface p-3 md:grid-cols-[140px_1fr_auto] md:items-start">
              <input
                className="h-10 rounded-md border border-line bg-white px-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-blue-100"
                value={line.time_hint}
                placeholder="0-3s"
                onChange={(event) => updateVoiceover(index, { time_hint: event.target.value })}
              />
              <input
                className="h-10 rounded-md border border-line bg-white px-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-blue-100"
                value={line.text}
                lang="vi"
                spellCheck
                    placeholder="Nội dung giọng đọc"
                onChange={(event) => updateVoiceover(index, { text: event.target.value })}
              />
              <button
                className="h-10 rounded-md border border-red-200 bg-white px-3 text-xs font-semibold text-red-700 hover:border-red-400"
                type="button"
                disabled={script.voiceover.length <= 1}
                onClick={() => patch({ voiceover: script.voiceover.filter((_, lineIndex) => lineIndex !== index) })}
              >
                Xoá
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-ink">Dòng phụ đề</h3>
          <button
            className="rounded-md border border-line bg-white px-3 py-1 text-xs font-semibold text-ink hover:border-brand"
            type="button"
            onClick={() => patch({ subtitles: [...script.subtitles, { start_hint: null, end_hint: null, text: '' }] })}
          >
                + Thêm dòng phụ đề
          </button>
        </div>
        <div className="space-y-3">
          {script.subtitles.map((line, index) => (
            <div key={index} className="grid gap-2 rounded-md bg-surface p-3 md:grid-cols-[95px_95px_1fr_auto] md:items-start">
              <input
                className="h-10 rounded-md border border-line bg-white px-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-blue-100"
                type="number"
                min={0}
                step={0.1}
                value={line.start_hint ?? ''}
                placeholder="Bắt đầu"
                onChange={(event) => updateSubtitle(index, { start_hint: parseOptionalNumber(event.target.value) })}
              />
              <input
                className="h-10 rounded-md border border-line bg-white px-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-blue-100"
                type="number"
                min={0}
                step={0.1}
                value={line.end_hint ?? ''}
                placeholder="Kết thúc"
                onChange={(event) => updateSubtitle(index, { end_hint: parseOptionalNumber(event.target.value) })}
              />
              <input
                className="h-10 rounded-md border border-line bg-white px-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-blue-100"
                value={line.text}
                lang="vi"
                spellCheck
                    placeholder="Nội dung phụ đề"
                onChange={(event) => updateSubtitle(index, { text: event.target.value })}
              />
              <button
                className="h-10 rounded-md border border-red-200 bg-white px-3 text-xs font-semibold text-red-700 hover:border-red-400"
                type="button"
                disabled={script.subtitles.length <= 1}
                onClick={() => patch({ subtitles: script.subtitles.filter((_, lineIndex) => lineIndex !== index) })}
              >
                Xoá
              </button>
            </div>
          ))}
        </div>
      </section>

      <TextInput label="Lời kêu gọi hành động" value={script.cta} onChange={(cta) => patch({ cta })} required />
      <TextArea label="Mô tả đăng kèm" rows={3} value={script.caption} onChange={(caption) => patch({ caption })} />
      <TextInput
        label="Hashtag"
        value={hashtagsText}
        onChange={(value) => patch({ hashtags: parseHashtags(value) })}
        placeholder="#review #sanpham #muasam"
      />
    </div>
  );
}

function validateScript(script: ProductVideoScript, targetDuration?: number): string[] {
  const errors: string[] = [];
  if (!script.hook.trim()) errors.push('Câu mở đầu không được rỗng.');
  if (!script.cta.trim()) errors.push('Lời kêu gọi hành động không được rỗng.');
  if (!script.voiceover.length) errors.push('Giọng đọc phải có ít nhất 1 dòng.');
  if (!script.subtitles.length) errors.push('Phụ đề phải có ít nhất 1 dòng.');

  script.voiceover.forEach((line, index) => {
    if (!line.text.trim()) errors.push(`Giọng đọc dòng ${index + 1} chưa có nội dung.`);
  });

  script.subtitles.forEach((line, index) => {
    const start = line.start_hint;
    const end = line.end_hint;
    if (!line.text.trim()) errors.push(`Phụ đề dòng ${index + 1} chưa có nội dung.`);
    if (start === null || start === undefined || Number.isNaN(start)) {
      errors.push(`Phụ đề dòng ${index + 1} thiếu thời điểm bắt đầu.`);
    }
    if (end === null || end === undefined || Number.isNaN(end)) {
      errors.push(`Phụ đề dòng ${index + 1} thiếu thời điểm kết thúc.`);
    }
    if (typeof start === 'number' && typeof end === 'number') {
    if (start < 0 || end < 0) errors.push(`Phụ đề dòng ${index + 1} không được âm.`);
    if (end < start) errors.push(`Phụ đề dòng ${index + 1} có thời điểm kết thúc nhỏ hơn bắt đầu.`);
      if (targetDuration && end > targetDuration) {
      errors.push(`Phụ đề dòng ${index + 1} vượt quá ${targetDuration}s.`);
      }
    }
  });

  return errors;
}

function parseOptionalNumber(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseHashtags(value: string): string[] {
  return value
    .split(/[\s,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}
