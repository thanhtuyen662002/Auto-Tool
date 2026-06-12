import type { ComponentProps } from 'react';
import PresetCard from './PresetCard';

export default function PresetGrid({ presets }: { presets: Array<ComponentProps<typeof PresetCard>> }) {
  return <div className="grid gap-3 md:grid-cols-2">{presets.map((preset) => <PresetCard key={preset.id} {...preset} />)}</div>;
}
