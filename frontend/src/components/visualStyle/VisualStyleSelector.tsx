import { useState } from 'react';
import { assetFileUrl, previewVisualStyle } from '../../api/client';
import type { VisualStylePreset } from '../../types/project';

interface VisualStyleSelectorProps {
  presets: VisualStylePreset[];
  selectedPresetId: string;
  resolution: string;
  sampleText?: string;
  onSelect: (presetId: string) => void;
}

export default function VisualStyleSelector({
  presets,
  selectedPresetId,
  resolution,
  sampleText = 'Nhỏ gọn, dễ dùng, phù hợp mỗi ngày',
  onSelect,
}: VisualStyleSelectorProps) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const [previewingId, setPreviewingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handlePreview(presetId: string) {
    setPreviewingId(presetId);
    setError(null);
    try {
      const response = await previewVisualStyle(presetId, sampleText, resolution);
      setPreviewPath(response.preview_image_path);
      setPreviewUrl(assetFileUrl(response.preview_image_url || response.preview_image_path));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo ảnh preview style.');
    } finally {
      setPreviewingId(null);
    }
  }

  if (!presets.length) {
    return (
      <div className="rounded-md border border-line bg-surface p-4 text-sm text-muted">
        Chưa tải được danh sách style overlay/subtitle.
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      <div className="grid gap-3 md:grid-cols-2">
        {presets.map((preset) => {
          const selected = preset.id === selectedPresetId;
          return (
            <article
              key={preset.id}
              className={`rounded-md border p-4 ${
                selected ? 'border-brand bg-blue-50' : 'border-line bg-white'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-ink">{preset.name}</h3>
                  <p className="mt-1 text-xs leading-relaxed text-muted">{preset.description}</p>
                </div>
                <span className="rounded bg-surface px-2 py-1 text-xs font-semibold text-muted">
                  {preset.category}
                </span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  className={`rounded-md px-3 py-2 text-xs font-semibold ${
                    selected
                      ? 'bg-brand text-white'
                      : 'border border-line bg-white text-ink hover:border-brand'
                  }`}
                  type="button"
                  onClick={() => onSelect(preset.id)}
                >
                  {selected ? 'Đang chọn' : 'Chọn style'}
                </button>
                <button
                  className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand"
                  type="button"
                  disabled={previewingId === preset.id}
                  onClick={() => handlePreview(preset.id)}
                >
                  {previewingId === preset.id ? 'Đang tạo...' : 'Preview'}
                </button>
              </div>
            </article>
          );
        })}
      </div>

      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

      {previewUrl ? (
        <div className="grid gap-3 rounded-md bg-surface p-3">
          <div className="text-sm font-semibold text-ink">Preview style</div>
          <img
            className="max-h-[520px] w-full rounded-md border border-line bg-white object-contain"
            src={previewUrl}
            alt="Visual style preview"
          />
          {previewPath ? <div className="break-all text-xs text-muted">{previewPath}</div> : null}
        </div>
      ) : null}
    </div>
  );
}
