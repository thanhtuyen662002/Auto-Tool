import { useId, useState } from 'react';
import { browsePath } from '../api/client';
import type { BrowsePathMode } from '../types/project';
import NotifyOnChange from './notifications/NotifyOnChange';

interface PathInputProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  modes?: BrowsePathMode[];
  fileExtensions?: string[];
  disabled?: boolean;
}

export default function PathInput({
  label,
  value,
  onChange,
  placeholder,
  required,
  modes = ['folder'],
  fileExtensions = [],
  disabled,
}: PathInputProps) {
  const inputId = useId();
  const [busyMode, setBusyMode] = useState<BrowsePathMode | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleBrowse(mode: BrowsePathMode) {
    setBusyMode(mode);
    setError(null);
    try {
      const response = await browsePath({
        mode,
        title: mode === 'folder' ? `Chọn thư mục cho ${label}` : `Chọn file cho ${label}`,
        initial_path: value || null,
        extensions: mode === 'file' ? fileExtensions : [],
      });
      if (!response.cancelled && response.path) {
        onChange(response.path);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể mở hộp thoại chọn đường dẫn.');
    } finally {
      setBusyMode(null);
    }
  }

  return (
    <div className="block">
      <label className="mb-1 block text-sm font-medium text-ink" htmlFor={inputId}>
        {label}
      </label>
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
        <input
          id={inputId}
          className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-blue-100"
          type="text"
          lang="vi"
          spellCheck={false}
          value={value}
          placeholder={placeholder}
          required={required}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          {modes.map((mode) => (
            <button
              key={mode}
              className="h-10 rounded-md border border-line bg-white px-3 text-xs font-semibold text-ink hover:border-brand disabled:text-muted"
              type="button"
              disabled={disabled || busyMode !== null}
              onClick={() => void handleBrowse(mode)}
            >
              {busyMode === mode ? 'Đang mở...' : mode === 'folder' ? 'Chọn thư mục' : 'Chọn file'}
            </button>
          ))}
        </div>
      </div>
      <NotifyOnChange value={error} variant="error" />
      {error ? <span className="mt-1 block text-xs text-red-600">{error}</span> : null}
    </div>
  );
}
