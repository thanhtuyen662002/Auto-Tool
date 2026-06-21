import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  CheckCircle2,
  ClipboardList,
  Copy,
  Download,
  ExternalLink,
  FolderOpen,
  History,
  PauseCircle,
  PlayCircle,
  RefreshCw,
  Search,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import {
  browsePath,
  checkDouyinDownloaderLogin,
  closeDouyinDownloaderBrowser,
  getDouyinDownloaderHistory,
  getDouyinDownloaderJob,
  getDouyinDownloaderStatus,
  openDouyinDownloaderBrowser,
  pauseDouyinDownloaderJob,
  resumeDouyinDownloaderJob,
  startDouyinDownloaderDownload,
  startDouyinDownloaderScan,
} from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import GlassButton from '../components/glass/GlassButton';
import GlassCard from '../components/glass/GlassCard';
import { addRecentSourceFolder, getLocalAppConfig, openFolder } from '../services/localAppApi';
import type {
  DouyinDownloaderHistoryResponse,
  DouyinDownloaderJobResponse,
  DouyinDownloaderStatusResponse,
} from '../types/project';

const DEFAULT_DOUYIN_URL = 'https://www.douyin.com/';
const DEFAULT_DOWNLOAD_FOLDER = './examples/sample_videos/douyin_downloads';

