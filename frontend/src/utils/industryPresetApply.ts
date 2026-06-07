import {
  EDIT_STRENGTH_OPTIONS,
  VIDEO_STYLE_OPTIONS,
  VOICE_OPTIONS,
} from '../config/simplePresets';
import { DEFAULT_TTS_SETTINGS, DEFAULT_VISUAL_STYLE_SETTINGS } from '../config/defaults';
import type { ApplyIndustryPresetOptions, IndustryPreset, ProjectConfig } from '../types/project';

export const DEFAULT_INDUSTRY_APPLY_OPTIONS: ApplyIndustryPresetOptions = {
  apply_visual_style: true,
  apply_timeline: true,
  apply_script_variation: true,
  apply_tts_voice: true,
  apply_edit_strength: true,
};

export function applyIndustryPresetToConfig(
  config: ProjectConfig,
  preset: IndustryPreset,
  options: ApplyIndustryPresetOptions = DEFAULT_INDUSTRY_APPLY_OPTIONS,
): ProjectConfig {
  const next: ProjectConfig = {
    ...config,
    industry: { preset_id: preset.id },
  };

  if (options.apply_timeline) {
    next.timeline = {
      ...(config.timeline ?? { template_id: 'ugc_reviewer_natural' }),
      template_id: preset.timeline_template_id,
    };
  }

  if (options.apply_visual_style) {
    next.visual_style = {
      ...(config.visual_style ?? DEFAULT_VISUAL_STYLE_SETTINGS),
      preset_id: preset.visual_style_preset_id,
      custom_overrides: null,
    };
  }

  if (options.apply_script_variation) {
    next.script_variation = {
      ...(config.script_variation ?? { mode: 'auto_mix' }),
      mode: preset.script_variation_mode,
      preferred_variant_ids: [...preset.preferred_script_variant_ids],
    };
  }

  if (options.apply_tts_voice) {
    const voiceOption = VOICE_OPTIONS.find((option) => option.voice === preset.default_tts_voice);
    next.tts = {
      ...(config.tts ?? DEFAULT_TTS_SETTINGS),
      provider: voiceOption?.provider ?? config.tts?.provider ?? DEFAULT_TTS_SETTINGS.provider,
      voice: preset.default_tts_voice,
      language: voiceOption?.language ?? config.tts?.language ?? DEFAULT_TTS_SETTINGS.language,
      output_format: config.tts?.output_format ?? DEFAULT_TTS_SETTINGS.output_format,
    };
  }

  if (options.apply_edit_strength) {
    const editOption = EDIT_STRENGTH_OPTIONS.find((option) => option.label === preset.default_edit_strength);
    if (editOption) {
      next.effects = { ...editOption.effects };
    }
  }

  return next;
}

export function videoStyleLabelForPreset(preset: IndustryPreset): string {
  return (
    VIDEO_STYLE_OPTIONS.find((option) => option.templateId === preset.timeline_template_id)?.label
    ?? preset.default_video_style
  );
}

