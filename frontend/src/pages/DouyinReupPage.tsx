import { useEffect, useMemo, useState } from 'react';
import {
  getDouyinReupJobResults,
  getJobStatus,
  getVisualStyles,
  scanDouyinReupFolder,
  startDouyinReupProcess,
  videoFileUrl,
} from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import PathInput from '../components/PathInput';
import SliderInput from '../components/SliderInput';
import type {
  DouyinOutputResult,
  DouyinReupSettings,
  DouyinVideoItem,
  JobStatus,
  VisualStylePreset,
} from '../types/project';

const DEFAULT_SETTINGS: DouyinReupSettings = {
  enabled: true,
  source_language: 'zh',
  target_language: 'vi',
  translation_provider: 'gemini',
  subtitle_source_priority: ['sidecar_srt', 'embedded_subtitle', 'asr'],
  use_sidecar_srt: true,
  use_embedded_subtitle: true,
  use_asr_if_no_subtitle: true,
  asr_provider: 'faster_whisper',
  asr_model_size: 'medium',
  asr_device: 'auto',
  asr_vad_filter: false,
  asr_subtitle_offset_seconds: -0.25,
  visual_style_preset_id: 'clean_review_light',
  burn_subtitle: true,
  add_overlay: true,
  music_folder: '',
  bgm_volume: 0.16,
  original_audio_volume: 0.85,
  duck_bgm_when_voice: false,
  resolution: '1080x1920',
  fps: 30,
  process_mode: 'all',
  max_videos: null,
  selected_video_paths: [],
  keep_temp: false,
};

