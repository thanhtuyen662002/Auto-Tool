import type { EffectSettings } from '../types/project';
import SliderInput from './SliderInput';

interface EffectSlidersProps {
  effects: EffectSettings;
  onChange: (effects: EffectSettings) => void;
}

export default function EffectSliders({ effects, onChange }: EffectSlidersProps) {
  const update = (key: keyof EffectSettings, value: number) => onChange({ ...effects, [key]: value });

  return (
    <div className="grid gap-3">
      <SliderInput
        label="Mức độ cắt cảnh"
        value={effects.cut_intensity}
        onChange={(value) => update('cut_intensity', value)}
      />
      <SliderInput
        label="Biến thiên tốc độ"
        value={effects.speed_variation}
        onChange={(value) => update('speed_variation', value)}
      />
      <SliderInput label="Hạt phim" value={effects.grain} onChange={(value) => update('grain', value)} />
      <SliderInput
        label="Chuyển động zoom"
        value={effects.zoom_motion}
        onChange={(value) => update('zoom_motion', value)}
      />
      <SliderInput
        label="Chiều cao lớp phủ"
        value={effects.overlay_height}
        onChange={(value) => update('overlay_height', value)}
      />
      <SliderInput
        label="Cỡ chữ phụ đề"
        value={effects.subtitle_size}
        min={16}
        max={120}
        onChange={(value) => update('subtitle_size', value)}
      />
    </div>
  );
}
