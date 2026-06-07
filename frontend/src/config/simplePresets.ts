import type { EffectSettings } from '../types/project';

export const OUTPUT_COUNT_OPTIONS = [
  { id: '1', label: '1 video', value: 1 },
  { id: '3', label: '3 video', value: 3 },
  { id: '5', label: '5 video', value: 5 },
  { id: '10', label: '10 video', value: 10 },
  { id: 'custom', label: 'Tùy chỉnh', value: null },
];

export const DURATION_OPTIONS = [
  { id: '8', label: '8s', value: 8 },
  { id: '12', label: '12s', value: 12 },
  { id: '15', label: '15s', value: 15 },
  { id: '20', label: '20s', value: 20 },
];

export const VIDEO_STYLE_OPTIONS = [
  {
    id: 'ugc_reviewer_natural',
    label: 'Review tự nhiên',
    summaryLabel: 'Review tự nhiên',
    templateId: 'ugc_reviewer_natural',
    visualStylePresetId: 'clean_review_light',
  },
  {
    id: 'product_showcase_clean',
    label: 'Showcase sản phẩm sạch đẹp',
    summaryLabel: 'Showcase sạch đẹp',
    templateId: 'product_showcase_clean',
    visualStylePresetId: 'transparent_caption_box',
  },
  {
    id: 'fast_tiktok_recut',
    label: 'Cắt nhanh kiểu TikTok',
    summaryLabel: 'Cắt nhanh TikTok',
    templateId: 'fast_tiktok_recut',
    visualStylePresetId: 'sale_bold_red',
  },
  {
    id: 'problem_solution',
    label: 'Vấn đề -> Giải pháp',
    summaryLabel: 'Vấn đề -> Giải pháp',
    templateId: 'problem_solution',
    visualStylePresetId: 'clean_review_light',
  },
];

export const EDIT_STRENGTH_OPTIONS: Array<{
  id: string;
  label: string;
  summaryLabel: string;
  effects: EffectSettings;
}> = [
  {
    id: 'light',
    label: 'Nhẹ',
    summaryLabel: 'Nhẹ',
    effects: {
      cut_intensity: 35,
      speed_variation: 15,
      grain: 5,
      zoom_motion: 10,
      overlay_height: 20,
      subtitle_size: 52,
    },
  },
  {
    id: 'balanced',
    label: 'Vừa',
    summaryLabel: 'Vừa',
    effects: {
      cut_intensity: 65,
      speed_variation: 30,
      grain: 12,
      zoom_motion: 20,
      overlay_height: 22,
      subtitle_size: 54,
    },
  },
  {
    id: 'strong',
    label: 'Mạnh',
    summaryLabel: 'Mạnh',
    effects: {
      cut_intensity: 85,
      speed_variation: 55,
      grain: 18,
      zoom_motion: 35,
      overlay_height: 24,
      subtitle_size: 56,
    },
  },
];

export const VOICE_OPTIONS = [
  {
    id: 'female_south_vi',
    label: 'Nữ miền Việt Nam - tự nhiên',
    summaryLabel: 'Nữ miền Việt Nam - tự nhiên',
    provider: 'edge_tts',
    voice: 'vi-VN-HoaiMyNeural',
    language: 'vi',
  },
  {
    id: 'male_south_vi',
    label: 'Nam miền Việt Nam - tự nhiên',
    summaryLabel: 'Nam miền Việt Nam - tự nhiên',
    provider: 'edge_tts',
    voice: 'vi-VN-NamMinhNeural',
    language: 'vi',
  },
];

export function effectsMatch(a: EffectSettings, b: EffectSettings): boolean {
  return (
    a.cut_intensity === b.cut_intensity &&
    a.speed_variation === b.speed_variation &&
    a.grain === b.grain &&
    a.zoom_motion === b.zoom_motion &&
    a.overlay_height === b.overlay_height &&
    a.subtitle_size === b.subtitle_size
  );
}