export default function DouyinReupPage() {
  const [projectName, setProjectName] = useState('douyin-reup');
  const [sourceFolder, setSourceFolder] = useState('');
  const [outputFolder, setOutputFolder] = useState('./examples/outputs');
  const [settings, setSettings] = useState<DouyinReupSettings>(DEFAULT_SETTINGS);
  const [visualStyles, setVisualStyles] = useState<VisualStylePreset[]>([]);
  const [videos, setVideos] = useState<DouyinVideoItem[]>([]);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [scanSummary, setScanSummary] = useState<{ total: number; valid: number; invalid: number } | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [results, setResults] = useState<DouyinOutputResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const done = jobStatus?.status === 'completed' || jobStatus?.status === 'completed_with_errors' || jobStatus?.status === 'failed';
  const canStart = sourceFolder.trim() && outputFolder.trim() && !busy && (!jobStatus || done);
  const selectedSet = useMemo(() => new Set(selectedPaths), [selectedPaths]);

  useEffect(() => {
    getVisualStyles()
      .then((response) => setVisualStyles(response.presets))
      .catch(() => setVisualStyles([]));
  }, []);

  useEffect(() => {
    if (!jobId || done) return;
    const timer = window.setInterval(() => {
      getJobStatus(jobId)
        .then((status) => {
          setJobStatus(status);
          if (['completed', 'completed_with_errors', 'failed'].includes(status.status)) {
            void loadResults(jobId);
          }
        })
        .catch((err) => setError(err instanceof Error ? err.message : 'Không thể tải trạng thái job.'));
    }, 2000);
    return () => window.clearInterval(timer);
  }, [jobId, done]);

  async function handleScan() {
    setBusy(true);
    setError(null);
    setResults([]);
    try {
      const response = await scanDouyinReupFolder(sourceFolder);
      setVideos(response.media);
      setSelectedPaths([]);
      setScanSummary({
        total: response.total_files,
        valid: response.valid_videos,
        invalid: response.invalid_files,
      });
      if (response.errors.length) {
        setError(response.errors.slice(0, 3).join('\n'));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể scan thư mục Douyin.');
    } finally {
      setBusy(false);
    }
  }

  async function handleStart() {
    setBusy(true);
    setError(null);
    setResults([]);
    try {
      const processSettings: DouyinReupSettings = {
        ...settings,
        enabled: true,
        music_folder: settings.music_folder?.trim() || null,
        process_mode: selectedPaths.length ? 'selected' : settings.max_videos ? 'first_n' : 'all',
        selected_video_paths: selectedPaths,
      };
      const response = await startDouyinReupProcess({
        project_name: projectName.trim() || 'douyin-reup',
        source_folder: sourceFolder,
        output_folder: outputFolder,
        settings: processSettings,
      });
      setJobId(response.job_id);
      setJobStatus({
        job_id: response.job_id,
        status: response.status,
        current_step: 'queued',
        progress: 0,
        total_outputs: 0,
        completed_outputs: 0,
        failed_outputs: 0,
        logs: [],
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể bắt đầu xử lý Douyin Reup.');
    } finally {
      setBusy(false);
    }
  }

  async function loadResults(targetJobId: string) {
    try {
      const response = await getDouyinReupJobResults(targetJobId);
      setResults(response.outputs);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải kết quả Douyin Reup.');
    }
  }

  function toggleSelected(path: string) {
    setSelectedPaths((current) => (current.includes(path) ? current.filter((item) => item !== path) : [...current, path]));
  }

  function updateSettings(updates: Partial<DouyinReupSettings>) {
    setSettings((current) => ({ ...current, ...updates }));
  }

  return (
    <div className="mx-auto grid max-w-7xl gap-6 px-6 py-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Douyin Reup</h1>
          <p className="mt-1 text-sm text-muted">
            Xử lý video Douyin đã tải sẵn trong máy, dịch subtitle sang tiếng Việt và render lại với overlay/nhạc nền.
          </p>
        </div>
        {jobStatus ? (
          <div className="rounded-md border border-line bg-white px-4 py-3 text-sm">
            <div className="font-semibold text-ink">{jobStatus.progress}%</div>
            <div className="text-muted">{jobStatus.current_step}</div>
          </div>
        ) : null}
      </div>

      <ApiErrorBox error={error} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
        <section className="grid gap-4 rounded-md border border-line bg-white p-5">
          <h2 className="text-base font-semibold text-ink">Nguồn video</h2>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-ink">Tên project</span>
            <input
              className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-blue-100"
              lang="vi"
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
            />
          </label>
          <PathInput label="Thư mục video Douyin" value={sourceFolder} onChange={setSourceFolder} required />
          <PathInput label="Thư mục output" value={outputFolder} onChange={setOutputFolder} required />
          <PathInput label="Thư mục nhạc nền" value={settings.music_folder || ''} onChange={(value) => updateSettings({ music_folder: value })} />

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-ink">Ngôn ngữ nguồn</span>
              <input
                className="h-10 w-full rounded-md border border-line px-3 text-sm"
                value={settings.source_language}
                onChange={(event) => updateSettings({ source_language: event.target.value })}
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-ink">Ngôn ngữ đích</span>
              <input
                className="h-10 w-full rounded-md border border-line px-3 text-sm"
                value={settings.target_language}
                onChange={(event) => updateSettings({ target_language: event.target.value })}
              />
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-ink">Visual style</span>
              <select
                className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
                value={settings.visual_style_preset_id}
                onChange={(event) => updateSettings({ visual_style_preset_id: event.target.value })}
              >
                {visualStyles.map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {preset.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-ink">Giới hạn số video</span>
              <input
                className="h-10 w-full rounded-md border border-line px-3 text-sm"
                type="number"
                min={1}
                value={settings.max_videos ?? ''}
                onChange={(event) =>
                  updateSettings({ max_videos: event.target.value ? Number(event.target.value) : null })
                }
              />
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <SliderInput
              label="Âm lượng nhạc nền"
              min={0}
              max={1}
              step={0.01}
              value={settings.bgm_volume}
              onChange={(value) => updateSettings({ bgm_volume: value })}
            />
            <SliderInput
              label="Âm lượng audio gốc"
              min={0}
              max={1}
              step={0.01}
              value={settings.original_audio_volume}
              onChange={(value) => updateSettings({ original_audio_volume: value })}
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <SliderInput
              label="Dịch thời gian sub ASR"
              min={-1}
              max={1}
              step={0.05}
              value={settings.asr_subtitle_offset_seconds}
              onChange={(value) => updateSettings({ asr_subtitle_offset_seconds: value })}
            />
            <Toggle
              label="Bật VAD cho ASR"
              checked={settings.asr_vad_filter}
              onChange={(value) => updateSettings({ asr_vad_filter: value })}
            />
          </div>

          <div className="grid gap-2 text-sm text-ink sm:grid-cols-2">
            <Toggle label="Dùng file .srt đi kèm" checked={settings.use_sidecar_srt} onChange={(value) => updateSettings({ use_sidecar_srt: value })} />
            <Toggle label="Dùng subtitle nhúng" checked={settings.use_embedded_subtitle} onChange={(value) => updateSettings({ use_embedded_subtitle: value })} />
            <Toggle label="ASR nếu không có subtitle" checked={settings.use_asr_if_no_subtitle} onChange={(value) => updateSettings({ use_asr_if_no_subtitle: value })} />
            <Toggle label="Burn subtitle vào video" checked={settings.burn_subtitle} onChange={(value) => updateSettings({ burn_subtitle: value })} />
            <Toggle label="Dùng overlay" checked={settings.add_overlay} onChange={(value) => updateSettings({ add_overlay: value })} />
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand disabled:text-muted"
              type="button"
              disabled={!sourceFolder.trim() || busy}
              onClick={() => void handleScan()}
            >
              {busy ? 'Đang xử lý...' : 'Scan video'}
            </button>
            <button
              className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white disabled:bg-blue-200"
              type="button"
              disabled={!canStart}
              onClick={() => void handleStart()}
            >
              Bắt đầu Douyin Reup
            </button>
          </div>
        </section>

        <aside className="grid gap-4">
          <section className="rounded-md border border-line bg-white p-5">
            <h2 className="text-base font-semibold text-ink">Tiến trình</h2>
            {jobStatus ? (
              <div className="mt-4 grid gap-3">
                <div className="h-2 overflow-hidden rounded-full bg-surface">
                  <div className="h-full bg-brand" style={{ width: `${jobStatus.progress}%` }} />
                </div>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <Stat label="Hoàn thành" value={jobStatus.completed_outputs} />
                  <Stat label="Lỗi" value={jobStatus.failed_outputs} />
                  <Stat label="Tổng" value={jobStatus.total_outputs} />
                </div>
                <div className="max-h-64 overflow-auto rounded-md bg-surface p-3 text-xs text-muted">
                  {jobStatus.logs.length ? (
                    jobStatus.logs.map((log, index) => (
                      <div key={`${log.created_at}-${index}`} className="border-b border-line py-2 last:border-b-0">
                        <span className="font-semibold text-ink">{log.level.toUpperCase()}</span> {log.message}
                      </div>
                    ))
                  ) : (
                    <div>Chưa có log.</div>
                  )}
                </div>
              </div>
            ) : (
              <p className="mt-2 text-sm text-muted">Chưa có job nào đang chạy.</p>
            )}
          </section>

          <section className="rounded-md border border-line bg-white p-5">
            <h2 className="text-base font-semibold text-ink">Config JSON</h2>
            <pre className="mt-3 max-h-[420px] overflow-auto rounded-md bg-surface p-3 text-xs text-muted">
              {JSON.stringify({ project_name: projectName, source_folder: sourceFolder, output_folder: outputFolder, settings }, null, 2)}
            </pre>
          </section>
        </aside>
      </div>

      <section className="rounded-md border border-line bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-ink">Video đã scan</h2>
          {scanSummary ? (
            <div className="text-sm text-muted">
              Tổng {scanSummary.total} file, hợp lệ {scanSummary.valid}, lỗi {scanSummary.invalid}
            </div>
          ) : null}
        </div>
        <div className="mt-4 overflow-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-line text-xs uppercase text-muted">
              <tr>
                <th className="py-2 pr-3">Chọn</th>
                <th className="py-2 pr-3">File</th>
                <th className="py-2 pr-3">Duration</th>
                <th className="py-2 pr-3">Subtitle</th>
                <th className="py-2 pr-3">Cảnh báo</th>
              </tr>
            </thead>
            <tbody>
              {videos.map((video) => (
                <tr key={video.path} className="border-b border-line last:border-b-0">
                  <td className="py-3 pr-3">
                    <input
                      type="checkbox"
                      checked={selectedSet.has(video.path)}
                      onChange={() => toggleSelected(video.path)}
                    />
                  </td>
                  <td className="max-w-lg break-all py-3 pr-3">
                    <div className="font-medium text-ink">{video.filename}</div>
                    <div className="text-xs text-muted">{video.path}</div>
                  </td>
                  <td className="py-3 pr-3 text-muted">{video.duration.toFixed(1)}s</td>
                  <td className="py-3 pr-3 text-muted">
                    {video.sidecar_srt_path ? 'SRT đi kèm' : video.embedded_subtitle_found ? 'Nhúng' : 'Cần ASR'}
                  </td>
                  <td className="py-3 pr-3 text-muted">{video.warnings.join('; ') || '-'}</td>
                </tr>
              ))}
              {!videos.length ? (
                <tr>
                  <td className="py-6 text-sm text-muted" colSpan={5}>
                    Chưa scan video.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      {results.length ? (
        <section className="rounded-md border border-line bg-white p-5">
          <h2 className="text-base font-semibold text-ink">Kết quả</h2>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {results.map((output) => (
              <article key={output.index} className="rounded-md border border-line p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-semibold text-ink">Video {output.index.toString().padStart(3, '0')}</div>
                  <span className={output.status === 'success' ? 'text-sm font-semibold text-green-700' : 'text-sm font-semibold text-red-700'}>
                    {output.status}
                  </span>
                </div>
                {output.path ? (
                  <video className="mt-3 aspect-[9/16] max-h-[520px] w-full rounded-md bg-black object-contain" src={videoFileUrl(output.path)} controls />
                ) : null}
                <div className="mt-3 grid gap-1 break-all text-xs text-muted">
                  <div>Output: {output.path || '-'}</div>
                  <div>Subtitle: {output.translated_srt_file || '-'}</div>
                  <div>Nhạc nền: {output.bgm_file || '-'}</div>
                  <div>Log: {output.log_file || '-'}</div>
                </div>
                {output.warnings.length ? <div className="mt-3 text-xs text-amber-700">{output.warnings.join('; ')}</div> : null}
                {output.errors.length ? <div className="mt-3 text-xs text-red-700">{output.errors.join('; ')}</div> : null}
                {output.path ? (
                  <button
                    className="mt-3 rounded-md border border-line px-3 py-2 text-xs font-semibold text-ink hover:border-brand"
                    type="button"
                    onClick={() => void navigator.clipboard.writeText(output.path)}
                  >
                    Copy path
                  </button>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-2">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-surface p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="text-lg font-semibold text-ink">{value}</div>
    </div>
  );
}
