import { backendUrl } from '../services/api';

export type GlassIntensity = 'soft' | 'medium' | 'strong';
export type MotionPreference = 'normal' | 'reduce';
export type LayoutDensity = 'comfortable' | 'compact';
export type DefaultWorkflow = 'douyin' | 'silent' | 'subtitle';
export type ThemeMode = 'dark' | 'light' | 'custom';
export type BackgroundImageMode = 'none' | 'local' | 'url';

export type LocalUiSettings = {
  themeMode: ThemeMode;
  glassIntensity: GlassIntensity;
  reduceMotion: boolean;
  layoutDensity: LayoutDensity;
  customBackgroundColor: string;
  customTextColor: string;
  customMutedTextColor: string;
  customCardColor: string;
  customCardSoftColor: string;
  customBorderColor: string;
  customAccentColor: string;
  backgroundImageMode: BackgroundImageMode;
  backgroundImageSource: string;
  backgroundImageEnabled: boolean;
  backgroundImageOpacity: number;
  backgroundImageBlur: number;
  backgroundImageOverlayOpacity: number;
  defaultWorkflow: DefaultWorkflow;
  defaultOutputFolder: string;
  defaultMusicFolder: string;
  defaultSourceFolder: string;
  debugUi: boolean;
  showRawJson: boolean;
  pollingInterval: number;
  onboardingSeen: boolean;
};

const DEFAULTS: LocalUiSettings = {
  themeMode: 'dark',
  glassIntensity: 'medium',
  reduceMotion: false,
  layoutDensity: 'comfortable',
  customBackgroundColor: '#070A13',
  customTextColor: '#F8FAFC',
  customMutedTextColor: '#AAB3C5',
  customCardColor: '#0F172A',
  customCardSoftColor: '#111827',
  customBorderColor: '#334155',
  customAccentColor: '#22D3EE',
  backgroundImageMode: 'none',
  backgroundImageSource: '',
  backgroundImageEnabled: false,
  backgroundImageOpacity: 0.22,
  backgroundImageBlur: 0,
  backgroundImageOverlayOpacity: 0.38,
  defaultWorkflow: 'douyin',
  defaultOutputFolder: './examples/outputs',
  defaultMusicFolder: '',
  defaultSourceFolder: '',
  debugUi: false,
  showRawJson: false,
  pollingInterval: 3,
  onboardingSeen: false,
};

const KEYS = {
  themeMode: 'auto-tool.ui.themeMode',
  glassIntensity: 'auto-tool.ui.glassIntensity',
  reduceMotion: 'auto-tool.ui.reduceMotion',
  layoutDensity: 'auto-tool.ui.layoutDensity',
  customBackgroundColor: 'auto-tool.ui.customBackgroundColor',
  customTextColor: 'auto-tool.ui.customTextColor',
  customMutedTextColor: 'auto-tool.ui.customMutedTextColor',
  customCardColor: 'auto-tool.ui.customCardColor',
  customCardSoftColor: 'auto-tool.ui.customCardSoftColor',
  customBorderColor: 'auto-tool.ui.customBorderColor',
  customAccentColor: 'auto-tool.ui.customAccentColor',
  backgroundImageMode: 'auto-tool.ui.backgroundImageMode',
  backgroundImageSource: 'auto-tool.ui.backgroundImageSource',
  backgroundImageEnabled: 'auto-tool.ui.backgroundImageEnabled',
  backgroundImageOpacity: 'auto-tool.ui.backgroundImageOpacity',
  backgroundImageBlur: 'auto-tool.ui.backgroundImageBlur',
  backgroundImageOverlayOpacity: 'auto-tool.ui.backgroundImageOverlayOpacity',
  defaultWorkflow: 'auto-tool.ui.defaultWorkflow',
  defaultOutputFolder: 'auto-tool.default-output-folder',
  defaultMusicFolder: 'auto-tool.default-bgm-folder',
  defaultSourceFolder: 'auto-tool.default-source-folder',
  debugUi: 'auto-tool.ui.debugUi',
  showRawJson: 'auto-tool.ui.showRawJson',
  pollingInterval: 'auto-tool.ui.pollingInterval',
  onboardingSeen: 'auto-tool.onboardingSeen',
};

