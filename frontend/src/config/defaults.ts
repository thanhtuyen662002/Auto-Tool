import type {
  EffectSettings,
  IndustrySettings,
  MusicSettings,
  ProjectConfig,
  RenderSettings,
  TTSSettings,
  VisualStyleSettings,
  CropSafetySettings,
  CacheSettings,
  SourceMediaSettings,
} from '../types/project';

export const DEFAULT_RENDER_SETTINGS: RenderSettings = {
  output_count: 3,
  duration: 12,
  aspect_ratio: '9:16',
  resolution: '1080x1920',
  fps: 30,
};

export const DEFAULT_EFFECT_SETTINGS: EffectSettings = {
  cut_intensity: 70,
  speed_variation: 30,
  grain: 15,
  zoom_motion: 25,
  overlay_height: 33,
  subtitle_size: 84,
};

export const DEFAULT_MUSIC_SETTINGS: MusicSettings = {
  enabled: true,
  source_folder: 'examples/music',
  source_file: null,
  volume: 0.12,
  fade_in: 0.5,
  fade_out: 0.8,
  duck_under_voice: false,
};

export const DEFAULT_TTS_SETTINGS: TTSSettings = {
  provider: 'edge_tts',
  fallback_provider: 'piper',
  voice: 'vi-VN-HoaiMyNeural',
  language: 'vi',
  api_key: '',
  credentials_json_path: '',
  access_token: '',
  rate: '+0%',
  pitch: '+0Hz',
  volume: '+0%',
  output_format: 'mp3',
};

export const DEFAULT_VISUAL_STYLE_SETTINGS: VisualStyleSettings = {
  preset_id: 'clean_review_light',
  custom_overrides: null,
};

export const DEFAULT_INDUSTRY_SETTINGS: IndustrySettings = {
  preset_id: 'general_product',
};

export const DEFAULT_CROP_SAFETY_SETTINGS: CropSafetySettings = {
  enabled: true,
  mode: 'auto_safe',
  allow_blur_background: true,
  reduce_zoom_on_risk: true,
  reduce_overlay_on_risk: true,
};

export const DEFAULT_CACHE_SETTINGS: CacheSettings = {
  enabled: true,
  cache_media_metadata: true,
  cache_segment_scoring: true,
  cache_crop_safety: true,
  cache_tts: true,
  cache_overlay_assets: true,
  clear_cache_before_render: false,
};

export const DEFAULT_SOURCE_MEDIA_SETTINGS: SourceMediaSettings = {
  respect_user_exclusions: true,
  prefer_favorite_segments: true,
  allow_excluded_fallback: false,
};

export function createDefaultProjectConfig(): ProjectConfig {
  return {
    project_name: 'kaw-xmax10',
    source_folder: 'examples/sample_videos/kaw_xmax10',
    output_folder: 'examples/outputs',
    product: {
      name: 'M\u00e1y Chi\u1ebfu 4K Android KAW XMAX10',
      brand: 'KAW',
      description:
        'M\u00e1y chi\u1ebfu gi\u1ea3i tr\u00ed gia \u0111\u00ecnh nh\u1ecf g\u1ecdn, h\u1ed7 tr\u1ee3 4K, Android 9.0.',
      features: [
        'H\u1ed7 tr\u1ee3 4K',
        'Android 9.0',
        'Thi\u1ebft k\u1ebf nh\u1ecf g\u1ecdn',
        'Ph\u00f9 h\u1ee3p ph\u00f2ng ng\u1ee7, ph\u00f2ng kh\u00e1ch, v\u0103n ph\u00f2ng',
      ],
      specs: [],
      cta: 'Xem chi ti\u1ebft s\u1ea3n ph\u1ea9m ngay',
      validation_warnings: [],
      hashtag_suggestions: [],
    },
    render: { ...DEFAULT_RENDER_SETTINGS },
    effects: { ...DEFAULT_EFFECT_SETTINGS },
    ai: {
      text_model: 'gemini-3.1-flash-lite',
      tone: 'friendly_reviewer',
      language: 'vi',
      gemini_api_keys: [],
    },
    music: { ...DEFAULT_MUSIC_SETTINGS },
    timeline: {
      template_id: 'ugc_reviewer_natural',
    },
    script_variation: {
      mode: 'auto_mix',
      preferred_variant_ids: ['reviewer_natural', 'benefit_first', 'use_case_scene'],
    },
    tts: { ...DEFAULT_TTS_SETTINGS },
    visual_style: { ...DEFAULT_VISUAL_STYLE_SETTINGS },
    industry: { ...DEFAULT_INDUSTRY_SETTINGS },
    crop_safety: { ...DEFAULT_CROP_SAFETY_SETTINGS },
    cache: { ...DEFAULT_CACHE_SETTINGS },
    source_media: { ...DEFAULT_SOURCE_MEDIA_SETTINGS },
  };
}
