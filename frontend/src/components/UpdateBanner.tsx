import { useEffect, useState } from 'react';
import { DownloadCloud, Info, X, Loader2 } from 'lucide-react';
import { checkSystemUpdate, downloadSystemUpdate, type UpdateCheckResponse } from '../api/client';
import GlassButton from './glass/GlassButton';

interface UpdateBannerProps {
  connected: boolean;
}

export default function UpdateBanner({ connected }: UpdateBannerProps) {
  const [updateInfo, setUpdateInfo] = useState<UpdateCheckResponse | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadSuccess, setDownloadSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!connected) {
      setIsVisible(false);
      return;
    }

    // Kiểm tra xem có phiên bản update đã được bỏ qua chưa
    const checkUpdate = async () => {
      try {
        const info = await checkSystemUpdate(false);
        if (info.has_update && info.latest_version) {
          const ignoredVersion = localStorage.getItem('ignored_update_version');
          if (ignoredVersion !== info.latest_version) {
            setUpdateInfo(info);
            setIsVisible(true);
          }
        }
      } catch (err) {
        console.error('Lỗi khi kiểm tra cập nhật:', err);
      }
    };

    void checkUpdate();
  }, [connected]);

  const handleIgnore = () => {
    if (updateInfo?.latest_version) {
      localStorage.setItem('ignored_update_version', updateInfo.latest_version);
    }
    setIsVisible(false);
  };

  const handleDownloadAndInstall = async () => {
    setIsDownloading(true);
    setError(null);
    try {
      const res = await downloadSystemUpdate();
      if (res.success) {
        setDownloadSuccess(true);
      } else {
        setError(res.error || 'Có lỗi xảy ra trong quá trình tải xuống.');
      }
    } catch (err: any) {
      setError(err.message || 'Không thể tải bản cập nhật.');
    } finally {
      setIsDownloading(false);
    }
  };

  if (!isVisible || !updateInfo) return null;

  return (
    <div className="mx-4 mt-3 lg:mx-6">
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
                🚀 Phát hiện phiên bản mới: v{updateInfo.latest_version}
                <span className="inline-flex items-center rounded-full bg-purple-400/10 px-2 py-0.5 text-xs font-medium text-purple-300 ring-1 ring-inset ring-purple-400/20">
                  New
                </span>
              </h4>
              <p className="mt-0.5 text-xs md:text-sm text-slate-300">
                Phiên bản hiện tại của bạn là v{updateInfo.current_version}. 
                {downloadSuccess ? (
                  <strong className="text-emerald-400 font-medium ml-1">
                    Tải thành công! Vui lòng đóng phần mềm để tự động cài đặt bản cập nhật.
                  </strong>
                ) : (
                  ' Bạn có thể cập nhật tự động chỉ với 1 cú click.'
                )}
              </p>
              {error && (
                <p className="mt-1 text-xs text-rose-400 font-medium">Lỗi: {error}</p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 md:self-center">
            {downloadSuccess ? (
              <div className="flex items-center gap-2 text-emerald-400 font-medium bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-lg text-sm">
                <Info size={16} className="animate-pulse" />
                <span>Hãy tắt ứng dụng để cập nhật</span>
              </div>
            ) : (
              <>
                {updateInfo.html_url && (
                  <GlassButton
                    variant="ghost"
                    className="min-h-9 px-4 text-xs font-semibold text-purple-200 hover:text-white"
                    onClick={() => window.open(updateInfo.html_url || '', '_blank')}
                  >
                    Xem thay đổi
                  </GlassButton>
                )}

                <GlassButton
                  variant="primary"
                  className="min-h-9 px-4 text-xs font-semibold bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 border-none shadow-md shadow-purple-500/10"
                  onClick={handleDownloadAndInstall}
                  disabled={isDownloading}
                >
                  {isDownloading ? (
                    <span className="flex items-center gap-1.5">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Đang tải...
                    </span>
                  ) : (
                    'Cập nhật ngay'
                  )}
                </GlassButton>
              </>
            )}

            <button
              type="button"
              className="ml-2 rounded-lg p-1.5 text-slate-400 hover:bg-white/5 hover:text-white transition-colors"
              onClick={handleIgnore}
              aria-label="Bỏ qua phiên bản này"
            >
              <X size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