export default function DouyinDownloadPage() {
  const [status, setStatus] = useState<DouyinDownloaderStatusResponse | null>(null);
  const [history, setHistory] = useState<DouyinDownloaderHistoryResponse | null>(null);
  const [job, setJob] = useState<DouyinDownloaderJobResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [channelUrl, setChannelUrl] = useState(DEFAULT_DOUYIN_URL);
  const [outputFolder, setOutputFolder] = useState(DEFAULT_DOWNLOAD_FOLDER);
  const [maxScrolls, setMaxScrolls] = useState(5000);
  const [scanUntilEnd, setScanUntilEnd] = useState(true);
  const [skipExisting, setSkipExisting] = useState(true);
  const [manualLinks, setManualLinks] = useState('');
  const [selectedLinks, setSelectedLinks] = useState<string[]>([]);

  const activeJob = job && (job.status === 'queued' || job.status === 'running') ? job : null;
  const scannedLinks = job?.links ?? [];
  const linkLines = useMemo(() => parseLinks(manualLinks), [manualLinks]);
  const usableLinks = selectedLinks.length ? selectedLinks : linkLines;
  const recentJobs = history?.recent_jobs?.slice(0, 5) ?? [];
  const recentChannels = history?.recent_channel_urls?.slice(0, 5) ?? [];
  const recentFolders = history?.recent_output_folders?.slice(0, 5) ?? [];
  const cachedChannelDownload = useMemo(() => {
    if (!history?.channel_downloads || !channelUrl.trim()) return null;
    const normalized = normalizeDouyinLink(channelUrl);
    return history.channel_downloads[normalized] ?? history.channel_downloads[normalized.replace(/\/$/, '')] ?? null;
  }, [history, channelUrl]);
  const cachedLinks = useMemo(() => {
    if (cachedChannelDownload?.links?.length) return cachedChannelDownload.links;
    if (!history?.scanned_channels || !channelUrl.trim()) return [];
    const normalized = normalizeDouyinLink(channelUrl);
    return history.scanned_channels[normalized] ?? history.scanned_channels[normalized.replace(/\/$/, '')] ?? [];
  }, [history, channelUrl]);

  useEffect(() => {
    void refreshStatus();
    void refreshHistory();
    getLocalAppConfig()
      .then((config) => {
        if (config.default_source_folder) setOutputFolder(config.default_source_folder);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!activeJob) return undefined;
    const timer = window.setInterval(() => {
      void refreshJob(activeJob.job_id);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activeJob?.job_id]);

  useEffect(() => {
    if (!job || job.status !== 'completed') return;
    if (job.job_type === 'scan') {
      setSelectedLinks(job.links);
      setManualLinks(job.links.join('\n'));
      void refreshHistory();
    }
    if (job.job_type === 'download') {
      void refreshHistory();
    }
  }, [job?.job_id, job?.status]);

  async function refreshStatus() {
    try {
      setStatus(await getDouyinDownloaderStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể lấy trạng thái trình duyệt Douyin.');
    }
  }

  async function refreshHistory() {
    try {
      const next = await getDouyinDownloaderHistory();
      setHistory(next);
      if (channelUrl === DEFAULT_DOUYIN_URL && next.recent_channel_urls.length) {
        setChannelUrl(next.recent_channel_urls[0]);
      }
      if (outputFolder === DEFAULT_DOWNLOAD_FOLDER && next.recent_output_folders.length) {
        setOutputFolder(next.recent_output_folders[0]);
      }
    } catch {
      setHistory(null);
    }
  }

  async function refreshJob(jobId: string) {
    try {
      const next = await getDouyinDownloaderJob(jobId);
      setJob(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể cập nhật tiến trình tác vụ Douyin.');
    }
  }

  async function runAction(name: string, action: () => Promise<void>) {
    setBusy(name);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thao tác Douyin thất bại.');
    } finally {
      setBusy(null);
    }
  }

  async function handleOpenBrowser() {
    await runAction('open-browser', async () => {
      const next = await openDouyinDownloaderBrowser({ start_url: channelUrl || DEFAULT_DOUYIN_URL });
      setStatus(next);
      setNotice('Chrome Douyin đã mở. Nếu đây là lần đầu, hãy đăng nhập trong cửa sổ Chrome rồi bấm Kiểm tra đăng nhập.');
    });
  }

  async function handleCheckLogin() {
    await runAction('check-login', async () => {
      const next = await checkDouyinDownloaderLogin();
      setStatus(next);
      setNotice(next.logged_in ? 'Đã phát hiện phiên đăng nhập Douyin.' : 'Chưa phát hiện đăng nhập. Hãy đăng nhập trong cửa sổ Chrome Douyin.');
    });
  }

  async function handleCloseBrowser() {
    await runAction('close-browser', async () => {
      const response = await closeDouyinDownloaderBrowser();
      setNotice(response.message);
      await refreshStatus();
    });
  }

  async function handleBrowseFolder() {
    await runAction('browse-folder', async () => {
      const response = await browsePath({
        mode: 'folder',
        title: 'Chọn thư mục lưu video Douyin',
        initial_path: outputFolder || null,
        extensions: [],
      });
      if (!response.cancelled && response.path) setOutputFolder(response.path);
    });
  }

  async function handleOpenFolder() {
    await runAction('open-folder', async () => {
      if (!outputFolder.trim()) throw new Error('Chưa chọn thư mục lưu video.');
      await openFolder(outputFolder);
    });
  }

  async function handleScan() {
    await runAction('scan', async () => {
      if (!channelUrl.trim()) throw new Error('Chưa nhập đường dẫn kênh hoặc trang Douyin.');
      const next = await startDouyinDownloaderScan({
        channel_url: channelUrl.trim(),
        max_scrolls: maxScrolls,
        scan_until_end: scanUntilEnd,
      });
      setJob(next);
      setNotice('Đã bắt đầu quét đường dẫn Douyin.');
      await refreshHistory();
    });
  }

  async function handleDownload() {
    await startDownload(usableLinks, outputFolder, skipExisting);
  }

  async function handleContinueCachedDownload() {
    const folder = cachedChannelDownload?.output_folder || outputFolder;
    if (folder) setOutputFolder(folder);
    if (cachedLinks.length) {
      setManualLinks(cachedLinks.join('\n'));
      setSelectedLinks(cachedLinks);
    }
    await startDownload(cachedLinks, folder, true);
  }

  async function startDownload(links: string[], folder: string, shouldSkipExisting: boolean) {
    const usableLinks = links;
    const outputFolder = folder;
    const skipExisting = shouldSkipExisting;
    await runAction('download', async () => {
      if (!outputFolder.trim()) throw new Error('Chưa chọn thư mục lưu video.');
      if (!usableLinks.length) throw new Error('Chưa có đường dẫn Douyin nào để tải.');
      const next = await startDouyinDownloaderDownload({
        links: usableLinks,
        output_folder: outputFolder.trim(),
        skip_existing: skipExisting,
        channel_url: channelUrl.trim() || null,
      });
      setJob(next);
      await addRecentSourceFolder(outputFolder.trim()).catch(() => undefined);
      await refreshHistory();
      setNotice('Đã bắt đầu tải video Douyin.');
    });
  }

  async function handlePauseJob() {
    if (!job) return;
    await runAction('pause-job', async () => {
      const response = await pauseDouyinDownloaderJob(job.job_id);
      setJob(response.job);
      setNotice(response.message);
    });
  }

  async function handleResumeJob(targetJob = job) {
    if (!targetJob) return;
    await runAction(`resume-${targetJob.job_id}`, async () => {
      const response = await resumeDouyinDownloaderJob(targetJob.job_id);
      setJob(response.job);
      setNotice(response.message);
      await refreshHistory();
    });
  }

  function useHistoryJob(targetJob: DouyinDownloaderJobResponse) {
    setJob(targetJob);
    if (targetJob.output_folder) setOutputFolder(targetJob.output_folder);
    if (targetJob.links.length) {
      setManualLinks(targetJob.links.join('\n'));
      setSelectedLinks(targetJob.links);
    }
    setNotice('Đã nạp lại tác vụ từ lịch sử.');
  }

  function toggleLink(link: string) {
    setSelectedLinks((current) => (current.includes(link) ? current.filter((item) => item !== link) : [...current, link]));
  }

  function selectAllLinks() {
    setSelectedLinks(scannedLinks.length ? scannedLinks : linkLines);
  }

  function clearSelectedLinks() {
    setSelectedLinks([]);
  }

  function useCachedScannedLinks() {
    if (!cachedLinks.length) return;
    if (cachedChannelDownload?.output_folder) setOutputFolder(cachedChannelDownload.output_folder);
    setManualLinks(cachedLinks.join('\n'));
    setSelectedLinks(cachedLinks);
    setNotice(`Đã nạp ${cachedLinks.length} link đã quét trước đó cho kênh này.`);
  }

  async function copyText(value: string) {
    await navigator.clipboard?.writeText(value);
    setNotice('Đã sao chép.');
  }

  return (
    <main className="mx-auto grid w-full max-w-[1600px] gap-5 px-4 py-5 lg:px-6">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(280px,0.45fr)]">
        <GlassCard strong className="min-w-0 p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">Nguồn Douyin</p>
              <h1 className="mt-2 text-2xl font-semibold text-white">Tải video Douyin</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
                Mở Chrome riêng, đăng nhập một lần, quét đường dẫn video và tải về thư mục nguồn để dựng lại.
              </p>
            </div>
            <StatusBadge status={status} />
          </div>

          <div className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <GlassButton className="whitespace-nowrap px-3 text-xs xl:text-sm" variant="primary" loading={busy === 'open-browser'} onClick={() => void handleOpenBrowser()}>
              <ExternalLink size={15} /> Mở Chrome
            </GlassButton>
            <GlassButton className="whitespace-nowrap px-3 text-xs xl:text-sm" loading={busy === 'check-login'} onClick={() => void handleCheckLogin()}>
              <ShieldCheck size={15} /> Kiểm tra đăng nhập
            </GlassButton>
            <GlassButton className="whitespace-nowrap px-3 text-xs xl:text-sm" loading={busy === 'close-browser'} onClick={() => void handleCloseBrowser()}>
              <XCircle size={15} /> Đóng Chrome
            </GlassButton>
            <GlassButton className="whitespace-nowrap px-3 text-xs xl:text-sm" loading={busy === 'refresh-status'} onClick={() => void runAction('refresh-status', refreshStatus)}>
              <RefreshCw size={15} /> Cập nhật
            </GlassButton>
          </div>

          <div className="mt-4 rounded-md border border-white/10 bg-slate-950/55 p-3 text-sm text-slate-300">
            <div className="grid gap-3 md:grid-cols-4">
              <InfoLine label="Chrome" value={status?.chrome_path || 'Chưa phát hiện'} />
              <InfoLine label="Trình điều khiển" value={status?.driver_path || 'Tự động quản lý'} />
              <InfoLine label="Hồ sơ đăng nhập" value={status?.profile_dir || 'Đang khởi tạo'} />
              <InfoLine label="Trang hiện tại" value={status?.current_url || 'Chưa mở'} />
            </div>
          </div>
        </GlassCard>

        <GlassCard strong className="min-w-0 p-4">
          <h2 className="text-base font-semibold text-white">Lưu ý sử dụng</h2>
          <div className="mt-3 grid gap-2 text-xs leading-5 text-slate-300">
            <p>Ứng dụng dùng Chrome riêng để bạn tự đăng nhập và xác minh nếu Douyin yêu cầu.</p>
            <p>Không tự vượt captcha, không gỡ watermark và không tải nội dung mà bạn không có quyền sử dụng.</p>
            <p>ChromeDriver có thể được tải lại nếu Chrome vừa cập nhật.</p>
          </div>
        </GlassCard>
      </section>

      <ApiErrorBox error={error} />
      {notice ? <div className="rounded-md border border-cyan-300/25 bg-cyan-300/10 px-4 py-3 text-sm text-cyan-100">{notice}</div> : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_400px]">
        <GlassCard className="flex min-h-0 min-w-0 flex-col p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-white">Quét đường dẫn video</h2>
            <span className="rounded-md border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-slate-300">
              Đã chọn {usableLinks.length} đường dẫn
            </span>
          </div>

          <div className="mt-4 grid gap-4">
            <Field label="Đường dẫn kênh hoặc trang Douyin">
              <input
                className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white outline-none transition focus:border-cyan-300"
                value={channelUrl}
                onChange={(event) => setChannelUrl(event.target.value)}
                placeholder="https://www.douyin.com/user/..."
                lang="vi"
              />
            </Field>
            {recentChannels.length ? <ChipRow label="Đã dùng gần đây" values={recentChannels} onUse={setChannelUrl} /> : null}

            {cachedLinks.length ? (
              <div className="rounded-md border border-emerald-300/25 bg-emerald-300/10 p-3 text-sm text-emerald-50">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span>Đã có {cachedLinks.length} link được lưu từ lần quét trước của kênh này.</span>
                  {cachedChannelDownload?.output_folder ? (
                    <span className="max-w-full truncate text-xs text-emerald-100/80" title={cachedChannelDownload.output_folder}>
                      Thư mục cũ: {compactPath(cachedChannelDownload.output_folder)}
                    </span>
                  ) : null}
                  <GlassButton className="whitespace-nowrap px-3" variant="primary" disabled={Boolean(activeJob)} onClick={() => void handleContinueCachedDownload()}>
                    Tiếp tục tải
                  </GlassButton>
                  <GlassButton className="whitespace-nowrap px-3" disabled={Boolean(activeJob)} onClick={useCachedScannedLinks}>
                    Dùng link đã quét
                  </GlassButton>
                </div>
              </div>
            ) : null}

            <label className="flex items-start gap-2 rounded-md border border-white/10 bg-white/5 p-3 text-sm text-slate-300">
              <input className="mt-1" type="checkbox" checked={scanUntilEnd} onChange={(event) => setScanUntilEnd(event.target.checked)} />
              <span>Quét đến khi hết video trong kênh. Bài dạng ảnh/slide sẽ được bỏ qua.</span>
            </label>

            <div className="grid gap-4 md:grid-cols-[220px_minmax(0,1fr)]">
              <Field label="Giới hạn an toàn số lần cuộn">
                <input
                  className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white outline-none transition focus:border-cyan-300"
                  type="number"
                  min={1}
                  max={5000}
                  value={maxScrolls}
                  onChange={(event) => setMaxScrolls(Number(event.target.value) || 1)}
                />
              </Field>
              <div className="flex flex-wrap items-end gap-2">
                <GlassButton className="whitespace-nowrap" variant="primary" loading={busy === 'scan'} disabled={Boolean(activeJob)} onClick={() => void handleScan()}>
                  <Search size={16} /> Quét đường dẫn
                </GlassButton>
                <GlassButton className="whitespace-nowrap" disabled={!scannedLinks.length && !linkLines.length} onClick={selectAllLinks}>
                  Chọn tất cả
                </GlassButton>
                <GlassButton className="whitespace-nowrap" disabled={!selectedLinks.length} onClick={clearSelectedLinks}>
                  Bỏ chọn
                </GlassButton>
              </div>
            </div>
          </div>

          <div className="mt-5 flex min-h-0 flex-1 flex-col">
            <h3 className="mb-2 text-sm font-semibold text-slate-100">Danh sách đường dẫn</h3>
            {scannedLinks.length ? (
              <div className="min-h-72 flex-1 overflow-y-auto rounded-md border border-white/10 bg-slate-950/55">
                {scannedLinks.map((link) => (
                  <label key={link} className="flex min-w-0 cursor-pointer items-start gap-3 border-b border-white/5 px-3 py-2 text-sm text-slate-300 last:border-b-0">
                    <input className="mt-1 shrink-0" type="checkbox" checked={selectedLinks.includes(link)} onChange={() => toggleLink(link)} />
                    <span className="min-w-0 flex-1 truncate" title={link}>{link}</span>
                    <button className="shrink-0 text-cyan-200 hover:text-cyan-100" type="button" onClick={() => void copyText(link)} aria-label="Sao chép đường dẫn">
                      <Copy size={15} />
                    </button>
                  </label>
                ))}
              </div>
            ) : (
              <textarea
                className="min-h-40 w-full flex-1 rounded-md border border-white/15 bg-slate-950/80 px-3 py-2 text-sm text-white outline-none transition focus:border-cyan-300"
                value={manualLinks}
                onChange={(event) => setManualLinks(event.target.value)}
                placeholder="Có thể dán mỗi dòng một đường dẫn video Douyin nếu không cần quét kênh."
                lang="vi"
              />
            )}
          </div>
        </GlassCard>

        <GlassCard className="min-w-0 p-5">
          <h2 className="text-lg font-semibold text-white">Tải về máy</h2>
          <div className="mt-4 grid gap-4">
            <Field label="Thư mục lưu video">
              <input
                className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white outline-none transition focus:border-cyan-300"
                value={outputFolder}
                onChange={(event) => setOutputFolder(event.target.value)}
                placeholder="./examples/sample_videos/douyin_downloads"
                lang="vi"
              />
            </Field>
            {recentFolders.length ? <ChipRow label="Thư mục gần đây" values={recentFolders} onUse={setOutputFolder} /> : null}
            <div className="flex flex-wrap gap-2">
              <GlassButton className="whitespace-nowrap px-3" loading={busy === 'browse-folder'} onClick={() => void handleBrowseFolder()}>
                <FolderOpen size={16} /> Chọn thư mục
              </GlassButton>
              <GlassButton className="whitespace-nowrap px-3" loading={busy === 'open-folder'} onClick={() => void handleOpenFolder()}>
                <ExternalLink size={16} /> Mở thư mục
              </GlassButton>
            </div>
            <label className="flex items-start gap-2 rounded-md border border-white/10 bg-white/5 p-3 text-sm text-slate-300">
              <input className="mt-1" type="checkbox" checked={skipExisting} onChange={(event) => setSkipExisting(event.target.checked)} />
              <span>Bỏ qua video đã tải để tiếp tục phần còn thiếu</span>
            </label>
            <GlassButton className="w-full whitespace-nowrap" variant="primary" loading={busy === 'download'} disabled={Boolean(activeJob)} onClick={() => void handleDownload()}>
              <Download size={16} /> Tải video đã chọn
            </GlassButton>
          </div>

          {job ? (
            <JobPanel
              job={job}
              busy={busy}
              onPause={() => void handlePauseJob()}
              onResume={() => void handleResumeJob()}
            />
          ) : null}
        </GlassCard>
      </section>

      {recentJobs.length ? (
        <GlassCard className="p-5">
          <div className="flex items-center gap-2">
            <History size={18} className="text-cyan-200" />
            <h2 className="text-lg font-semibold text-white">Lịch sử tải gần đây</h2>
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {recentJobs.map((item) => (
              <button
                key={item.job_id}
                className="min-w-0 rounded-md border border-white/10 bg-slate-950/45 p-3 text-left transition hover:border-cyan-300/35"
                type="button"
                onClick={() => useHistoryJob(item)}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="truncate text-sm font-semibold text-white">{item.job_type === 'scan' ? 'Quét đường dẫn' : 'Tải video'}</span>
                  <span className={statusClass(item.status)}>{statusLabel(item.status)}</span>
                </div>
                <div className="mt-2 truncate text-xs text-slate-400" title={item.current_step}>{item.current_step}</div>
                <div className="mt-2 text-xs text-slate-500">
                  {item.completed_items}/{item.total_items || item.links.length} hoàn tất · {formatDate(item.updated_at)}
                </div>
                {item.status === 'paused' && item.job_type === 'download' ? (
                  <div className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-cyan-200">
                    <PlayCircle size={14} /> Có thể tiếp tục
                  </div>
                ) : null}
              </button>
            ))}
          </div>
        </GlassCard>
      ) : null}
    </main>
  );
}

function StatusBadge({ status }: { status: DouyinDownloaderStatusResponse | null }) {
  const ready = Boolean(status?.browser_open);
  const loggedIn = Boolean(status?.logged_in);
  return (
    <div className={`inline-flex shrink-0 items-center gap-2 rounded-md border px-3 py-2 text-sm ${loggedIn ? 'border-emerald-300/35 bg-emerald-300/10 text-emerald-100' : ready ? 'border-amber-300/35 bg-amber-300/10 text-amber-100' : 'border-white/15 bg-white/5 text-slate-300'}`}>
      {loggedIn ? <CheckCircle2 size={16} /> : ready ? <ShieldCheck size={16} /> : <XCircle size={16} />}
      <span>{loggedIn ? 'Đã đăng nhập' : ready ? 'Đang mở Chrome' : 'Chưa mở Chrome'}</span>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-1.5">
      <span className="text-sm font-medium text-slate-200">{label}</span>
      {children}
    </label>
  );
}

function InfoLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 truncate text-sm text-slate-200" title={value}>{value}</div>
    </div>
  );
}

function ChipRow({ label, values, onUse }: { label: string; values: string[]; onUse: (value: string) => void }) {
  return (
    <div className="min-w-0">
      <div className="mb-2 text-xs font-medium text-slate-500">{label}</div>
      <div className="flex min-w-0 flex-wrap gap-2">
        {values.map((value) => (
          <button
            key={value}
            className="max-w-full truncate rounded-md border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-slate-300 transition hover:border-cyan-300/35 hover:text-white"
            type="button"
            title={value}
            onClick={() => onUse(value)}
          >
            {compactPath(value)}
          </button>
        ))}
      </div>
    </div>
  );
}

function JobPanel({
  job,
  busy,
  onPause,
  onResume,
}: {
  job: DouyinDownloaderJobResponse;
  busy: string | null;
  onPause: () => void;
  onResume: () => void;
}) {
  const canPause = job.status === 'running' || job.status === 'queued';
  const canResume = job.job_type === 'download' && job.status === 'paused';
  const latestLogs = job.logs.slice(-8).reverse();
  const latestOutputs = job.outputs.slice(-8).reverse();

  return (
    <div className="mt-5 rounded-md border border-white/10 bg-slate-950/55 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <ClipboardList size={16} className="text-cyan-200" />
            {job.job_type === 'scan' ? 'Tác vụ quét' : 'Tác vụ tải'}
          </div>
          <div className="mt-1 truncate text-xs text-slate-400" title={job.current_step}>{job.current_step}</div>
        </div>
        <span className="shrink-0 text-lg font-semibold text-cyan-100">{job.progress}%</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-cyan-300 transition-all" style={{ width: `${job.progress}%` }} />
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
        <Metric label="Tổng" value={job.total_items || job.links.length} />
        <Metric label="Xong" value={job.completed_items} />
        <Metric label="Lỗi" value={job.failed_items} />
      </div>
      {canPause || canResume ? (
        <div className="mt-3 flex gap-2">
          {canPause ? (
            <GlassButton className="flex-1 whitespace-nowrap px-3" loading={busy === 'pause-job'} onClick={onPause}>
              <PauseCircle size={16} /> {job.job_type === 'scan' ? 'Dừng quét' : 'Dừng tải'}
            </GlassButton>
          ) : null}
          {canResume ? (
            <GlassButton className="flex-1 whitespace-nowrap px-3" variant="primary" loading={busy?.startsWith('resume-')} onClick={onResume}>
              <PlayCircle size={16} /> Tiếp tục tải
            </GlassButton>
          ) : null}
        </div>
      ) : null}
      {latestOutputs.length ? (
        <div className="mt-4 rounded-md border border-white/10">
          {latestOutputs.map((output, index) => (
            <div key={`${output.link}-${index}`} className="min-w-0 border-b border-white/5 px-3 py-2 text-xs last:border-b-0">
              <div className={`truncate ${output.status === 'failed' ? 'text-rose-200' : output.status === 'skipped' ? 'text-amber-100' : 'text-emerald-100'}`} title={output.message}>
                {outputStatusLabel(output.status)}: {output.message}
              </div>
              {output.path ? <div className="mt-1 truncate text-slate-500" title={output.path}>{output.path}</div> : null}
            </div>
          ))}
        </div>
      ) : null}
      <div className="mt-4 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-xs text-slate-400">
        {latestLogs.length ? latestLogs.map((line, index) => <div className="truncate" title={line} key={`${line}-${index}`}>{line}</div>) : <div>Chưa có nhật ký.</div>}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-white/10 bg-white/5 p-2">
      <div className="text-slate-500">{label}</div>
      <div className="mt-1 text-base font-semibold text-white">{value}</div>
    </div>
  );
}

function parseLinks(value: string): string[] {
  const seen = new Set<string>();
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => {
      if (seen.has(line)) return false;
      seen.add(line);
      return true;
    });
}

