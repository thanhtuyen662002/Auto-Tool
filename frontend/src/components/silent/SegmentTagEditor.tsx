import { useEffect, useMemo, useState } from 'react';
import type { SilentVisualSegment, SilentVisualTagVocabulary } from '../../types/project';

type Props = {
  segment: SilentVisualSegment;
  vocabulary: SilentVisualTagVocabulary;
  disabled?: boolean;
  onSave: (payload: {
    tags: string[];
    primary_industry: string | null;
    primary_scene: string | null;
    primary_action: string | null;
  }) => Promise<void>;
  onRegenerate: () => Promise<void>;
};

export default function SegmentTagEditor({ segment, vocabulary, disabled, onSave, onRegenerate }: Props) {
  const [primaryIndustry, setPrimaryIndustry] = useState(segment.primary_industry ?? 'general_product');
  const [primaryScene, setPrimaryScene] = useState(segment.primary_scene ?? '');
  const [primaryAction, setPrimaryAction] = useState(segment.primary_action ?? '');
  const [tags, setTags] = useState<string[]>(segment.visual_tags.map((tag) => tag.tag));

  useEffect(() => {
    setPrimaryIndustry(segment.primary_industry ?? 'general_product');
    setPrimaryScene(segment.primary_scene ?? '');
    setPrimaryAction(segment.primary_action ?? '');
    setTags(segment.visual_tags.map((tag) => tag.tag));
  }, [segment]);

  const groups = useMemo(
    () => [
      { label: 'Industry', values: vocabulary.industry },
      { label: 'Scene', values: vocabulary.scene },
      { label: 'Action', values: vocabulary.action },
      { label: 'Product stage', values: vocabulary.product_stage },
      { label: 'Quality', values: vocabulary.quality },
    ],
    [vocabulary],
  );

  function toggleTag(tag: string) {
    setTags((current) => current.includes(tag) ? current.filter((item) => item !== tag) : [...current, tag]);
  }

  async function save() {
    const required = [primaryIndustry, primaryScene, primaryAction].filter(Boolean);
    await onSave({
      tags: Array.from(new Set([...tags, ...required])),
      primary_industry: primaryIndustry || null,
      primary_scene: primaryScene || null,
      primary_action: primaryAction || null,
    });
  }

  return (
    <div className="grid gap-3 border-t border-line pt-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <TagSelect label="Primary industry" value={primaryIndustry} options={vocabulary.industry} onChange={setPrimaryIndustry} />
        <TagSelect label="Primary scene" value={primaryScene} options={vocabulary.scene} onChange={setPrimaryScene} allowEmpty />
        <TagSelect label="Primary action" value={primaryAction} options={vocabulary.action} onChange={setPrimaryAction} allowEmpty />
      </div>
      <div className="grid gap-3">
        {groups.map((group) => (
          <fieldset key={group.label}>
            <legend className="mb-1 text-xs font-semibold text-muted">{group.label}</legend>
            <div className="flex flex-wrap gap-x-4 gap-y-2">
              {group.values.map((tag) => (
                <label key={tag} className="flex items-center gap-1.5 text-xs text-ink">
                  <input type="checkbox" checked={tags.includes(tag)} onChange={() => toggleTag(tag)} />
                  {formatTag(tag)}
                </label>
              ))}
            </div>
          </fieldset>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="rounded-md bg-brand px-3 py-2 text-xs font-semibold text-white disabled:opacity-50" type="button" disabled={disabled} onClick={() => void save()}>
          Save tags
        </button>
        <button className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink disabled:opacity-50" type="button" disabled={disabled} onClick={() => void onRegenerate()}>
          Regenerate caption
        </button>
      </div>
    </div>
  );
}

function TagSelect({ label, value, options, onChange, allowEmpty = false }: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
  allowEmpty?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold text-muted">{label}</span>
      <select className="h-9 w-full rounded-md border border-line bg-white px-2 text-xs" value={value} onChange={(event) => onChange(event.target.value)}>
        {allowEmpty ? <option value="">None</option> : null}
        {options.map((option) => <option key={option} value={option}>{formatTag(option)}</option>)}
      </select>
    </label>
  );
}

function formatTag(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}
