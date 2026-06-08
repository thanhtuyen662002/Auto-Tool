import type { ProjectConfig } from '../types/project';
import {
  createDefaultProjectConfig,
  DEFAULT_CACHE_SETTINGS,
  DEFAULT_CROP_SAFETY_SETTINGS,
  DEFAULT_INDUSTRY_SETTINGS,
  DEFAULT_MUSIC_SETTINGS,
  DEFAULT_PROJECT_ASSET_SETTINGS,
  DEFAULT_SOURCE_MEDIA_SETTINGS,
  DEFAULT_TTS_SETTINGS,
  DEFAULT_VISUAL_STYLE_SETTINGS,
} from '../config/defaults';

const CONFIG_PREFIX = 'auto-tool:project-config:';
const DIRTY_PREFIX = 'auto-tool:project-dirty:';

export function defaultProjectConfig(): ProjectConfig {
  return createDefaultProjectConfig();
}

export function saveProjectConfig(projectId: string, config: ProjectConfig, dirty = false): void {
  localStorage.setItem(`${CONFIG_PREFIX}${projectId}`, JSON.stringify(config));
  localStorage.setItem(`${DIRTY_PREFIX}${projectId}`, dirty ? '1' : '0');
}

export function loadProjectConfig(projectId: string): ProjectConfig | null {
  const raw = localStorage.getItem(`${CONFIG_PREFIX}${projectId}`);
  if (!raw) return null;
  try {
    const config = JSON.parse(raw) as ProjectConfig;
    return {
      ...config,
      product: {
        ...config.product,
        specs: config.product.specs ?? [],
        validation_warnings: config.product.validation_warnings ?? [],
        hashtag_suggestions: config.product.hashtag_suggestions ?? [],
      },
      ai: {
        ...config.ai,
        gemini_api_keys: config.ai.gemini_api_keys ?? [],
      },
      music: config.music ? { ...DEFAULT_MUSIC_SETTINGS, ...config.music } : { ...DEFAULT_MUSIC_SETTINGS },
      timeline: config.timeline ?? { template_id: 'ugc_reviewer_natural' },
      script_variation: config.script_variation ?? { mode: 'auto_mix', preferred_variant_ids: [] },
      tts: config.tts ? { ...DEFAULT_TTS_SETTINGS, ...config.tts } : { ...DEFAULT_TTS_SETTINGS },
      visual_style: config.visual_style
        ? { ...DEFAULT_VISUAL_STYLE_SETTINGS, ...config.visual_style }
        : { ...DEFAULT_VISUAL_STYLE_SETTINGS },
      industry: config.industry ? { ...DEFAULT_INDUSTRY_SETTINGS, ...config.industry } : { ...DEFAULT_INDUSTRY_SETTINGS },
      crop_safety: config.crop_safety
        ? { ...DEFAULT_CROP_SAFETY_SETTINGS, ...config.crop_safety }
        : { ...DEFAULT_CROP_SAFETY_SETTINGS },
      cache: config.cache ? { ...DEFAULT_CACHE_SETTINGS, ...config.cache } : { ...DEFAULT_CACHE_SETTINGS },
      source_media: config.source_media
        ? { ...DEFAULT_SOURCE_MEDIA_SETTINGS, ...config.source_media }
        : { ...DEFAULT_SOURCE_MEDIA_SETTINGS },
      assets: config.assets ? { ...DEFAULT_PROJECT_ASSET_SETTINGS, ...config.assets } : { ...DEFAULT_PROJECT_ASSET_SETTINGS },
    };
  } catch {
    return null;
  }
}

export function isProjectDirty(projectId: string): boolean {
  return localStorage.getItem(`${DIRTY_PREFIX}${projectId}`) === '1';
}

export function setProjectDirty(projectId: string, dirty: boolean): void {
  localStorage.setItem(`${DIRTY_PREFIX}${projectId}`, dirty ? '1' : '0');
}

export function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function maskSensitiveConfig(config: ProjectConfig): ProjectConfig {
  return {
    ...config,
    ai: {
      ...config.ai,
      gemini_api_keys: (config.ai.gemini_api_keys ?? []).map((key) => maskApiKey(key)),
    },
    tts: config.tts
      ? {
          ...config.tts,
          api_key: config.tts.api_key ? maskApiKey(config.tts.api_key) : config.tts.api_key,
          access_token: config.tts.access_token ? maskApiKey(config.tts.access_token) : config.tts.access_token,
        }
      : config.tts,
  };
}

function maskApiKey(key: string): string {
  const trimmed = key.trim();
  if (!trimmed) return '';
  if (trimmed.length <= 8) return '********';
  return `${trimmed.slice(0, 4)}...${trimmed.slice(-4)}`;
}