export const recentFolderKeys = {
  source: 'auto-tool.recentSourceFolders',
  output: 'auto-tool.recentOutputFolders',
  music: 'auto-tool.recentMusicFolders',
} as const;

function readString(key: string, fallback: string): string {
  try {
    return localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

function readBoolean(key: string, fallback: boolean): boolean {
  const value = readString(key, fallback ? 'true' : 'false');
  return value === 'true';
}

function readNumber(key: string, fallback: number): number {
  const value = Number(readString(key, String(fallback)));
  return Number.isFinite(value) ? value : fallback;
}

export function getLocalUiSettings(): LocalUiSettings {
  return {
    themeMode: normalizeThemeMode(readString(KEYS.themeMode, DEFAULTS.themeMode)),
    glassIntensity: normalizeGlass(readString(KEYS.glassIntensity, DEFAULTS.glassIntensity)),
    reduceMotion: readBoolean(KEYS.reduceMotion, DEFAULTS.reduceMotion),
    layoutDensity: normalizeDensity(readString(KEYS.layoutDensity, DEFAULTS.layoutDensity)),
    customBackgroundColor: normalizeHexColor(readString(KEYS.customBackgroundColor, DEFAULTS.customBackgroundColor), DEFAULTS.customBackgroundColor),
    customTextColor: normalizeHexColor(readString(KEYS.customTextColor, DEFAULTS.customTextColor), DEFAULTS.customTextColor),
    customMutedTextColor: normalizeHexColor(readString(KEYS.customMutedTextColor, DEFAULTS.customMutedTextColor), DEFAULTS.customMutedTextColor),
    customCardColor: normalizeHexColor(readString(KEYS.customCardColor, DEFAULTS.customCardColor), DEFAULTS.customCardColor),
    customCardSoftColor: normalizeHexColor(readString(KEYS.customCardSoftColor, DEFAULTS.customCardSoftColor), DEFAULTS.customCardSoftColor),
    customBorderColor: normalizeHexColor(readString(KEYS.customBorderColor, DEFAULTS.customBorderColor), DEFAULTS.customBorderColor),
    customAccentColor: normalizeHexColor(readString(KEYS.customAccentColor, DEFAULTS.customAccentColor), DEFAULTS.customAccentColor),
    backgroundImageMode: normalizeBackgroundImageMode(readString(KEYS.backgroundImageMode, DEFAULTS.backgroundImageMode)),
    backgroundImageSource: readString(KEYS.backgroundImageSource, DEFAULTS.backgroundImageSource),
    backgroundImageEnabled: readBoolean(KEYS.backgroundImageEnabled, DEFAULTS.backgroundImageEnabled),
    backgroundImageOpacity: clampNumber(readNumber(KEYS.backgroundImageOpacity, DEFAULTS.backgroundImageOpacity), 0, 0.8),
    backgroundImageBlur: clampNumber(readNumber(KEYS.backgroundImageBlur, DEFAULTS.backgroundImageBlur), 0, 24),
    backgroundImageOverlayOpacity: clampNumber(readNumber(KEYS.backgroundImageOverlayOpacity, DEFAULTS.backgroundImageOverlayOpacity), 0, 0.9),
    defaultWorkflow: normalizeWorkflow(readString(KEYS.defaultWorkflow, DEFAULTS.defaultWorkflow)),
    defaultOutputFolder: readString(KEYS.defaultOutputFolder, DEFAULTS.defaultOutputFolder),
    defaultMusicFolder: readString(KEYS.defaultMusicFolder, DEFAULTS.defaultMusicFolder),
    defaultSourceFolder: readString(KEYS.defaultSourceFolder, DEFAULTS.defaultSourceFolder),
    debugUi: readBoolean(KEYS.debugUi, DEFAULTS.debugUi),
    showRawJson: readBoolean(KEYS.showRawJson, DEFAULTS.showRawJson),
    pollingInterval: Math.max(1, readNumber(KEYS.pollingInterval, DEFAULTS.pollingInterval)),
    onboardingSeen: readBoolean(KEYS.onboardingSeen, DEFAULTS.onboardingSeen),
  };
}

export function saveLocalUiSettings(settings: Partial<LocalUiSettings>) {
  Object.entries(settings).forEach(([key, value]) => {
    const storageKey = KEYS[key as keyof LocalUiSettings];
    if (!storageKey || value === undefined) return;
    localStorage.setItem(storageKey, String(value));
  });
  applyAppearanceSettings(getLocalUiSettings());
}

export function markOnboardingSeen() {
  saveLocalUiSettings({ onboardingSeen: true });
}

export function resetLocalUiSettings() {
  Object.values(KEYS).forEach((key) => localStorage.removeItem(key));
  Object.values(recentFolderKeys).forEach((key) => localStorage.removeItem(key));
  applyAppearanceSettings(DEFAULTS);
}

export function readRecentFolders(key: string): string[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || '[]') as unknown;
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string').slice(0, 8) : [];
  } catch {
    return [];
  }
}

