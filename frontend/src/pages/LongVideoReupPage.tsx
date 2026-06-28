import { useState, useEffect } from 'react';
import { Film, Play, AlertTriangle, CheckCircle2, RefreshCw, ShieldAlert, Cpu } from 'lucide-react';
import GlassCard from '../components/glass/GlassCard';
import GlassButton from '../components/glass/GlassButton';
import PathInput from '../components/PathInput';
import SliderInput from '../components/SliderInput';
import { scanDouyinFolder, startDouyinOneClick, getHealth } from '../services/startWorkflowApi';
import { emitNotification } from '../components/notifications/NotificationProvider';
import { getAppSettings } from '../api/client';
import type { DouyinVideoItem, DouyinReupSettings } from '../types/project';

const VIETNAMESE_TTS_VOICES = [
  { provider: 'edge_tts', voice: 'vi-VN-HoaiMyNeural', label: 'Edge TTS - Hoài My (Nữ)' },
  { provider: 'edge_tts', voice: 'vi-VN-NamMinhNeural', label: 'Edge TTS - Nam Minh (Nam)' },
  { provider: 'piper', voice: 'vi_VN-vais1000-medium', label: 'Piper Offline (Nam)' },
  { provider: 'google_cloud_tts', voice: 'vi-VN-Wavenet-A', label: 'Google Cloud - Wavenet A (Nữ)' },
  { provider: 'google_cloud_tts', voice: 'vi-VN-Wavenet-D', label: 'Google Cloud - Wavenet D (Nam)' },
];

