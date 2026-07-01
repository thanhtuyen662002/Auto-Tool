import { useEffect, useState } from 'react';
import { DownloadCloud, Info, Loader2 } from 'lucide-react';
import { checkSystemUpdate, downloadSystemUpdate, type UpdateCheckResponse } from '../api/client';
import { getHealth } from '../services/healthApi';
import GlassButton from './glass/GlassButton';
import NotifyOnChange from './notifications/NotifyOnChange';

interface UpdateBannerProps {
  connected: boolean;
}

export default function UpdateBanner({ connected }: UpdateBannerProps) {
  const [updateInfo, setUpdateInfo] = useState<UpdateCheckResponse | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadElapsedSeconds, setDownloadElapsedSeconds] = useState(0);
  const [downloadSuccess, setDownloadSuccess] = useState(false);
  const [isRestarting, setIsRestarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!connected) {
      setIsVisible(false);
      return;
    }

    const checkUpdate = async () => {
      try {
        const info = await checkSystemUpdate(false);
        if (info.has_update && info.latest_version) {
          setUpdateInfo(info);
          setIsVisible(true);
        }
      } catch (err) {
        console.error('Lỗi khi kiểm tra cập nhật:', err);
      }
    };

    void checkUpdate();
  }, [connected]);

  useEffect(() => {
    if (!isDownloading) return undefined;
    const timer = window.setInterval(() => {
      setDownloadElapsedSeconds((current) => current + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [isDownloading]);

  const handleDownloadAndInstall = async () => {
    setIsDownloading(true);
    setDownloadElapsedSeconds(0);
    setError(null);
    try {
      const res = await downloadSystemUpdate();
      if (res.success) {
        const targetVersion = updateInfo?.latest_version;
        setDownloadSuccess(true);
        setIsRestarting(true);
        if (targetVersion) {
          void waitForRestartAndReload(targetVersion);
        }
      } else {
        setError(res.error || 'Có lỗi xảy ra trong quá trình tải xuống.');
      }
    } catch (err: any) {
      setError(err.message || 'Không thể tải bản cập nhật.');
    } finally {
      setIsDownloading(false);
    }
  };

  const waitForRestartAndReload = async (targetVersion: string) => {
    const normalizedTarget = targetVersion.replace(/^v/i, '');
    const deadline = Date.now() + 10 * 60 * 1000;
    let sawBackendOffline = false;

    while (Date.now() < deadline) {
      await sleep(sawBackendOffline ? 2000 : 1200);
      try {
        const health = await getHealth();
        const normalizedCurrent = (health.version || '').replace(/^v/i, '');
        if (normalizedCurrent === normalizedTarget) {
          window.location.reload();
          return;
        }
      } catch {
        sawBackendOffline = true;
      }
    }

    setError('Cập nhật đã chạy nhưng giao diện chưa kết nối lại được. Hãy mở lại Auto Tool thủ công nếu cần.');
    setIsRestarting(false);
  };

  if (!isVisible || !updateInfo) return null;

  return (
    <div className="mx-4 mt-3 lg:mx-6">
      <NotifyOnChange value={error} variant="error" />
      <div className="relative overflow-hidden rounded-xl border border-purple-500/30 bg-gradient-to-r from-purple-900/20 via-indigo-950/30 to-blue-900/20 p-4 shadow-lg backdrop-blur-md studio-fade-in">
        {/* Decorative background light */}
        <div className="absolute -left-10 -top-10 h-32 w-32 rounded-full bg-purple-500/10 blur-2xl pointer-events-none" />
        <div className="absolute -right-10 -bottom-10 h-32 w-32 rounded-full bg-blue-500/10 blur-2xl pointer-events-none" />

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-300">
              <DownloadCloud className={`h-5 w-5 ${isDownloading ? 'animate-bounce' : ''}`} />
            </div>
            <div>
              <h4 className="font-semibold text-white text-sm md:text-base flex items-center gap-2">
                Phát hiện phiên bản mới: v{updateInfo.latest_version}
                <span className="inline-flex items-center rounded-full bg-purple-400/10 px-2 py-0.5 text-xs font-medium text-purple-300 ring-1 ring-inset ring-purple-400/20">
                  Mới
                </span>
              </h4>
              <p className="mt-0.5 text-xs md:text-sm text-slate-300">
                Phiên bản hiện tại của bạn là v{updateInfo.current_version}. 
                {downloadSuccess ? (
                  <strong className="text-emerald-400 font-medium ml-1">
                    Auto Tool đang tự cập nhật và sẽ mở lại sau khi hoàn tất.
                  </strong>
                ) : (
                  isDownloading
                    ? ' Auto Tool đang tải bản cập nhật, nếu mạng chập chờn hệ thống sẽ tự thử lại.'
                    : ' Bạn có thể cập nhật tự động chỉ với 1 cú click.'
                )}
              </p>
              {isDownloading && !downloadSuccess ? (
                <p className="mt-1 text-xs text-slate-400">
                  Đang chờ {formatElapsed(downloadElapsedSeconds)}. Nếu đường truyền GitHub đứng yên hơn khoảng 30 giây,
                  tool sẽ tự ngắt kết nối và tải tiếp từ phần đã tải.
                </p>
              ) : null}
              {error && (
                <div className="mt-1 space-y-1 text-xs font-medium text-rose-300">
                  <p>Lỗi: {error}</p>
                  {updateInfo.html_url && (
                    <button
                      type="button"
                      className="text-purple-200 underline decoration-purple-300/50 underline-offset-4 hover:text-white"
                      onClick={() => window.open(updateInfo.html_url || '', '_blank')}
                    >
                      Mở trang tải thủ công trên GitHub
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 md:self-center">
            {downloadSuccess ? (
              <div className="flex items-center gap-2 text-emerald-400 font-medium bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-lg text-sm">
                {isRestarting ? <Loader2 size={16} className="animate-spin" /> : <Info size={16} className="animate-pulse" />}
                <span>Đang cập nhật...</span>
              </div>
            ) : (
              <GlassButton
                variant="primary"
                className="min-h-9 px-4 text-xs font-semibold bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 border-none shadow-md shadow-purple-500/10"
                onClick={handleDownloadAndInstall}
                disabled={isDownloading}
              >
                {isDownloading ? (
                  <span className="flex items-center gap-1.5">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Đang cập nhật...
                  </span>
                ) : (
                  'Cập nhật'
                )}
              </GlassButton>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds} giây`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return remainder ? `${minutes} phút ${remainder} giây` : `${minutes} phút`;
}