export function clearRecentFolders() {
  Object.values(recentFolderKeys).forEach((key) => localStorage.removeItem(key));
}

export function applyAppearanceSettings(settings = getLocalUiSettings()) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  root.classList.remove(
    'theme-dark',
    'theme-light',
    'theme-custom',
    'glass-soft',
    'glass-medium',
    'glass-strong',
    'reduce-motion',
    'density-comfortable',
    'density-compact',
  );
  root.classList.add(`theme-${settings.themeMode}`);
  root.classList.add(`glass-${settings.glassIntensity}`);
  root.classList.add(`density-${settings.layoutDensity}`);
  if (settings.reduceMotion) root.classList.add('reduce-motion');
  root.style.colorScheme = settings.themeMode === 'light' ? 'light' : 'dark';
  applyThemeVariables(root, settings);
}

function applyThemeVariables(root: HTMLElement, settings: LocalUiSettings) {
  const customVariableNames = [
    '--studio-bg',
    '--studio-panel',
    '--studio-panel-soft',
    '--studio-panel-strong',
    '--studio-border',
    '--studio-border-strong',
    '--studio-text',
    '--studio-muted',
    '--studio-cyan',
    '--studio-input-bg',
    '--studio-input-text',
    '--studio-input-placeholder',
    '--studio-select-bg',
    '--studio-shadow',
    '--studio-accent-bg',
    '--studio-accent-soft',
    '--studio-accent-text',
    '--studio-accent-foreground',
    '--studio-background-gradient',
  ];

  customVariableNames.forEach((name) => root.style.removeProperty(name));

  if (settings.themeMode === 'custom') {
    const bg = settings.customBackgroundColor;
    const panel = settings.customCardColor;
    const panelSoft = settings.customCardSoftColor;
    const border = settings.customBorderColor;
    const text = settings.customTextColor;
    const muted = settings.customMutedTextColor;
    const accent = settings.customAccentColor;
    root.style.setProperty('--studio-bg', bg);
    root.style.setProperty('--studio-panel', rgbaFromHex(panel, 0.82));
    root.style.setProperty('--studio-panel-soft', rgbaFromHex(panelSoft, 0.58));
    root.style.setProperty('--studio-panel-strong', rgbaFromHex(panel, 0.94));
    root.style.setProperty('--studio-border', rgbaFromHex(border, 0.5));
    root.style.setProperty('--studio-border-strong', rgbaFromHex(accent, 0.45));
    root.style.setProperty('--studio-text', text);
    root.style.setProperty('--studio-muted', muted);
    root.style.setProperty('--studio-cyan', accent);
    root.style.setProperty('--studio-input-bg', rgbaFromHex(panel, 0.86));
    root.style.setProperty('--studio-input-text', text);
    root.style.setProperty('--studio-input-placeholder', rgbaFromHex(muted, 0.7));
    root.style.setProperty('--studio-select-bg', panel);
    root.style.setProperty('--studio-shadow', `0 22px 64px ${rgbaFromHex(bg, 0.32)}`);
    root.style.setProperty('--studio-accent-bg', accent);
    root.style.setProperty('--studio-accent-soft', rgbaFromHex(accent, 0.12));
    root.style.setProperty('--studio-accent-text', accent);
    root.style.setProperty('--studio-accent-foreground', readableTextOnHex(accent));
    root.style.setProperty(
      '--studio-background-gradient',
      `radial-gradient(circle at 12% 10%, ${rgbaFromHex(accent, 0.14)}, transparent 32%), linear-gradient(145deg, ${bg} 0%, ${mixHex(bg, panelSoft, 0.32)} 52%, ${mixHex(bg, accent, 0.18)} 100%)`,
    );
  }

  const backgroundSource = settings.backgroundImageSource.trim();
  const hasBackgroundImage = settings.backgroundImageEnabled && settings.backgroundImageMode !== 'none' && backgroundSource.length > 0;
  root.style.setProperty('--studio-bg-image', hasBackgroundImage ? `url("${escapeCssUrl(resolveBackgroundImageUrl(settings))}")` : 'none');
  root.style.setProperty('--studio-bg-image-opacity', hasBackgroundImage ? String(settings.backgroundImageOpacity) : '0');
  root.style.setProperty('--studio-bg-image-blur', `${settings.backgroundImageBlur}px`);
  root.style.setProperty(
    '--studio-bg-image-overlay',
    hasBackgroundImage ? rgbaFromHex(backgroundOverlayColor(settings), settings.backgroundImageOverlayOpacity) : 'rgba(0, 0, 0, 0)',
  );
}

