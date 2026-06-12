export type GlassIntensity = 'soft' | 'medium' | 'strong';
export type MotionPreference = 'normal' | 'reduce';
export type LayoutDensity = 'comfortable' | 'compact';
export type DefaultWorkflow = 'douyin' | 'silent' | 'subtitle';

export type LocalUiSettings = {
  glassIntensity: GlassIntensity;
  reduceMotion: boolean;
  layoutDensity: LayoutDensity;
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
  glassIntensity: 'medium',
  reduceMotion: false,
  layoutDensity: 'comfortable',
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
  glassIntensity: 'auto-tool.ui.glassIntensity',
  reduceMotion: 'auto-tool.ui.reduceMotion',
  layoutDensity: 'auto-tool.ui.layoutDensity',
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
    glassIntensity: normalizeGlass(readString(KEYS.glassIntensity, DEFAULTS.glassIntensity)),
    reduceMotion: readBoolean(KEYS.reduceMotion, DEFAULTS.reduceMotion),
    layoutDensity: normalizeDensity(readString(KEYS.layoutDensity, DEFAULTS.layoutDensity)),
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
  root.classList.remove('glass-soft', 'glass-medium', 'glass-strong', 'reduce-motion', 'density-comfortable', 'density-compact');
  root.classList.add(`glass-${settings.glassIntensity}`);
  root.classList.add(`density-${settings.layoutDensity}`);
  if (settings.reduceMotion) root.classList.add('reduce-motion');
}

function normalizeGlass(value: string): GlassIntensity {
  return value === 'soft' || value === 'strong' ? value : 'medium';
}

function normalizeDensity(value: string): LayoutDensity {
  return value === 'compact' ? 'compact' : 'comfortable';
}

function normalizeWorkflow(value: string): DefaultWorkflow {
  if (value === 'silent' || value === 'subtitle') return value;
  return 'douyin';
}