function normalizeDouyinLink(value: string) {
  return value.trim().split('?')[0];
}

function compactPath(value: string) {
  if (value.length <= 48) return value;
  return `${value.slice(0, 18)}…${value.slice(-24)}`;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('vi-VN');
}

function statusLabel(status: DouyinDownloaderJobResponse['status']) {
  if (status === 'running') return 'Đang chạy';
  if (status === 'queued') return 'Đang chờ';
  if (status === 'paused') return 'Tạm dừng';
  if (status === 'completed') return 'Hoàn tất';
  if (status === 'failed') return 'Bị lỗi';
  return status;
}

function statusClass(status: DouyinDownloaderJobResponse['status']) {
  if (status === 'completed') return 'shrink-0 rounded-md bg-emerald-300/10 px-2 py-1 text-xs text-emerald-100';
  if (status === 'failed') return 'shrink-0 rounded-md bg-rose-300/10 px-2 py-1 text-xs text-rose-100';
  if (status === 'paused') return 'shrink-0 rounded-md bg-amber-300/10 px-2 py-1 text-xs text-amber-100';
  return 'shrink-0 rounded-md bg-cyan-300/10 px-2 py-1 text-xs text-cyan-100';
}

function outputStatusLabel(status: string) {
  if (status === 'failed') return 'Lỗi';
  if (status === 'skipped') return 'Bỏ qua';
  if (status === 'paused') return 'Tạm dừng';
  return 'Thành công';
}