export function resolveBackgroundImageUrl(settings: LocalUiSettings): string {
  const source = settings.backgroundImageSource.trim();
  if (!source) return '';
  if (/^data:image\//i.test(source)) return source;
  if (/^https?:\/\//i.test(source)) return backendUrl(`/api/files/remote-image?url=${encodeURIComponent(source)}`);
  if (source.startsWith('/api/')) return backendUrl(source);
  return backendUrl(`/api/files/image?path=${encodeURIComponent(source)}`);
}

function normalizeGlass(value: string): GlassIntensity {
  return value === 'soft' || value === 'strong' ? value : 'medium';
}

function normalizeThemeMode(value: string): ThemeMode {
  if (value === 'light' || value === 'custom') return value;
  return 'dark';
}

function normalizeBackgroundImageMode(value: string): BackgroundImageMode {
  if (value === 'local' || value === 'url') return value;
  return 'none';
}

function normalizeDensity(value: string): LayoutDensity {
  return value === 'compact' ? 'compact' : 'comfortable';
}

function normalizeWorkflow(value: string): DefaultWorkflow {
  if (value === 'silent' || value === 'subtitle') return value;
  return 'douyin';
}

function normalizeHexColor(value: string, fallback: string): string {
  const trimmed = value.trim();
  if (/^#[0-9a-fA-F]{6}$/.test(trimmed)) return trimmed.toUpperCase();
  if (/^#[0-9a-fA-F]{3}$/.test(trimmed)) {
    const [, r, g, b] = trimmed;
    return `#${r}${r}${g}${g}${b}${b}`.toUpperCase();
  }
  return fallback;
}

function clampNumber(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function rgbaFromHex(hex: string, alpha: number): string {
  const { r, g, b } = hexToRgb(normalizeHexColor(hex, '#000000'));
  return `rgba(${r}, ${g}, ${b}, ${clampNumber(alpha, 0, 1).toFixed(3)})`;
}

function mixHex(from: string, to: string, amount: number): string {
  const a = hexToRgb(normalizeHexColor(from, '#000000'));
  const b = hexToRgb(normalizeHexColor(to, '#FFFFFF'));
  const mix = clampNumber(amount, 0, 1);
  const r = Math.round(a.r + (b.r - a.r) * mix);
  const g = Math.round(a.g + (b.g - a.g) * mix);
  const blue = Math.round(a.b + (b.b - a.b) * mix);
  return `#${[r, g, blue].map((value) => value.toString(16).padStart(2, '0')).join('')}`;
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const normalized = normalizeHexColor(hex, '#000000').slice(1);
  return {
    r: Number.parseInt(normalized.slice(0, 2), 16),
    g: Number.parseInt(normalized.slice(2, 4), 16),
    b: Number.parseInt(normalized.slice(4, 6), 16),
  };
}

function backgroundOverlayColor(settings: LocalUiSettings): string {
  if (settings.themeMode === 'light') return '#FFFFFF';
  if (settings.themeMode === 'custom') return settings.customBackgroundColor;
  return '#070A13';
}

function readableTextOnHex(hex: string): string {
  const { r, g, b } = hexToRgb(normalizeHexColor(hex, '#22D3EE'));
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.62 ? '#071018' : '#FFFFFF';
}

function escapeCssUrl(value: string): string {
  return value.replace(/\\/g, '/').replace(/"/g, '\\"');
}