export default function LongVideoReupPage() {
  const [sourceFolder, setSourceFolder] = useState('');
  const [outputFolder, setOutputFolder] = useState('');
  const [scanning, setScanning] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [videos, setVideos] = useState<DouyinVideoItem[]>([]);
  
  const [gpuAvailable, setGpuAvailable] = useState<boolean | null>(null);
  const [gpuName, setGpuName] = useState<string | null>(null);

  // Cấu hình video dài (độc lập)
  const [mode, setMode] = useState<'viet_sub' | 'dubbing'>('viet_sub');
  const [isolateAmbientSound, setIsolateAmbientSound] = useState(true);
  const [keepOriginalAudio, setKeepOriginalAudio] = useState(true);
  const [originalVolume, setOriginalVolume] = useState(0.85);
  
  const [addBgm, setAddBgm] = useState(false);
  const [bgmVolume, setBgmVolume] = useState(0.05);

  const [multiSpeakerEnabled, setMultiSpeakerEnabled] = useState(false);
  const [narratorVoice, setNarratorVoice] = useState('vi-VN-HoaiMyNeural');
  const [maleVoice, setMaleVoice] = useState('vi-VN-NamMinhNeural');
  const [femaleVoice, setFemaleVoice] = useState('vi-VN-HoaiMyNeural');
  
  // Tỷ lệ khung hình xuất
  const [dimensionMode, setDimensionMode] = useState<'vertical' | 'horizontal' | 'square' | 'auto'>('auto');

  // Cấu hình chia tập nhỏ video
  const [splitLongVideo, setSplitLongVideo] = useState(false);
  const [splitMaxDuration, setSplitMaxDuration] = useState(55);
  const [splitPartPrefix, setSplitPartPrefix] = useState('Phần');
  const [splitLabelDurationMode, setSplitLabelDurationMode] = useState<'always' | 'intro_5s'>('always');
  const [splitLabelPosition, setSplitLabelPosition] = useState<'top_center' | 'bottom_center' | 'top_left' | 'top_right'>('top_center');
  const [splitLabelFontSize, setSplitLabelFontSize] = useState(48);
  const [splitLabelFontColor, setSplitLabelFontColor] = useState('#ffffff');
  const [splitLabelBgColor, setSplitLabelBgColor] = useState('#000000');
  const [splitLabelBgOpacity, setSplitLabelBgOpacity] = useState(0.5);

  // Lấy cấu hình gần nhất và check GPU
  useEffect(() => {
    getAppSettings()
      .then((settings: any) => {
        if (settings.last_source_folder) setSourceFolder(settings.last_source_folder);
        if (settings.last_output_folder) setOutputFolder(settings.last_output_folder);
      })
      .catch(() => {});

    getHealth()
      .then((health) => {
        setGpuAvailable(Boolean(health.gpu_available));
        setGpuName(health.gpu_name || null);
      })
      .catch(() => {
        setGpuAvailable(false);
      });
  }, []);

  const handleScan = async () => {
    if (!sourceFolder.trim()) {
      emitNotification({ variant: 'warning', message: 'Vui lòng chọn thư mục chứa video nguồn' });
      return;
    }
    setScanning(true);
    try {
      const response = await scanDouyinFolder(sourceFolder);
      const items = response.media || [];
      setVideos(items);
      emitNotification({ variant: 'success', message: `Đã quét được ${items.length} video trong thư mục` });
    } catch (err: any) {
      emitNotification({ variant: 'error', message: `Không thể quét thư mục: ${err.message || err}` });
    } finally {
      setScanning(false);
    }
  };

  const handleStartWorkflow = async () => {
    if (videos.length === 0) {
      emitNotification({ variant: 'warning', message: 'Không có video nào trong danh sách để xử lý' });
      return;
    }
    if (!outputFolder.trim()) {
      emitNotification({ variant: 'warning', message: 'Vui lòng chọn thư mục xuất kết quả' });
      return;
    }

    setProcessing(true);
    try {
      const selectedPresetId = mode === 'viet_sub' ? 'long_movie_sub_only' : 'long_movie_dubbing';
      
      // Map cài đặt độc lập thành JSON truyền vào backend dưới dạng overrides
      const settingsPayload: Partial<DouyinReupSettings> = {
        enabled: true,
        preset_id: selectedPresetId,
        preset_name: mode === 'viet_sub' ? 'Phim - Chỉ chèn Sub Việt' : 'Phim - Thuyết minh Việt',
        burn_subtitle: true,
        
        // Cấu hình âm thanh video dài
        keep_original_audio: keepOriginalAudio,
        original_audio_volume: originalVolume,
        add_bgm: addBgm,
        bgm_volume: bgmVolume,
        video_dimension_mode: dimensionMode,
        
        // Tách vocal / giữ ambient
        reduce_original_voice: isolateAmbientSound,
        original_voice_reduction_strength: 0.88,
        
        // Thuyết minh & Multi-speaker
        generate_voiceover_for_silent_video: mode === 'dubbing',
        silent_voiceover_provider: 'edge_tts',
        silent_voiceover_voice: narratorVoice,
        
        // Cấu hình multi-speaker (Dành riêng cho phim dài)
        multi_speaker_enabled: multiSpeakerEnabled,
        speaker_voice_mapping: multiSpeakerEnabled ? {
          "narrator": narratorVoice,
          "male": maleVoice,
          "female": femaleVoice
        } : {},

        // Cấu hình chia nhỏ video
        split_long_video: splitLongVideo,
        split_max_duration: splitMaxDuration,
        split_part_prefix: splitPartPrefix,
        split_label_duration_mode: splitLabelDurationMode,
        split_label_position: splitLabelPosition,
        split_label_font_size: splitLabelFontSize,
        split_label_font_color: splitLabelFontColor,
        split_label_bg_color: splitLabelBgColor,
        split_label_bg_opacity: splitLabelBgOpacity,
      };

      // Gọi API bắt đầu xử lý hàng loạt
      await startDouyinOneClick({
        project_name: 'Phim/Vlog Dài',
        source_folder: sourceFolder,
        output_folder: outputFolder,
        preset_id: selectedPresetId,
        review_subtitles_before_render: true,
        auto_render_after_translation: false,
        advanced_overrides: settingsPayload,
      });

      emitNotification({ variant: 'success', message: 'Đã khởi tạo tác vụ xử lý video dài thành công!' });
      window.location.hash = '/results';
    } catch (err: any) {
      emitNotification({ variant: 'error', message: `Khởi chạy thất bại: ${err.message || err}` });
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 lg:px-8">
      {/* Tiêu đề & Giới thiệu */}
      <div className="mb-8 flex flex-col items-start justify-between gap-4 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-lg border border-cyan-400/35 bg-cyan-400/10 text-cyan-200">
              <Film size={22} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-wide">Xử lý video dài & Phim</h1>
              <p className="text-sm text-slate-400">Thiết kế tối ưu cho Phim, Vlog, Video tài liệu dài trên 15 phút</p>
            </div>
          </div>
        </div>

        <div className={`flex items-center gap-2 rounded-full border px-4 py-1.5 text-xs ${
          gpuAvailable === null
            ? 'border-white/10 bg-white/5 text-slate-300'
            : gpuAvailable
              ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-200'
              : 'border-amber-500/20 bg-amber-500/10 text-amber-200'
        }`}>
          <Cpu size={14} className={gpuAvailable ? 'animate-pulse' : ''} />
          <span>
            Trạng thái:{' '}
            {gpuAvailable === null ? (
              <strong>Đang kiểm tra...</strong>
            ) : gpuAvailable ? (
              <>
                Sẵn sàng chạy <strong>GPU</strong> ({gpuName || 'CUDA'})
              </>
            ) : (
              <>
                Chạy bằng <strong>CPU</strong> (Không phát hiện GPU CUDA)
              </>
            )}
          </span>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Cột 1 & 2: Cài đặt & Chọn thư mục */}
        <div className="space-y-6 lg:col-span-2">
          {/* Card Thư mục */}
          <GlassCard className="p-6">
            <h2 className="mb-4 text-base font-semibold text-white">1. Chọn đường dẫn làm việc</h2>
            <div className="space-y-4">
              <PathInput
                label="Thư mục chứa video gốc"
                value={sourceFolder}
                onChange={setSourceFolder}
                placeholder="Chọn thư mục chứa các tệp video cần reup..."
              />
              <PathInput
                label="Thư mục lưu kết xuất"
                value={outputFolder}
                onChange={setOutputFolder}
                placeholder="Chọn thư mục đích để lưu video thành phẩm..."
              />
              
              <div className="flex justify-end pt-2">
                <GlassButton
                  variant="primary"
                  onClick={handleScan}
                  disabled={scanning || !sourceFolder}
                  className="min-w-36"
                >
                  {scanning ? (
                    <>
                      <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      Đang quét...
                    </>
                  ) : (
                    'Quét thư mục'
                  )}
                </GlassButton>
              </div>
            </div>
          </GlassCard>

          {/* Cấu hình Âm thanh & Dịch thuật */}
          <GlassCard className="p-6">
            <h2 className="mb-6 text-base font-semibold text-white">2. Cài đặt âm thanh & Dịch thuật phim</h2>

            <div className="grid gap-6 sm:grid-cols-2">
              {/* Chọn chế độ xuất */}
              <div>
                <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-400">
                  Chế độ xuất video
                </label>
                <div className="grid gap-3">
                  <button
                    type="button"
                    onClick={() => setMode('viet_sub')}
                    className={`flex flex-col rounded-lg border p-4 text-left transition-all ${
                      mode === 'viet_sub'
                        ? 'border-cyan-400/40 bg-cyan-400/10 text-white'
                        : 'border-white/5 bg-white/3 text-slate-300 hover:bg-white/5'
                    }`}
                  >
                    <span className="font-semibold text-sm">Bản Việt Sub (Chỉ chèn phụ đề)</span>
                    <span className="mt-1 text-[11px] text-slate-400">
                      Chỉ dịch nghĩa thoại gốc và in cứng chữ tiếng Việt lên hình. Phù hợp giữ nguyên bản gốc.
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setMode('dubbing')}
                    className={`flex flex-col rounded-lg border p-4 text-left transition-all ${
                      mode === 'dubbing'
                        ? 'border-cyan-400/40 bg-cyan-400/10 text-white'
                        : 'border-white/5 bg-white/3 text-slate-300 hover:bg-white/5'
                    }`}
                  >
                    <span className="font-semibold text-sm">Bản Thuyết minh (Lồng tiếng + Phụ đề)</span>
                    <span className="mt-1 text-[11px] text-slate-400">
                      Tự động chuyển câu dịch sang giọng đọc AI tiếng Việt, đè khớp lên dòng thời gian phim.
                    </span>
                  </button>
                </div>
              </div>

              {/* Lựa chọn khung hình */}
              <div className="mt-4 sm:mt-0">
                <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-400">
                  Khung hình xuất video
                </label>
                <div className="grid gap-2">
                  <div>
                    <select
                      value={dimensionMode}
                      onChange={(e) => setDimensionMode(e.target.value as any)}
                      className="w-full rounded-md border border-white/10 bg-slate-900 px-3 py-2.5 text-xs text-white focus:border-cyan-500 focus:ring-cyan-500"
                    >
                      <option value="auto">Tự động (Giữ nguyên kích thước phim gốc)</option>
                      <option value="vertical">Dọc (9:16 - Thêm viền mờ boxblur cho video ngang)</option>
                      <option value="horizontal">Ngang (16:9 - Chuẩn định dạng phim/máy tính)</option>
                      <option value="square">Vuông (1:1)</option>
                    </select>
                    <span className="mt-1.5 block text-[10px] text-slate-400">
                      Mặc định: <strong>Giữ nguyên gốc</strong>. Nếu chọn Dọc, hệ thống tự động chèn blurred background (viền mờ) để khớp màn hình dọc điện thoại mà không cắt mất hình phim.
                    </span>
                  </div>
                </div>
              </div>

              {/* Tách thoại gốc & Nhạc nền */}
              <div className="space-y-6">
                <div>
                  <label className="mb-3 block text-xs font-bold uppercase tracking-wider text-slate-400">
                    Xử lý giọng nói cũ
                  </label>
                  
                  <div className="space-y-3">
                    <label className="flex items-start gap-3 cursor-pointer rounded-lg bg-white/3 p-3 border border-white/5">
                      <input
                        type="checkbox"
                        checked={isolateAmbientSound}
                        onChange={(e) => setIsolateAmbientSound(e.target.checked)}
                        className="mt-0.5 h-4 w-4 rounded border-white/10 bg-slate-800 text-cyan-500 focus:ring-cyan-500 focus:ring-offset-0"
                      />
                      <div>
                        <span className="block text-xs font-semibold text-slate-200">Tách giọng cũ (Isolate Ambient)</span>
                        <span className="block text-[10px] text-slate-400 mt-0.5">
                          Tự động giảm/loại tiếng nói của nhân vật gốc nhưng vẫn giữ lại tiếng động môi trường.
                        </span>
                      </div>
                    </label>

                    <label className="flex items-start gap-3 cursor-pointer rounded-lg bg-white/3 p-3 border border-white/5">
                      <input
                        type="checkbox"
                        checked={keepOriginalAudio}
                        onChange={(e) => setKeepOriginalAudio(e.target.checked)}
                        className="mt-0.5 h-4 w-4 rounded border-white/10 bg-slate-800 text-cyan-500 focus:ring-cyan-500 focus:ring-offset-0"
                      />
                      <div>
                        <span className="block text-xs font-semibold text-slate-200">Giữ âm thanh môi trường gốc</span>
                        <span className="block text-[10px] text-slate-400 mt-0.5">
                          Âm thanh nền (tiếng bước chân, tiếng gió, nhạc phim...) được hòa trộn lại.
                        </span>
                      </div>
                    </label>
                  </div>
                </div>

                {keepOriginalAudio && (
                  <SliderInput
                    label="Âm lượng âm thanh gốc"
                    min={0}
                    max={1}
                    step={0.05}
                    value={originalVolume}
                    onChange={setOriginalVolume}
                  />
                )}
              </div>
            </div>

            {/* Mục nhạc nền */}
            <div className="mt-6 border-t border-white/5 pt-6">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={addBgm}
                  onChange={(e) => setAddBgm(e.target.checked)}
                  className="h-4 w-4 rounded border-white/10 bg-slate-800 text-cyan-500 focus:ring-cyan-500"
                />
                <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-300">
                  <span>Chèn nhạc nền nhẹ (BGM)</span>
                </div>
              </label>

              {addBgm && (
                <div className="mt-4 max-w-md">
                  <SliderInput
                    label="Âm lượng nhạc nền phim (Khuyên dùng mức rất nhỏ)"
                    min={0}
                    max={0.3}
                    step={0.01}
                    value={bgmVolume}
                    onChange={setBgmVolume}
                  />
                </div>
              )}
            </div>
          </GlassCard>

          {/* Cấu hình phân vai giọng đọc */}
          {mode === 'dubbing' && (
            <GlassCard className="p-6">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-base font-semibold text-white flex items-center gap-2">
                  <Film size={18} className="text-cyan-300" />
                  3. Phân vai giọng thuyết minh
                </h2>

                <label className="flex items-center gap-2 cursor-pointer text-xs text-cyan-200">
                  <input
                    type="checkbox"
                    checked={multiSpeakerEnabled}
                    onChange={(e) => setMultiSpeakerEnabled(e.target.checked)}
                    className="h-3.5 w-3.5 rounded border-white/10 bg-slate-800 text-cyan-500 focus:ring-cyan-500"
                  />
                  <span>Kích hoạt thuyết minh đa vai (Roadmap)</span>
                </label>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-xs text-slate-400">Giọng thuyết minh chính (Dẫn truyện)</label>
                  <select
                    value={narratorVoice}
                    onChange={(e) => setNarratorVoice(e.target.value)}
                    className="w-full rounded-md border border-white/10 bg-slate-900 px-3 py-2 text-xs text-white focus:border-cyan-500 focus:ring-cyan-500"
                  >
                    {VIETNAMESE_TTS_VOICES.map((item) => (
                      <option key={item.voice} value={item.voice}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </div>

                {multiSpeakerEnabled && (
                  <>
                    <div>
                      <label className="mb-1.5 block text-xs text-slate-400">Giọng nhân vật Nam</label>
                      <select
                        value={maleVoice}
                        onChange={(e) => setMaleVoice(e.target.value)}
                        className="w-full rounded-md border border-white/10 bg-slate-900 px-3 py-2 text-xs text-white focus:border-cyan-500 focus:ring-cyan-500"
                      >
                        {VIETNAMESE_TTS_VOICES.filter((item) => item.label.includes('Nam') || item.label.includes('Offline')).map((item) => (
                          <option key={item.voice} value={item.voice}>
                            {item.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="mb-1.5 block text-xs text-slate-400">Giọng nhân vật Nữ</label>
                      <select
                        value={femaleVoice}
                        onChange={(e) => setFemaleVoice(e.target.value)}
                        className="w-full rounded-md border border-white/10 bg-slate-900 px-3 py-2 text-xs text-white focus:border-cyan-500 focus:ring-cyan-500"
                      >
                        {VIETNAMESE_TTS_VOICES.filter((item) => item.label.includes('Nữ')).map((item) => (
                          <option key={item.voice} value={item.voice}>
                            {item.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </>
                )}
              </div>
            </GlassCard>
          )}

          {/* Cấu hình chia nhỏ video dài thành các tập ngắn */}
          <GlassCard className="p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Film size={18} className="text-cyan-300" />
                3. Chia nhỏ video dài thành các tập ngắn (Shorts/Reels)
              </h2>

              <label className="flex items-center gap-2 cursor-pointer text-xs text-cyan-200">
                <input
                  type="checkbox"
                  checked={splitLongVideo}
                  onChange={(e) => setSplitLongVideo(e.target.checked)}
                  className="h-3.5 w-3.5 rounded border-white/10 bg-slate-800 text-cyan-500 focus:ring-cyan-500"
                />
                <span>Kích hoạt tự động chia tập</span>
              </label>
            </div>

            {splitLongVideo && (
              <div className="space-y-6 pt-2 border-t border-white/5">
                <div className="grid gap-4 sm:grid-cols-3">
                  <div>
                    <label className="mb-1.5 block text-xs text-slate-400">Thời lượng mỗi tập (giây)</label>
                    <input
                      type="number"
                      min={10}
                      max={300}
                      value={splitMaxDuration}
                      onChange={(e) => setSplitMaxDuration(Number(e.target.value))}
                      className="w-full rounded-md border border-white/10 bg-slate-900 px-3 py-2 text-xs text-white focus:border-cyan-500 focus:ring-cyan-500"
                    />
                    <span className="mt-1 block text-[10px] text-slate-500">Mốc lý tưởng là 55s</span>
                  </div>

                  <div>
                    <label className="mb-1.5 block text-xs text-slate-400">Tiền tố số tập (Chữ hiển thị)</label>
                    <input
                      type="text"
                      value={splitPartPrefix}
                      onChange={(e) => setSplitPartPrefix(e.target.value)}
                      className="w-full rounded-md border border-white/10 bg-slate-900 px-3 py-2 text-xs text-white focus:border-cyan-500 focus:ring-cyan-500"
                    />
                    <span className="mt-1 block text-[10px] text-slate-500">Ví dụ: Phần 1, Tập 1...</span>
                  </div>

                  <div>
                    <label className="mb-1.5 block text-xs text-slate-400">Thời gian hiển thị số tập</label>
                    <select
                      value={splitLabelDurationMode}
                      onChange={(e) => setSplitLabelDurationMode(e.target.value as any)}
                      className="w-full rounded-md border border-white/10 bg-slate-900 px-3 py-2 text-xs text-white focus:border-cyan-500 focus:ring-cyan-500"
                    >
                      <option value="always">Hiển thị xuyên suốt video</option>
                      <option value="intro_5s">Chỉ hiển thị 5 giây đầu</option>
                    </select>
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <h3 className="mb-3 text-xs font-semibold text-slate-300">Tùy biến hiển thị nhãn tập</h3>
                    <div className="space-y-4">
                      <div>
                        <label className="mb-1.5 block text-xs text-slate-400">Vị trí hiển thị trên khung hình</label>
                        <select
                          value={splitLabelPosition}
                          onChange={(e) => setSplitLabelPosition(e.target.value as any)}
                          className="w-full rounded-md border border-white/10 bg-slate-900 px-3 py-2 text-xs text-white focus:border-cyan-500 focus:ring-cyan-500"
                        >
                          <option value="top_center">Góc trên cùng - Ở giữa</option>
                          <option value="bottom_center">Góc dưới cùng - Ở giữa</option>
                          <option value="top_left">Góc trên cùng - Bên trái</option>
                          <option value="top_right">Góc trên cùng - Bên phải</option>
                        </select>
                      </div>

                      <SliderInput
                        label="Cỡ chữ nhãn số tập"
                        min={16}
                        max={96}
                        step={2}
                        value={splitLabelFontSize}
                        onChange={setSplitLabelFontSize}
                      />
                    </div>
                  </div>

                  <div>
                    <h3 className="mb-3 text-xs font-semibold text-slate-300">Màu sắc & Hộp nền</h3>
                    <div className="space-y-4">
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div>
                          <label className="mb-1.5 block text-xs text-slate-400">Màu chữ nhãn</label>
                          <div className="flex gap-2 items-center">
                            <input
                              type="color"
                              value={splitLabelFontColor}
                              onChange={(e) => setSplitLabelFontColor(e.target.value)}
                              className="h-8 w-8 rounded border border-white/10 bg-slate-900"
                            />
                            <span className="font-mono text-xs text-slate-300">{splitLabelFontColor}</span>
                          </div>
                        </div>

                        <div>
                          <label className="mb-1.5 block text-xs text-slate-400">Màu nền hộp</label>
                          <div className="flex gap-2 items-center">
                            <input
                              type="color"
                              value={splitLabelBgColor}
                              onChange={(e) => setSplitLabelBgColor(e.target.value)}
                              className="h-8 w-8 rounded border border-white/10 bg-slate-900"
                            />
                            <span className="font-mono text-xs text-slate-300">{splitLabelBgColor}</span>
                          </div>
                        </div>
                      </div>

                      <SliderInput
                        label="Độ mờ của hộp nền (%)"
                        min={0}
                        max={1}
                        step={0.05}
                        value={splitLabelBgOpacity}
                        onChange={setSplitLabelBgOpacity}
                      />
                    </div>
                  </div>
                </div>

                <div className="rounded-lg bg-cyan-400/5 border border-cyan-400/10 p-3.5 text-xs text-cyan-200">
                  <div className="font-bold mb-1">⚡ Thuật toán cắt thông minh tự động:</div>
                  Hệ thống sẽ tự động quét file phụ đề sau khi dịch để tìm khoảng lặng kết thúc câu nói gần mốc {splitMaxDuration}s nhất để cắt video. Tránh tuyệt đối việc cắt đứt câu thoại dở dang của nhân vật!
                </div>
              </div>
            )}
          </GlassCard>
        </div>

        {/* Cột 3: Danh sách video & Nút xử lý */}
        <div className="lg:h-0 lg:min-h-full flex flex-col min-h-[500px]">
          <GlassCard className="p-6 flex flex-col flex-1 min-h-0">
            <h2 className="mb-4 text-base font-semibold text-white flex items-center justify-between">
              <span>Danh sách quét ({videos.length})</span>
              {videos.length > 0 && (
                <button
                  onClick={handleScan}
                  className="text-xs text-cyan-300 hover:text-cyan-200 transition-colors flex items-center gap-1"
                >
                  <RefreshCw size={10} /> Quét lại
                </button>
              )}
            </h2>

            {videos.length === 0 ? (
              <div className="flex flex-1 flex-col items-center justify-center text-center p-6 border border-dashed border-white/10 rounded-lg bg-white/2">
                <Film size={36} className="text-slate-600 mb-3" />
                <p className="text-xs text-slate-400">Chưa có video được quét.</p>
                <p className="text-[10px] text-slate-500 mt-1">Hãy chọn thư mục nguồn rồi bấm "Quét thư mục" để hiển thị danh sách video.</p>
              </div>
            ) : (
              <div className="flex-1 min-h-0 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
                {videos.map((item, idx) => {
                  const isVeryLong = item.duration > 1800; // >30m
                  const isLong = item.duration > 900; // >15m
                  return (
                    <div
                      key={idx}
                      className={`rounded-lg border bg-white/3 p-3 transition-colors ${
                        isVeryLong ? 'border-red-500/25' : isLong ? 'border-yellow-500/25' : 'border-white/5'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <span className="block truncate text-xs font-semibold text-white" title={item.filename}>
                            {item.filename}
                          </span>
                          <span className="block text-[10px] text-slate-400 mt-1">
                            Thời lượng: {Math.floor(item.duration / 60)} phút {Math.floor(item.duration % 60)} giây
                          </span>
                        </div>

                        {isVeryLong ? (
                          <ShieldAlert size={14} className="text-red-400 shrink-0 mt-0.5" />
                        ) : isLong ? (
                          <AlertTriangle size={14} className="text-yellow-400 shrink-0 mt-0.5" />
                        ) : (
                          <CheckCircle2 size={14} className="text-emerald-400 shrink-0 mt-0.5" />
                        )}
                      </div>

                      {(isLong || isVeryLong) && (
                        <div className={`mt-2 rounded p-1.5 text-[9px] ${isVeryLong ? 'bg-red-500/10 text-red-300' : 'bg-yellow-500/10 text-yellow-300'}`}>
                          {isVeryLong 
                            ? 'Lưu ý: Quá 30 phút. Ưu tiên chạy GPU để tránh timeout CPU.' 
                            : 'Xử lý video dài trên 15 phút có thể lâu trên CPU.'}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Khu vực kích hoạt hàng loạt */}
            <div className="mt-auto pt-6 border-t border-white/5">
              <GlassButton
                variant="primary"
                onClick={handleStartWorkflow}
                disabled={processing || videos.length === 0 || !outputFolder}
                className="w-full justify-center text-sm font-semibold h-11 shadow-[0_0_20px_rgba(34,211,238,0.15)] hover:shadow-[0_0_28px_rgba(34,211,238,0.3)] transition-all"
              >
                {processing ? (
                  <>
                    <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                    Đang khởi tạo hàng đợi...
                  </>
                ) : (
                  <>
                    <Play className="mr-2 h-4.5 w-4.5 fill-current" />
                    Bắt đầu xử lý hàng loạt
                  </>
                )}
              </GlassButton>
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
