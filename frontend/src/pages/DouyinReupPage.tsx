import { useEffect, useMemo, useState, type PointerEvent, type ReactNode } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { AlertTriangle, CheckCircle2, Info, Play, RefreshCw, Route, Settings2 } from 'lucide-react';
import {
  applyDouyinReupPreset,
  buildSilentReupPlan,
  browsePath,
  createSilentReupReviewDocument,
  createDouyinExportPack,
  finalOutputQAReportUrl,
  getDouyinExportPack,
  getDouyinReupJobResults,
  getAppSettings,
  getJobStatus,
  getProject,
  getSilentVisualTagVocabulary,
  getVisualStyles,
  listSilentCaptionIndustries,
  openDouyinExportPack,
  recommendDouyinReupPreset,
  regenerateSilentReupCaptions,
  updateSilentSegmentVisualTags,
  renderApprovedSubtitleReviewDocuments,
  retryDouyinReupJobWithPreset,
  retryDouyinReupJobCustom,
  retryFailedDouyinReupJob,
  runFinalOutputQAForJob,
  sourceVideoFileUrl,
  startDouyinReupProcess,
  videoFileUrl,
} from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import SliderInput from '../components/SliderInput';
import GlassButton from '../components/glass/GlassButton';
import GlassCard from '../components/glass/GlassCard';
import GlassModal from '../components/glass/GlassModal';
import JobProgressPanel from '../components/jobs/JobProgressPanel';
import { emitNotification } from '../components/notifications/NotificationProvider';
import NotifyOnChange from '../components/notifications/NotifyOnChange';
import SegmentTagEditor from '../components/silent/SegmentTagEditor';
import SilentPlanPreview from '../components/silent/SilentPlanPreview';
import MusicFolderCard from '../components/start-workflow/MusicFolderCard';
import OutputFolderCard from '../components/start-workflow/OutputFolderCard';
import ProductContextCard from '../components/start-workflow/ProductContextCard';
import SourceFolderCard from '../components/start-workflow/SourceFolderCard';
import StartAdvancedSettingsDrawer from '../components/start-workflow/StartAdvancedSettingsDrawer';
import StartPresetSelector from '../components/start-workflow/StartPresetSelector';
import StartWorkflowLayout from '../components/start-workflow/StartWorkflowLayout';
import WorkflowHero from '../components/start-workflow/WorkflowHero';
import WorkflowStepper from '../components/workflow/WorkflowStepper';
import {
  browseStartFolder,
  getHealth,
  getPresets,
  scanDouyinFolder,
  startDouyinOneClick,
  startSilentOneClick,
} from '../services/startWorkflowApi';
import { getHealth as getBackendHealth, type HealthResponse } from '../services/healthApi';
import {
  addRecentMusicFolder,
  addRecentOutputFolder,
  addRecentSourceFolder,
  getLocalAppConfig,
  getRecentPaths,
  type LocalRecentPaths,
} from '../services/localAppApi';
import type {
  DouyinOutputResult,
  DouyinPresetRecommendationResponse,
  DouyinReupPreset,
  DouyinReupSummary,
  DouyinReupSettings,
  DouyinRetryCustomMode,
  DouyinVideoItem,
  JobStatus,
  PlatformExportPack,
  PlatformTarget,
  SystemDependencyStatusResponse,
  SilentReupPlanResponse,
  SilentVisualTagVocabulary,
  VisualStylePreset,
} from '../types/project';
import type {
  JobStartedView,
  StartChecklistItem,
  StartPresetViewModel,
  StartRecentFolder,
  StartScanSummary,
  StartValidationMessage,
  StartWorkflowMode,
} from '../types/startWorkflow';
import { summarizeStartScan } from '../types/startWorkflow';
import { formatBytes } from '../utils/formatBytes';
import { friendlyTermLabel } from '../utils/userFacingTerms';

type ExportOptions = {
  copy_videos: boolean;
  include_subtitles: boolean;
  include_logs: boolean;
  include_captions: boolean;
  include_posting_checklist: boolean;
};

const CUSTOM_RETRY_MODE_OPTIONS: Array<{
  value: DouyinRetryCustomMode;
  label: string;
  description: string;
}> = [
  {
    value: 'render_only',
    label: 'Chỉ dựng lại video',
    description: 'Dùng lại phụ đề/dịch cũ. Phù hợp khi bạn chỉ đổi font, vị trí sub, nền che, nhạc hoặc âm lượng.',
  },
  {
    value: 'read_screen_text',
    label: 'Đọc lại chữ trên video rồi dựng',
    description: 'Ưu tiên đọc chữ đang hiện trên video trước khi dịch và dựng lại. Phù hợp khi sub Trung nằm giữa màn hình hoặc nền che chưa đúng.',
  },
  {
    value: 'rebuild_subtitle',
    label: 'Làm lại phụ đề/thoại rồi dựng',
    description: 'Chạy lại bước lấy phụ đề/thoại, dịch lại rồi dựng. Dùng khi lời thoại hoặc bản dịch cũ không ổn.',
  },
];

type SilentProductContext = {
  product_name: string;
  industry: string;
  features: string;
  cta: string;
};

const DEFAULT_SILENT_INDUSTRIES = [
  { id: 'auto', name: 'Tự nhận diện từ video' },
  { id: 'general_product', name: 'Sản phẩm chung' },
  { id: 'home_goods', name: 'Đồ gia dụng' },
  { id: 'kitchen_goods', name: 'Đồ nhà bếp' },
  { id: 'storage_organization', name: 'Đồ sắp xếp/lưu trữ' },
  { id: 'desk_setup', name: 'Góc bàn/làm việc' },
  { id: 'dorm_goods', name: 'Phòng nhỏ/ký túc xá' },
  { id: 'beauty_goods', name: 'Mỹ phẩm/làm đẹp' },
  { id: 'cleaning_goods', name: 'Đồ vệ sinh/lau dọn' },
];

const DEFAULT_VISUAL_TAG_VOCABULARY: SilentVisualTagVocabulary = {
  industry: DEFAULT_SILENT_INDUSTRIES.map((item) => item.id).filter((id) => id !== 'auto'),
  scene: ['home_scene', 'kitchen_scene', 'bathroom_scene', 'bedroom_scene', 'desk_scene', 'dorm_scene', 'vanity_scene', 'storage_scene', 'cleaning_scene'],
  action: ['unboxing', 'opening_package', 'hands_operation', 'placing_product', 'assembling', 'testing', 'pouring', 'wiping', 'cleaning', 'organizing', 'folding', 'comparison', 'before_after', 'closeup', 'product_reveal', 'usage_demo', 'result_showcase'],
  product_stage: ['packaging', 'first_look', 'detail_closeup', 'demo_step', 'benefit_scene', 'final_result', 'cta_scene'],
  quality: ['clear_frame', 'dark_frame', 'high_motion', 'low_motion', 'stable_shot', 'blur_risk'],
};

const VIETNAMESE_TTS_VOICES = [
  { provider: 'edge_tts', voice: 'vi-VN-HoaiMyNeural', label: 'Edge TTS - Hoài My (nữ)' },
  { provider: 'edge_tts', voice: 'vi-VN-NamMinhNeural', label: 'Edge TTS - Nam Minh (nam)' },
  { provider: 'piper', voice: 'vi_VN-vais1000-medium', label: 'Piper offline - vais1000' },
  { provider: 'google_cloud_tts', voice: 'vi-VN-Wavenet-A', label: 'Google Cloud - Wavenet A (nữ)' },
  { provider: 'google_cloud_tts', voice: 'vi-VN-Wavenet-D', label: 'Google Cloud - Wavenet D (nam)' },
];

type VietnameseSubtitleStylePreset = {
  id: string;
  name: string;
  description: string;
  accentColor: string;
  previewText: string;
  settings: Partial<DouyinReupSettings>;
};

const VIETNAMESE_SUBTITLE_FONT_OPTIONS = [
  'Be Vietnam Pro',
  'Montserrat',
  'Roboto Condensed',
  'Nunito Sans',
  'Lexend',
  'Mulish',
  'Manrope',
  'Inter',
  'Be Vietnam Pro Black',
  'Panger',
  'Word Shark (Black Italy)',
  'Badiho Support',
  'ICL KDA',
  'Gotham Ultra',
  'SVN-Gotham Black',
  'SVN-Gilroy Heavy',
  'SVN-Gilroy XBold',
  'SVN-Gotham Ultra',
  'Be Vietnam Pro ExtraBold',
  'Baloo 2 ExtraBold',
  'Nunito ExtraBold',
  'Roboto Condensed Bold',
  'Google Sans Bold',
  'UTM Avo Bold',
  'SVN-Poppins ExtraBold',
  'SVN-Montserrat Black',
  'Montserrat ExtraBold',
  'Inter Tight Black',
  'Inter Black',
  'SF Pro Display Heavy',
  'Arial Rounded MT Bold',
  'Arial Unicode MS',
  'Tahoma',
  'Arial',
];

const LEGACY_VIETNAMESE_SUBTITLE_STYLE_PRESETS: VietnameseSubtitleStylePreset[] = [
  {
    id: 'review_mint_pop',
    name: 'Review mint nổi',
    description: 'Nền xanh ngọc trầm, chữ sáng, hợp review sản phẩm đời sống.',
    accentColor: '#56F0C9',
    previewText: 'Rất đáng thử',
    settings: {
      subtitle_style_custom_enabled: true,
      subtitle_font_family: 'Be Vietnam Pro ExtraBold',
      subtitle_font_size: 56,
      subtitle_font_color: '#E9FFF7',
      subtitle_stroke_color: '#00342F',
      subtitle_stroke_width: 3,
      subtitle_shadow_enabled: true,
      subtitle_shadow_color: '#001C19',
      subtitle_shadow_opacity: 0.42,
      subtitle_shadow_size: 3,
      subtitle_max_chars_per_line: 22,
      subtitle_max_lines: 2,
      subtitle_cover_enabled: true,
      subtitle_cover_color: '#062E2B',
      subtitle_cover_opacity: 0.86,
      subtitle_cover_height_ratio: 0.12,
      subtitle_cover_padding_ratio: 0.03,
    },
  },
  {
    id: 'viral_coral_panger',
    name: 'Viral coral',
    description: 'Cam san hô ấm, chữ sáng nổi mạnh cho video nhịp nhanh.',
    accentColor: '#FF8A5B',
    previewText: 'Mua là mê',
    settings: {
      subtitle_style_custom_enabled: true,
      subtitle_font_family: 'Panger',
      subtitle_font_size: 62,
      subtitle_font_color: '#FFE66D',
      subtitle_stroke_color: '#2B0612',
      subtitle_stroke_width: 4,
      subtitle_shadow_enabled: true,
      subtitle_shadow_color: '#2B0612',
      subtitle_shadow_opacity: 0.5,
      subtitle_shadow_size: 3,
      subtitle_max_chars_per_line: 18,
      subtitle_max_lines: 2,
      subtitle_cover_enabled: true,
      subtitle_cover_color: '#2B0712',
      subtitle_cover_opacity: 0.9,
      subtitle_cover_height_ratio: 0.12,
      subtitle_cover_padding_ratio: 0.035,
    },
  },
  {
    id: 'sale_champagne_gotham',
    name: 'Sale champagne',
    description: 'Vàng champagne sang hơn, hợp video bán hàng và CTA cuối.',
    accentColor: '#D6A84F',
    previewText: 'Chốt đơn ngay',
    settings: {
      subtitle_style_custom_enabled: true,
      subtitle_font_family: 'Gotham Ultra',
      subtitle_font_size: 58,
      subtitle_font_color: '#FFD166',
      subtitle_stroke_color: '#2F1705',
      subtitle_stroke_width: 3,
      subtitle_shadow_enabled: true,
      subtitle_shadow_color: '#000000',
      subtitle_shadow_opacity: 0.38,
      subtitle_shadow_size: 2,
      subtitle_max_chars_per_line: 19,
      subtitle_max_lines: 2,
      subtitle_cover_enabled: true,
      subtitle_cover_color: '#241005',
      subtitle_cover_opacity: 0.9,
      subtitle_cover_height_ratio: 0.12,
      subtitle_cover_padding_ratio: 0.035,
    },
  },
  {
    id: 'beauty_lilac_wordshark',
    name: 'Beauty lilac',
    description: 'Tím lilac mềm, hợp mỹ phẩm, thời trang và video lifestyle.',
    accentColor: '#FF9FD8',
    previewText: 'Xinh nhẹ nhàng',
    settings: {
      subtitle_style_custom_enabled: true,
      subtitle_font_family: 'Word Shark (Black Italy)',
      subtitle_font_size: 54,
      subtitle_font_color: '#FFF7FF',
      subtitle_stroke_color: '#6E3A7D',
      subtitle_stroke_width: 2,
      subtitle_shadow_enabled: true,
      subtitle_shadow_color: '#30133E',
      subtitle_shadow_opacity: 0.36,
      subtitle_shadow_size: 3,
      subtitle_max_chars_per_line: 21,
      subtitle_max_lines: 2,
      subtitle_cover_enabled: true,
      subtitle_cover_color: '#5B2A86',
      subtitle_cover_opacity: 0.78,
      subtitle_cover_height_ratio: 0.12,
      subtitle_cover_padding_ratio: 0.03,
    },
  },
  {
    id: 'tech_aqua_iclkda',
    name: 'Tech aqua',
    description: 'Xanh điện tử, chữ sáng lạnh cho gadget và đồ công nghệ.',
    accentColor: '#41E6FF',
    previewText: 'Nét căng luôn',
    settings: {
      subtitle_style_custom_enabled: true,
      subtitle_font_family: 'ICL KDA',
      subtitle_font_size: 54,
      subtitle_font_color: '#D7FBFF',
      subtitle_stroke_color: '#021D28',
      subtitle_stroke_width: 3,
      subtitle_shadow_enabled: true,
      subtitle_shadow_color: '#41E6FF',
      subtitle_shadow_opacity: 0.45,
      subtitle_shadow_size: 3,
      subtitle_max_chars_per_line: 22,
      subtitle_max_lines: 2,
      subtitle_cover_enabled: true,
      subtitle_cover_color: '#05283C',
      subtitle_cover_opacity: 0.86,
      subtitle_cover_height_ratio: 0.12,
      subtitle_cover_padding_ratio: 0.035,
    },
  },
  {
    id: 'kitchen_cream_badiho',
    name: 'Kitchen cream',
    description: 'Kem xanh dịu cho đồ gia dụng, bếp, mẹ và bé, ít chói mắt.',
    accentColor: '#7BBF8E',
    previewText: 'Dùng tiện lắm',
    settings: {
      subtitle_style_custom_enabled: true,
      subtitle_font_family: 'Badiho Support',
      subtitle_font_size: 54,
      subtitle_font_color: '#F8FFE5',
      subtitle_stroke_color: '#07110B',
      subtitle_stroke_width: 3,
      subtitle_shadow_enabled: true,
      subtitle_shadow_color: '#7BBF8E',
      subtitle_shadow_opacity: 0.24,
      subtitle_shadow_size: 2,
      subtitle_max_chars_per_line: 22,
      subtitle_max_lines: 2,
      subtitle_cover_enabled: true,
      subtitle_cover_color: '#1E2A1F',
      subtitle_cover_opacity: 0.9,
      subtitle_cover_height_ratio: 0.12,
      subtitle_cover_padding_ratio: 0.03,
    },
  },
  {
    id: 'night_violet_reup',
    name: 'Night violet',
    description: 'Tím đêm hiện đại, che sub gốc tốt nhưng không quá nặng.',
    accentColor: '#A78BFA',
    previewText: 'Đáng xem nha',
    settings: {
      subtitle_style_custom_enabled: true,
      subtitle_font_family: 'Montserrat ExtraBold',
      subtitle_font_size: 56,
      subtitle_font_color: '#F4EEFF',
      subtitle_stroke_color: '#160A2E',
      subtitle_stroke_width: 3,
      subtitle_shadow_enabled: true,
      subtitle_shadow_color: '#000000',
      subtitle_shadow_opacity: 0.4,
      subtitle_shadow_size: 3,
      subtitle_max_chars_per_line: 22,
      subtitle_max_lines: 2,
      subtitle_cover_enabled: true,
      subtitle_cover_color: '#21123D',
      subtitle_cover_opacity: 0.84,
      subtitle_cover_height_ratio: 0.12,
      subtitle_cover_padding_ratio: 0.03,
    },
  },
  {
    id: 'soft_peach_story',
    name: 'Story peach',
    description: 'Hồng đào mềm, hợp video kể chuyện, beauty và daily review.',
    accentColor: '#FF7A90',
    previewText: 'Nhìn thích ghê',
    settings: {
      subtitle_style_custom_enabled: true,
      subtitle_font_family: 'SF Pro Display Heavy',
      subtitle_font_size: 54,
      subtitle_font_color: '#FFE9D6',
      subtitle_stroke_color: '#3A1020',
      subtitle_stroke_width: 3,
      subtitle_shadow_enabled: true,
      subtitle_shadow_color: '#FFFFFF',
      subtitle_shadow_opacity: 0.22,
      subtitle_shadow_size: 2,
      subtitle_max_chars_per_line: 21,
      subtitle_max_lines: 2,
      subtitle_cover_enabled: true,
      subtitle_cover_color: '#3A1020',
      subtitle_cover_opacity: 0.88,
      subtitle_cover_height_ratio: 0.12,
      subtitle_cover_padding_ratio: 0.03,
    },
  },
];

const VIETNAMESE_SUBTITLE_STYLE_PRESETS: VietnameseSubtitleStylePreset[] = [
  {
    id: 'basic_readable',
    name: 'Cơ bản, dễ đọc nhất',
    description: 'Chữ trắng, nền đen 60%, viền và bóng đen để đọc rõ trên hầu hết video.',
    accentColor: '#FFFFFF',
    previewText: 'Rõ dễ đọc',
    settings: {
      subtitle_style_custom_enabled: true,
      subtitle_font_family: 'Be Vietnam Pro',
      subtitle_font_size: 56,
      subtitle_font_color: '#FFFFFF',
      subtitle_stroke_color: '#000000',
      subtitle_stroke_width: 2,
      subtitle_shadow_enabled: true,
      subtitle_shadow_color: '#000000',
      subtitle_shadow_opacity: 0.45,
      subtitle_shadow_size: 5,
      subtitle_max_chars_per_line: 24,
      subtitle_max_lines: 2,
      subtitle_cover_enabled: true,
      subtitle_cover_mode: 'solid',
      subtitle_cover_color: '#000000',
      subtitle_cover_opacity: 0.6,
      subtitle_cover_height_ratio: 0.12,
      subtitle_cover_padding_ratio: 0.035,
      subtitle_cover_radius_ratio: 0.035,
    },
  },
  {
    id: 'review_tiktok_yellow',
    name: 'Sub vàng kiểu review/TikTok',
    description: 'Chữ vàng nổi bật, nền đen mờ để nhấn điểm hay, ưu đãi và thông số nhanh.',
    accentColor: '#FFE600',
    previewText: 'Đáng mua nha',
    settings: {
      subtitle_style_custom_enabled: true,
      subtitle_font_family: 'Montserrat',
      subtitle_font_size: 56,
      subtitle_font_color: '#FFE600',
      subtitle_stroke_color: '#000000',
      subtitle_stroke_width: 2,
      subtitle_shadow_enabled: true,
      subtitle_shadow_color: '#000000',
      subtitle_shadow_opacity: 0.5,
      subtitle_shadow_size: 5,
      subtitle_max_chars_per_line: 23,
      subtitle_max_lines: 2,
      subtitle_cover_enabled: true,
      subtitle_cover_mode: 'solid',
      subtitle_cover_color: '#000000',
      subtitle_cover_opacity: 0.55,
      subtitle_cover_height_ratio: 0.12,
      subtitle_cover_padding_ratio: 0.035,
      subtitle_cover_radius_ratio: 0.032,
    },
  },
  {
    id: 'clean_modern',
    name: 'Sạch, hiện đại',
    description: 'Chữ trắng trên nền xám than 72%, gọn và hiện đại cho video review chung.',
    accentColor: '#16181D',
    previewText: 'Sạch hiện đại',
    settings: {
      subtitle_style_custom_enabled: true,
      subtitle_font_family: 'Inter',
      subtitle_font_size: 54,
      subtitle_font_color: '#FFFFFF',
      subtitle_stroke_color: '#0A0A0A',
      subtitle_stroke_width: 2,
      subtitle_shadow_enabled: true,
      subtitle_shadow_color: '#000000',
      subtitle_shadow_opacity: 0.35,
      subtitle_shadow_size: 4,
      subtitle_max_chars_per_line: 24,
      subtitle_max_lines: 2,
      subtitle_cover_enabled: true,
      subtitle_cover_mode: 'solid',
      subtitle_cover_color: '#16181D',
      subtitle_cover_opacity: 0.72,
      subtitle_cover_height_ratio: 0.12,
      subtitle_cover_padding_ratio: 0.035,
      subtitle_cover_radius_ratio: 0.032,
    },
  },
  {
    id: 'sale_red',
    name: 'Nhấn giá/khuyến mãi',
    description: 'Nền đỏ sale, chữ trắng và viền đỏ đậm để làm nổi giá, deal và CTA.',
    accentColor: '#E63946',
    previewText: 'Giá tốt hôm nay',
    settings: {
      subtitle_style_custom_enabled: true,
      subtitle_font_family: 'Roboto Condensed',
      subtitle_font_size: 60,
      subtitle_font_color: '#FFFFFF',
      subtitle_stroke_color: '#78000A',
      subtitle_stroke_width: 2,
      subtitle_shadow_enabled: true,
      subtitle_shadow_color: '#000000',
      subtitle_shadow_opacity: 0.35,
      subtitle_shadow_size: 4,
      subtitle_max_chars_per_line: 22,
      subtitle_max_lines: 2,
      subtitle_cover_enabled: true,
      subtitle_cover_mode: 'solid',
      subtitle_cover_color: '#E63946',
      subtitle_cover_opacity: 1,
      subtitle_cover_height_ratio: 0.12,
      subtitle_cover_padding_ratio: 0.035,
      subtitle_cover_radius_ratio: 0.032,
    },
  },
  {
    id: 'beauty_skincare_pink',
    name: 'Review mỹ phẩm/skincare',
    description: 'Chữ xám mềm trên nền hồng pastel, hợp mỹ phẩm, skincare và làm đẹp.',
    accentColor: '#FFDDE8',
    previewText: 'Da mịn hơn',
    settings: {
      subtitle_style_custom_enabled: true,
      subtitle_font_family: 'Nunito Sans',
      subtitle_font_size: 54,
      subtitle_font_color: '#2D2D2D',
      subtitle_stroke_color: '#FFFFFF',
      subtitle_stroke_width: 1,
      subtitle_shadow_enabled: true,
      subtitle_shadow_color: '#000000',
      subtitle_shadow_opacity: 0.2,
      subtitle_shadow_size: 3,
      subtitle_max_chars_per_line: 24,
      subtitle_max_lines: 2,
      subtitle_cover_enabled: true,
      subtitle_cover_mode: 'solid',
      subtitle_cover_color: '#FFDDE8',
      subtitle_cover_opacity: 1,
      subtitle_cover_height_ratio: 0.12,
      subtitle_cover_padding_ratio: 0.035,
      subtitle_cover_radius_ratio: 0.04,
    },
  },
  {
    id: 'tech_ios_blue',
    name: 'Review đồ công nghệ',
    description: 'Nền xanh iOS, chữ trắng và viền xanh đậm cho điện thoại, máy tính, gadget.',
    accentColor: '#007AFF',
    previewText: 'Nét căng luôn',
    settings: {
      subtitle_style_custom_enabled: true,
      subtitle_font_family: 'Lexend',
      subtitle_font_size: 56,
      subtitle_font_color: '#FFFFFF',
      subtitle_stroke_color: '#002D78',
      subtitle_stroke_width: 2,
      subtitle_shadow_enabled: true,
      subtitle_shadow_color: '#000000',
      subtitle_shadow_opacity: 0.35,
      subtitle_shadow_size: 4,
      subtitle_max_chars_per_line: 24,
      subtitle_max_lines: 2,
      subtitle_cover_enabled: true,
      subtitle_cover_mode: 'solid',
      subtitle_cover_color: '#007AFF',
      subtitle_cover_opacity: 1,
      subtitle_cover_height_ratio: 0.12,
      subtitle_cover_padding_ratio: 0.035,
      subtitle_cover_radius_ratio: 0.033,
    },
  },
  {
    id: 'food_yellow_orange',
    name: 'Review đồ ăn',
    description: 'Nền vàng cam, chữ nâu đậm và viền trắng cho đồ ăn, bếp và lifestyle ấm áp.',
    accentColor: '#FFC72C',
    previewText: 'Ngon thật sự',
    settings: {
      subtitle_style_custom_enabled: true,
      subtitle_font_family: 'Mulish',
      subtitle_font_size: 56,
      subtitle_font_color: '#2D1E14',
      subtitle_stroke_color: '#FFFFFF',
      subtitle_stroke_width: 1,
      subtitle_shadow_enabled: true,
      subtitle_shadow_color: '#000000',
      subtitle_shadow_opacity: 0.25,
      subtitle_shadow_size: 3,
      subtitle_max_chars_per_line: 24,
      subtitle_max_lines: 2,
      subtitle_cover_enabled: true,
      subtitle_cover_mode: 'solid',
      subtitle_cover_color: '#FFC72C',
      subtitle_cover_opacity: 1,
      subtitle_cover_height_ratio: 0.12,
      subtitle_cover_padding_ratio: 0.035,
      subtitle_cover_radius_ratio: 0.038,
    },
  },
  {
    id: 'bright_background_float',
    name: 'Sub nổi trên nền sáng',
    description: 'Chữ đen mềm trên nền trắng mờ, hợp video nền sáng hoặc sản phẩm trắng.',
    accentColor: '#F8FAFC',
    previewText: 'Rõ từng chi tiết',
    settings: {
      subtitle_style_custom_enabled: true,
      subtitle_font_family: 'Inter',
      subtitle_font_size: 54,
      subtitle_font_color: '#141414',
      subtitle_stroke_color: '#FFFFFF',
      subtitle_stroke_width: 1,
      subtitle_shadow_enabled: true,
      subtitle_shadow_color: '#000000',
      subtitle_shadow_opacity: 0.18,
      subtitle_shadow_size: 2,
      subtitle_max_chars_per_line: 24,
      subtitle_max_lines: 2,
      subtitle_cover_enabled: true,
      subtitle_cover_mode: 'solid',
      subtitle_cover_color: '#FFFFFF',
      subtitle_cover_opacity: 0.78,
      subtitle_cover_height_ratio: 0.12,
      subtitle_cover_padding_ratio: 0.035,
      subtitle_cover_radius_ratio: 0.035,
    },
  },
];

const DEFAULT_SETTINGS: DouyinReupSettings = {
  enabled: true,
  preset_id: 'safe_review',
  preset_name: 'Safe Review',
  source_language: 'zh',
  target_language: 'vi',
  translation_style: 'sat_nghia_troi_chay',
  subtitle_position: 'bottom_overlay',
  translation_provider: 'gemini',
  subtitle_source_priority: ['sidecar_srt', 'embedded_subtitle', 'ocr_hardsub', 'asr'],
  use_sidecar_srt: true,
  use_embedded_subtitle: true,
  use_asr_if_no_subtitle: true,
  asr_provider: 'faster_whisper',
  asr_model_size: 'base',
  asr_device: 'auto',
  asr_vad_filter: true,
  asr_max_audio_seconds: 180,
  asr_subprocess_isolation: false,
  asr_timeout_seconds: 1200,
  asr_subtitle_offset_seconds: -0.25,
  use_ocr_if_asr_failed: true,
  use_ocr_if_no_subtitle: true,
  ocr_provider: 'easyocr',
  ocr_language: 'ch',
  ocr_sample_fps: 2.0,
  ocr_subprocess_isolation: false,
  ocr_timeout_seconds: 1200,
  ocr_region_mode: 'full_frame',
  ocr_manual_region: null,
  ocr_min_confidence: 0.35,
  ocr_dedupe_similarity: 0.86,
  ocr_min_text_length: 2,
  ocr_merge_gap_ms: 600,
  ocr_min_duration_ms: 500,
  ocr_max_duration_ms: 6000,
  ocr_filter_watermarks: true,
  ocr_watermark_terms: [],
  subtitle_quality_gate_enabled: true,
  asr_quality_min_blocks: 3,
  asr_quality_min_chars: 24,
  ocr_quality_min_blocks: 2,
  ocr_quality_min_chars: 16,
  subtitle_quality_min_coverage: 0.18,
  prefer_ocr_over_asr_when_text_visible: false,
  visual_style_preset_id: 'clean_review_light',
  burn_subtitle: true,
  add_overlay: false,
  overlay_mode: 'none',
  custom_overlay_path: 'examples/overlay',
  custom_overlay_height_percent: 100,
  custom_overlay_fit_mode: 'cover',
  subtitle_style_custom_enabled: false,
  subtitle_font_family: 'Arial',
  subtitle_font_size: 54,
  subtitle_font_color: '#FFFFFF',
  subtitle_stroke_color: '#000000',
  subtitle_stroke_width: 2,
  subtitle_shadow_enabled: true,
  subtitle_shadow_color: '#000000',
  subtitle_shadow_opacity: 0.35,
  subtitle_shadow_size: 2,
  subtitle_max_chars_per_line: 22,
  subtitle_max_lines: 2,
  subtitle_cover_enabled: true,
  subtitle_cover_mode: 'solid',
  subtitle_cover_blur_strength: 12,
  subtitle_cover_color: '#000000',
  subtitle_cover_opacity: 0.86,
  subtitle_cover_auto_position: true,
  subtitle_cover_probe_if_no_ocr: true,
  subtitle_cover_probe_sample_fps: 1,
  subtitle_cover_height_ratio: 0.12,
  subtitle_cover_bottom_ratio: 0,
  subtitle_cover_padding_ratio: 0.035,
  subtitle_cover_lead_seconds: 0.85,
  subtitle_cover_tail_seconds: 0.25,
  subtitle_cover_radius_ratio: 0.035,
  subtitle_cover_text_y_offset_ratio: 0,
  keep_original_audio: true,
  add_bgm: true,
  music_folder: '',
  favorite_music_paths: [],
  bgm_volume: 0.16,
  original_audio_volume: 0.85,
  reduce_original_voice: false,
  original_voice_reduction_strength: 0.65,
  original_voice_reduction_fallback_volume: 0.35,
  duck_bgm_when_voice: false,
  resolution: '1080x1920',
  fps: 30,
  process_mode: 'all',
  max_videos: null,
  selected_video_paths: [],
  source_selection_id: null,
  batch_performance_mode: 'safe',
  batch_chunk_size: 50,
  batch_ffmpeg_timeout_seconds: 900,
  batch_item_timeout_seconds: 1800,
  batch_watchdog_stale_minutes: 20,
  batch_pause_on_repeated_failures: true,
  batch_max_consecutive_failures: 10,
  keep_temp: false,
  review_subtitles_before_render: true,
  auto_render_after_translation: false,
  auto_mark_low_quality_lines: true,
  enable_subtitle_rewrite_suggestions: true,
  auto_generate_rewrite_for_flagged_lines: false,
  auto_apply_safe_rewrites: false,
  default_rewrite_style: 'short_natural',
  enable_silent_immersive_mode: true,
  silent_mode_detection: true,
  silent_mode_strategy: 'chill_immersive',
  detect_speech_presence: true,
  speech_detection_threshold: 0.35,
  auto_route_speech_to_voice_reup: true,
  auto_route_no_speech_to_silent_reup: true,
  auto_route_speech_threshold: 0.28,
  use_visual_segments_for_silent_video: true,
  silent_segment_duration_min: 1.2,
  silent_segment_duration_max: 4.0,
  generate_visual_captions: false,
  silent_visual_caption_min_product_confidence: 0.75,
  silent_visual_caption_min_segments: 3,
  silent_voiceover_max_duration_ratio: 0.85,
  visual_caption_language: 'vi',
  visual_caption_style: 'natural_short',
  silent_caption_tone: 'natural',
  generate_voiceover_for_silent_video: false,
  silent_voiceover_provider: 'edge_tts',
  silent_voiceover_voice: 'vi-VN-HoaiMyNeural',
  voiceover_auto_slow_video: true,
  voiceover_max_video_slowdown: 1.28,
  voiceover_comfort_speedup: 1.18,
  keep_immersive_original_audio: true,
  immersive_original_audio_volume: 0.75,
  add_bgm_for_silent_video: true,
  immersive_bgm_volume: 0.18,
  silent_review_before_render: true,
  product_context_lock_enabled: true,
  locked_product_name: null,
  locked_industry: null,
  locked_product_keywords: [],
};

const RECENT_SOURCE_KEY = 'auto-tool.recentSourceFolders';
const RECENT_OUTPUT_KEY = 'auto-tool.recentOutputFolders';
const RECENT_MUSIC_KEY = 'auto-tool.recentMusicFolders';
const LAST_PRESET_KEY = 'auto-tool.lastSelectedPreset';
const LAST_INDUSTRY_KEY = 'auto-tool.lastSelectedIndustry';
const LAST_TONE_KEY = 'auto-tool.lastSelectedTone';
const SAVED_REUP_SETTINGS_KEY = 'auto-tool.douyinReupSettings.v2';

function defaultProjectName(workflow: 'douyin' | 'silent'): string {
  const date = new Date().toISOString().slice(0, 10).replaceAll('-', '_');
  return workflow === 'silent' ? `silent_immersive_${date}` : `douyin_reup_${date}`;
}

function normalizeDouyinSettings(settings: Partial<DouyinReupSettings>): DouyinReupSettings {
  return { ...DEFAULT_SETTINGS, ...migrateDouyinSettings(settings) };
}

function migrateDouyinSettings(settings: Partial<DouyinReupSettings>): Partial<DouyinReupSettings> {
  const next = { ...settings };
  if (
    next.preset_id === 'voice_priority'
    && next.review_subtitles_before_render === true
    && next.auto_render_after_translation === false
  ) {
    next.review_subtitles_before_render = false;
    next.auto_render_after_translation = true;
  }
  return next;
}

function splitWatermarkTerms(value: string): string[] {
  return value.split(/[,;，\n]+/).map((item) => item.trim()).filter(Boolean);
}

function prioritizeOcrBeforeAsr(priority: string[]): string[] {
  const cleaned = priority.filter((source) => source !== 'ocr_hardsub');
  const asrIndex = cleaned.indexOf('asr');
  if (asrIndex >= 0) {
    cleaned.splice(asrIndex, 0, 'ocr_hardsub');
    return cleaned;
  }
  return [...cleaned, 'ocr_hardsub'];
}

function readSavedDouyinSettings(): Partial<DouyinReupSettings> {
  try {
    const raw = localStorage.getItem(SAVED_REUP_SETTINGS_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Partial<DouyinReupSettings>;
    if (!parsed || typeof parsed !== 'object') return {};
    return parsed;
  } catch {
    return {};
  }
}

function saveDouyinSettings(settings: DouyinReupSettings) {
  try {
    const {
      selected_video_paths: _selectedVideoPaths,
      source_selection_id: _sourceSelectionId,
      process_mode: _processMode,
      ...persisted
    } = settings;
    localStorage.setItem(SAVED_REUP_SETTINGS_KEY, JSON.stringify(persisted));
  } catch {
    // LocalStorage can be full or disabled; rendering must not depend on this convenience cache.
  }
}

function clearSavedDouyinSettings() {
  try {
    localStorage.removeItem(SAVED_REUP_SETTINGS_KEY);
  } catch {
    // Ignore browser storage errors.
  }
}

function readRecentFolders(key: string): StartRecentFolder[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || '[]') as string[];
    return parsed.filter(Boolean).slice(0, 5).map((path) => ({ id: path, path }));
  } catch {
    return [];
  }
}

function writeRecentFolders(key: string, folders: StartRecentFolder[]) {
  localStorage.setItem(key, JSON.stringify(folders.map((folder) => folder.path).slice(0, 5)));
}

function addRecentFolder(key: string, folders: StartRecentFolder[], path: string): StartRecentFolder[] {
  const trimmed = path.trim();
  if (!trimmed) return folders;
  const next = [{ id: trimmed, path: trimmed }, ...folders.filter((folder) => folder.path !== trimmed)].slice(0, 5);
  writeRecentFolders(key, next);
  return next;
}

function removeRecentFolder(key: string, folders: StartRecentFolder[], path: string): StartRecentFolder[] {
  const next = folders.filter((folder) => folder.path !== path);
  writeRecentFolders(key, next);
  return next;
}

function toRecentFolders(paths: string[]): StartRecentFolder[] {
  return paths.filter(Boolean).map((path) => ({ id: path, path }));
}

function parseRetryVideoIndexes(value: string | null): number[] {
  if (!value) return [];
  return [
    ...new Set(
      value
        .split(',')
        .map((item) => item.trim().toLowerCase())
        .map((item) => {
          const match = item.match(/(?:video_)?(\d+)/);
          return match ? Number.parseInt(match[1], 10) : 0;
        })
        .filter((index) => Number.isFinite(index) && index > 0),
    ),
  ];
}

export default function DouyinReupPage({ initialWorkflow = 'douyin' }: { initialWorkflow?: 'douyin' | 'silent' }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const workflowMode: StartWorkflowMode = initialWorkflow === 'silent' ? 'silent_immersive' : 'douyin_voice';
  const resumeJobId = searchParams.get('job_id') || searchParams.get('resume_job_id');
  const resumeVideoIdsParam = searchParams.get('video_ids');
  const resumeVideoIndexes = useMemo(() => parseRetryVideoIndexes(resumeVideoIdsParam), [resumeVideoIdsParam]);
  const [mode, setMode] = useState<'simple' | 'advanced'>('simple');
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [riskyConfirmOpen, setRiskyConfirmOpen] = useState(false);
  const [projectName, setProjectName] = useState(() => defaultProjectName(initialWorkflow));
  const [sourceFolder, setSourceFolder] = useState('');
  const [outputFolder, setOutputFolder] = useState(() => localStorage.getItem('auto-tool.default-output-folder') || './examples/outputs');
  const [settings, setSettings] = useState<DouyinReupSettings>(() => {
    const savedSettings = readSavedDouyinSettings();
    return normalizeDouyinSettings({
      ...savedSettings,
      music_folder: savedSettings.music_folder ?? localStorage.getItem('auto-tool.default-bgm-folder') ?? DEFAULT_SETTINGS.music_folder,
      silent_caption_tone: localStorage.getItem(LAST_TONE_KEY) || savedSettings.silent_caption_tone || DEFAULT_SETTINGS.silent_caption_tone,
      selected_video_paths: [],
      source_selection_id: null,
      process_mode: 'all',
    });
  });
  const [silentProductContext, setSilentProductContext] = useState<SilentProductContext>({
    product_name: '',
    industry: localStorage.getItem(LAST_INDUSTRY_KEY) || 'auto',
    features: '',
    cta: '',
  });
  const [presets, setPresets] = useState<DouyinReupPreset[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState(() => localStorage.getItem(LAST_PRESET_KEY) || (initialWorkflow === 'silent' ? 'silent_chill_immersive' : 'safe_review'));
  const [recommendation, setRecommendation] = useState<DouyinPresetRecommendationResponse | null>(null);
  const [visualStyles, setVisualStyles] = useState<VisualStylePreset[]>([]);
  const [videos, setVideos] = useState<DouyinVideoItem[]>([]);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [scanSummary, setScanSummary] = useState<StartScanSummary | null>(null);
  const [scanErrors, setScanErrors] = useState<string[]>([]);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [results, setResults] = useState<DouyinOutputResult[]>([]);
  const [summary, setSummary] = useState<DouyinReupSummary | null>(null);
  const [resultsTab, setResultsTab] = useState<'results' | 'final_qa'>('results');
  const [platformTarget, setPlatformTarget] = useState<PlatformTarget>('tiktok');
  const [exportPack, setExportPack] = useState<PlatformExportPack | null>(null);
  const [exportOutputIndexes, setExportOutputIndexes] = useState<number[]>([]);
  const [exportOptions, setExportOptions] = useState<ExportOptions>({
    copy_videos: true,
    include_subtitles: true,
    include_logs: true,
    include_captions: true,
    include_posting_checklist: true,
  });
  const [dependencyStatus, setDependencyStatus] = useState<SystemDependencyStatusResponse | null>(null);
  const [backendHealth, setBackendHealth] = useState<HealthResponse | null>(null);
  const [retryPresetByOutput, setRetryPresetByOutput] = useState<Record<number, string>>({});
  const [retryMode, setRetryMode] = useState<DouyinRetryCustomMode>('render_only');
  const [selectedResultIndexes, setSelectedResultIndexes] = useState<number[]>([]);
  const [loadedJobFromQuery, setLoadedJobFromQuery] = useState<string | null>(null);
  const [retryBusy, setRetryBusy] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [silentIndustries, setSilentIndustries] = useState<Array<{ id: string; name: string }>>([]);
  const [captionPreview, setCaptionPreview] = useState<SilentReupPlanResponse | null>(null);
  const [visualTagVocabulary, setVisualTagVocabulary] = useState<SilentVisualTagVocabulary>(DEFAULT_VISUAL_TAG_VOCABULARY);
  const [editingSegmentId, setEditingSegmentId] = useState<string | null>(null);
  const [recentSourceFolders, setRecentSourceFolders] = useState(() => readRecentFolders(RECENT_SOURCE_KEY));
  const [recentOutputFolders, setRecentOutputFolders] = useState(() => readRecentFolders(RECENT_OUTPUT_KEY));
  const [recentMusicFolders, setRecentMusicFolders] = useState(() => readRecentFolders(RECENT_MUSIC_KEY));
  const [subtitlePreviewVideoError, setSubtitlePreviewVideoError] = useState(false);

  const done = Boolean(jobStatus?.status && ['completed', 'completed_with_errors', 'completed_with_warnings', 'failed', 'cancelled', 'paused'].includes(jobStatus.status));
  const canStart = sourceFolder.trim() && outputFolder.trim() && !busy && (!jobStatus || done);
  const selectedSet = useMemo(() => new Set(selectedPaths), [selectedPaths]);
  const selectedResultVideoIds = useMemo(
    () => selectedResultIndexes.map((index) => `video_${index.toString().padStart(3, '0')}`),
    [selectedResultIndexes],
  );
  const subtitlePreviewVideo = useMemo(
    () => videos.find((video) => selectedSet.has(video.path)) || videos.find((video) => video.status === 'valid') || videos[0] || null,
    [selectedSet, videos],
  );
  const reviewDocuments = useMemo(() => results.filter((output) => output.subtitle_review_document_id), [results]);
  const failedResults = useMemo(() => results.filter((output) => output.status === 'failed'), [results]);
  const qaFailedResults = useMemo(() => results.filter((output) => output.final_output_qa?.status === 'failed'), [results]);
  const resultGroups = useMemo(
    () => [
      { title: 'Cần duyệt phụ đề trước khi render MP4', items: results.filter((output) => output.status === 'needs_review') },
      { title: 'Đã render MP4', items: results.filter((output) => output.status === 'success') },
      { title: 'Lỗi', items: results.filter((output) => output.status === 'failed') },
      {
        title: 'Bỏ qua',
        items: results.filter((output) => !['needs_review', 'success', 'failed'].includes(output.status)),
      },
    ],
    [results],
  );

  useEffect(() => {
    setSubtitlePreviewVideoError(false);
  }, [subtitlePreviewVideo?.path]);

  useEffect(() => {
    setSelectedResultIndexes((current) => {
      const available = new Set(results.map((output) => output.index));
      const next = current.filter((index) => available.has(index));
      return next.length === current.length ? current : next;
    });
  }, [results]);

  const reviewBeforeRender = workflowMode === 'silent_immersive' ? settings.silent_review_before_render : settings.review_subtitles_before_render;
  const usesManualSubtitleReview = reviewBeforeRender && !settings.auto_render_after_translation;
  const currentAutoRender = !usesManualSubtitleReview;
  const addMusicEnabled = workflowMode === 'silent_immersive' ? settings.add_bgm_for_silent_video : settings.add_bgm;
  const isSilentPreset =
    selectedPresetId.startsWith('silent_') || Boolean(settings.enable_silent_immersive_mode && settings.preset_id?.startsWith('silent_'));
  const normalPresets = useMemo(() => presets.filter((preset) => !preset.id.startsWith('silent_')), [presets]);
  const silentPresets = useMemo(() => presets.filter((preset) => preset.id.startsWith('silent_')), [presets]);
  const selectedPreset = useMemo(() => presets.find((preset) => preset.id === selectedPresetId), [presets, selectedPresetId]);
  const recommendedPresetId = useMemo(
    () => pickRecommendedPresetId(workflowMode, sourceFolder, recommendation, presets),
    [workflowMode, sourceFolder, recommendation, presets],
  );
  const startPresetCards = useMemo(
    () => (workflowMode === 'silent_immersive' ? silentPresets : normalPresets).map((preset) => toStartPresetViewModel(preset, workflowMode, preset.id === recommendedPresetId)),
    [normalPresets, recommendedPresetId, silentPresets, workflowMode],
  );
  const selectedPresetCard = useMemo(
    () => startPresetCards.find((preset) => preset.id === selectedPresetId),
    [selectedPresetId, startPresetCards],
  );
  const workflowPreviewPreset = selectedPresetCard
    ? { ...selectedPresetCard, autoRender: currentAutoRender, reviewRequired: usesManualSubtitleReview }
    : undefined;
  const recommendedPresetCard = useMemo(
    () => startPresetCards.find((preset) => preset.id === recommendedPresetId),
    [recommendedPresetId, startPresetCards],
  );
  const checklist = useMemo(
    () => buildChecklist({
      sourceFolder,
      outputFolder,
      selectedPreset: selectedPresetCard,
      scanSummary,
      scanErrors,
      musicFolder: settings.music_folder || '',
      addMusic: addMusicEnabled,
      backendReady: dependencyStatus !== null,
      backendHealth,
      translationProvider: settings.translation_provider,
      voiceoverEnabled: settings.generate_voiceover_for_silent_video,
      voiceProvider: settings.silent_voiceover_provider,
      autoRender: currentAutoRender,
    }),
    [
      addMusicEnabled,
      backendHealth,
      currentAutoRender,
      dependencyStatus,
      outputFolder,
      scanErrors,
      scanSummary,
      selectedPresetCard,
      settings.generate_voiceover_for_silent_video,
      settings.music_folder,
      settings.silent_voiceover_provider,
      settings.translation_provider,
      sourceFolder,
    ],
  );
  const validationMessages = useMemo(
    () => buildValidationMessages(checklist, selectedPresetCard, dependencyStatus, scanSummary, currentAutoRender),
    [checklist, currentAutoRender, dependencyStatus, scanSummary, selectedPresetCard],
  );
  const startDisabled = busy || checklist.some((item) => item.status === 'missing') || Boolean(jobStatus && !done);
  const riskyPreset = Boolean(currentAutoRender && selectedPresetId !== 'silent_chill_immersive');
  const jobStartedView: JobStartedView | null = jobId ? { jobId, projectName: projectName.trim() || defaultProjectName(initialWorkflow), jobStatus } : null;

  useEffect(() => {
    const savedSettings = readSavedDouyinSettings();
    const hasSavedSettings = Object.keys(savedSettings).length > 0;
    getLocalAppConfig()
      .then((config) => {
        if (!localStorage.getItem('auto-tool.default-output-folder')) setOutputFolder(config.default_output_folder);
        if (!localStorage.getItem('auto-tool.default-bgm-folder') && config.default_music_folder) {
          setSettings((current) => {
            if (current.music_folder) return current;
            const next = { ...current, music_folder: config.default_music_folder };
            saveDouyinSettings(next);
            return next;
          });
        }
        setSourceFolder((current) => current || config.default_source_folder);
      })
      .catch(() => undefined);
    getRecentPaths()
      .then((recent) => {
        const hasBackendRecents = recent.source_folders.length || recent.output_folders.length || recent.music_folders.length;
        if (hasBackendRecents) applyBackendRecentPaths(recent);
      })
      .catch(() => undefined);
    getPresets()
      .then((loadedPresets) => {
        setPresets(loadedPresets);
        const savedPresetId = localStorage.getItem(LAST_PRESET_KEY);
        const savedPreset = savedPresetId
          ? loadedPresets.find((preset) => preset.id === savedPresetId && (initialWorkflow === 'silent' ? preset.id.startsWith('silent_') : !preset.id.startsWith('silent_')))
          : null;
        const defaultPreset = initialWorkflow === 'silent'
          ? loadedPresets.find((preset) => preset.id === 'silent_chill_immersive')
          : loadedPresets.find((preset) => preset.is_default) ?? loadedPresets[0];
        const selectedPreset = savedPreset ?? defaultPreset;
        if (selectedPreset) {
          setSelectedPresetId(selectedPreset.id);
          if (!hasSavedSettings && !resumeJobId) {
            const next = normalizeDouyinSettings({
              ...selectedPreset.settings,
              music_folder: localStorage.getItem('auto-tool.default-bgm-folder') || DEFAULT_SETTINGS.music_folder,
              silent_caption_tone: localStorage.getItem(LAST_TONE_KEY) || selectedPreset.settings.silent_caption_tone,
            });
            saveDouyinSettings(next);
            setSettings(next);
          }
        }
      })
      .catch(() => setPresets([]));
    getVisualStyles()
      .then((response) => setVisualStyles(response.presets))
      .catch(() => setVisualStyles([]));
    getHealth()
      .then(setDependencyStatus)
      .catch(() => setDependencyStatus(null));
    getBackendHealth()
      .then(setBackendHealth)
      .catch(() => setBackendHealth(null));
    listSilentCaptionIndustries()
      .then((response) => setSilentIndustries(response.items))
      .catch(() => setSilentIndustries(DEFAULT_SILENT_INDUSTRIES));
    getSilentVisualTagVocabulary()
      .then(setVisualTagVocabulary)
      .catch(() => setVisualTagVocabulary(DEFAULT_VISUAL_TAG_VOCABULARY));
  }, [initialWorkflow, resumeJobId]);

  useEffect(() => {
    if (!resumeJobId || loadedJobFromQuery === resumeJobId) return;
    const targetJobId = resumeJobId;
    let cancelled = false;

    async function loadResumeJob() {
      setBusy(true);
      setError(null);
      try {
        const status = await getJobStatus(targetJobId);
        if (cancelled) return;
        setLoadedJobFromQuery(targetJobId);
        setJobId(targetJobId);
        setJobStatus(status);
        setMode('advanced');
        setAdvancedOpen(true);
        setResultsTab('results');

        if (status.project_id) {
          const project = await getProject(status.project_id).catch(() => null);
          if (project && !cancelled) {
            setProjectName(project.config.project_name || projectName);
            setSourceFolder(project.config.source_folder || '');
            setOutputFolder(project.config.output_folder || outputFolder);
            if (project.config.douyin_reup) {
              const restoredSettings = normalizeDouyinSettings({
                ...project.config.douyin_reup,
                selected_video_paths: [],
                process_mode: 'all',
              });
              setSettings(restoredSettings);
              saveDouyinSettings(restoredSettings);
            }
          }
        }

        await loadResults(targetJobId);
        if (resumeVideoIndexes.length) {
          setSelectedResultIndexes(resumeVideoIndexes);
          setResultsTab('results');
        }
        if (!cancelled) {
          setActionMessage(
            resumeVideoIndexes.length
              ? `Đã mở lại lô cũ và chọn sẵn ${resumeVideoIndexes.length} video. Chỉnh cài đặt xong hãy bấm “Render lại đã chọn”.`
              : 'Đã mở lại lô cũ. Bạn có thể chỉnh cài đặt nâng cao, chọn video cần xử lý lại rồi bấm chạy tiếp.',
          );
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Không thể mở lại lô cũ để chỉnh cài đặt.');
        }
      } finally {
        if (!cancelled) setBusy(false);
      }
    }

    void loadResumeJob();
    return () => {
      cancelled = true;
    };
  }, [loadedJobFromQuery, outputFolder, projectName, resumeJobId, resumeVideoIndexes]);

  function applyBackendRecentPaths(recent: LocalRecentPaths) {
    const source = toRecentFolders(recent.source_folders);
    const output = toRecentFolders(recent.output_folders);
    const music = toRecentFolders(recent.music_folders);
    setRecentSourceFolders(source);
    setRecentOutputFolders(output);
    setRecentMusicFolders(music);
    writeRecentFolders(RECENT_SOURCE_KEY, source);
    writeRecentFolders(RECENT_OUTPUT_KEY, output);
    writeRecentFolders(RECENT_MUSIC_KEY, music);
  }

  function syncRecentPath(kind: 'source' | 'output' | 'music', path: string) {
    const action = kind === 'source'
      ? addRecentSourceFolder(path)
      : kind === 'output'
        ? addRecentOutputFolder(path)
        : addRecentMusicFolder(path);
    action.then(applyBackendRecentPaths).catch(() => undefined);
  }

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
    setScanErrors([]);
    setResults([]);
    setSummary(null);
    try {
      const response = await scanDouyinFolder(sourceFolder);
      setVideos(response.media);
      setSelectedPaths([]);
      setScanSummary(summarizeStartScan(response.media, response.total_files, response.valid_videos, response.invalid_files));
      setRecentSourceFolders((current) => addRecentFolder(RECENT_SOURCE_KEY, current, sourceFolder));
      syncRecentPath('source', sourceFolder);
      recommendDouyinReupPreset(sourceFolder)
        .then(setRecommendation)
        .catch(() => setRecommendation(null));
      if (response.errors.length) {
        setScanErrors(['Không thể scan folder này. Vui lòng kiểm tra đường dẫn hoặc quyền truy cập.', ...response.errors.slice(0, 2)]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể scan thư mục Douyin.');
      setScanErrors(['Không thể scan folder này. Vui lòng kiểm tra đường dẫn hoặc quyền truy cập.']);
    } finally {
      setBusy(false);
    }
  }

  async function handlePresetSelect(presetId: string) {
    setSelectedPresetId(presetId);
    localStorage.setItem(LAST_PRESET_KEY, presetId);
    setError(null);
    try {
      const response = await applyDouyinReupPreset({
        preset_id: presetId,
        current_settings: settings,
      });
      const next = normalizeDouyinSettings(response.settings);
      saveDouyinSettings(next);
      setSettings(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể áp dụng preset.');
    }
  }

  async function handleOneClickStart() {
    setBusy(true);
    setError(null);
    setResults([]);
    setSummary(null);
    try {
      const processMode: 'selected' | 'first_n' | 'all_videos' = selectedPaths.length ? 'selected' : settings.max_videos ? 'first_n' : 'all_videos';
      setRecentSourceFolders((current) => addRecentFolder(RECENT_SOURCE_KEY, current, sourceFolder));
      setRecentOutputFolders((current) => addRecentFolder(RECENT_OUTPUT_KEY, current, outputFolder));
      syncRecentPath('source', sourceFolder);
      syncRecentPath('output', outputFolder);
      if (settings.music_folder?.trim()) {
        setRecentMusicFolders((current) => addRecentFolder(RECENT_MUSIC_KEY, current, settings.music_folder || ''));
        syncRecentPath('music', settings.music_folder || '');
      }
      const productContext = buildSilentProductContext(silentProductContext);
      const audioOverrides = buildAudioOverrides();
      const subtitleSourceOverrides = buildSubtitleSourceOverrides();
      const silentAutoRender = settings.auto_render_after_translation || selectedPresetId === 'silent_sales_recut';
      const response = initialWorkflow === 'silent'
        ? await startSilentOneClick({
            project_name: projectName.trim() || 'silent-reup',
            source_folder: sourceFolder,
            output_folder: outputFolder,
            strategy: settings.silent_mode_strategy || strategyFromSilentPreset(selectedPresetId),
            bgm_folder: settings.music_folder?.trim() || null,
            visual_style_preset_id: settings.visual_style_preset_id,
            process_mode: processMode,
            max_videos: settings.max_videos,
            selected_video_paths: selectedPaths,
            review_before_render: Boolean(settings.silent_review_before_render && !silentAutoRender),
            product_context: productContext,
            advanced_overrides: {
              ...audioOverrides,
              ...subtitleSourceOverrides,
              silent_caption_tone: settings.silent_caption_tone,
            },
          })
        : await startDouyinOneClick({
        project_name: projectName.trim() || 'douyin-reup',
        source_folder: sourceFolder,
        output_folder: outputFolder,
        preset_id: selectedPresetId,
        bgm_folder: settings.music_folder?.trim() || null,
        visual_style_preset_id: settings.visual_style_preset_id,
        process_mode: processMode,
        max_videos: settings.max_videos,
        selected_video_paths: selectedPaths,
        review_subtitles_before_render: settings.review_subtitles_before_render,
        auto_render_after_translation: settings.auto_render_after_translation,
            product_context: productContext,
        advanced_overrides: {
          ...audioOverrides,
          ...subtitleSourceOverrides,
          ...(mode === 'advanced' ? settings : {}),
          silent_caption_tone: settings.silent_caption_tone,
        },
          });
      setJobId(response.job_id);
      setJobStatus({
        job_id: response.job_id,
        status: response.status,
        current_step: 'queued',
        progress: 0,
        total_outputs: response.total_outputs,
        completed_outputs: 0,
        failed_outputs: 0,
        logs: [],
      });
      setActionMessage('Batch đã bắt đầu. Bạn có thể xem tiến trình hoặc mở kết quả khi job hoàn tất.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể bắt đầu one-click batch.');
    } finally {
      setBusy(false);
    }
  }

  async function handleStart() {
    setBusy(true);
    setError(null);
    setResults([]);
    setSummary(null);
    try {
      const processSettings: DouyinReupSettings = {
        ...settings,
        enabled: true,
        music_folder: settings.music_folder?.trim() || null,
        process_mode: selectedPaths.length ? 'selected' : settings.max_videos ? 'first_n' : 'all',
        selected_video_paths: selectedPaths,
      };
      setRecentSourceFolders((current) => addRecentFolder(RECENT_SOURCE_KEY, current, sourceFolder));
      setRecentOutputFolders((current) => addRecentFolder(RECENT_OUTPUT_KEY, current, outputFolder));
      syncRecentPath('source', sourceFolder);
      syncRecentPath('output', outputFolder);
      if (settings.music_folder?.trim()) {
        setRecentMusicFolders((current) => addRecentFolder(RECENT_MUSIC_KEY, current, settings.music_folder || ''));
        syncRecentPath('music', settings.music_folder || '');
      }
      const response = await startDouyinReupProcess({
        project_name: projectName.trim() || 'douyin-reup',
        source_folder: sourceFolder,
        output_folder: outputFolder,
        settings: processSettings,
        selected_video_paths: selectedPaths,
        source_selection_id: settings.source_selection_id,
        product_context: buildSilentProductContext(silentProductContext),
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
      setActionMessage('Batch đã bắt đầu. Bạn có thể xem tiến trình hoặc mở kết quả khi job hoàn tất.');
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
      setSummary(response.summary ?? null);
      setExportOutputIndexes(response.outputs.filter((output) => Boolean(output.path)).map((output) => output.index));
      getDouyinExportPack(targetJobId)
        .then((packResponse) => setExportPack(packResponse.export_pack))
        .catch(() => setExportPack(null));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải kết quả Douyin Reup.');
    }
  }

  function toggleSelected(path: string) {
    setSelectedPaths((current) => (current.includes(path) ? current.filter((item) => item !== path) : [...current, path]));
  }

  function updateSettings(updates: Partial<DouyinReupSettings>) {
    if (typeof updates.silent_caption_tone === 'string') {
      localStorage.setItem(LAST_TONE_KEY, updates.silent_caption_tone);
    }
    setSettings((current) => {
      const next = { ...current, ...updates };
      saveDouyinSettings(next);
      return next;
    });
  }

  function updateSilentProductContext(updates: Partial<SilentProductContext>) {
    if (typeof updates.industry === 'string') {
      localStorage.setItem(LAST_INDUSTRY_KEY, updates.industry);
    }
    setSilentProductContext((current) => ({ ...current, ...updates }));
  }

  function updateRenderFlow(renderMode: 'review' | 'auto', advanced = false) {
    const review = renderMode === 'review';
    const updates: Partial<DouyinReupSettings> = {
      review_subtitles_before_render: review,
      silent_review_before_render: review,
      auto_render_after_translation: !review,
    };
    if (advanced) {
      updateAdvancedSettings(updates);
      return;
    }
    updateSettings(updates);
  }

  function buildAudioOverrides(): Record<string, unknown> {
    return {
      add_bgm: settings.add_bgm,
      add_bgm_for_silent_video: settings.add_bgm_for_silent_video,
      bgm_volume: settings.bgm_volume,
      immersive_bgm_volume: settings.immersive_bgm_volume,
      original_audio_volume: settings.original_audio_volume,
      immersive_original_audio_volume: settings.immersive_original_audio_volume,
      keep_original_audio: settings.keep_original_audio,
      keep_immersive_original_audio: settings.keep_immersive_original_audio,
      reduce_original_voice: settings.reduce_original_voice,
      original_voice_reduction_strength: settings.original_voice_reduction_strength,
      original_voice_reduction_fallback_volume: settings.original_voice_reduction_fallback_volume,
      subtitle_style_custom_enabled: settings.subtitle_style_custom_enabled,
      subtitle_font_family: settings.subtitle_font_family,
      subtitle_font_size: settings.subtitle_font_size,
      subtitle_font_color: settings.subtitle_font_color,
      subtitle_stroke_color: settings.subtitle_stroke_color,
      subtitle_stroke_width: settings.subtitle_stroke_width,
      subtitle_shadow_enabled: settings.subtitle_shadow_enabled,
      subtitle_shadow_color: settings.subtitle_shadow_color,
      subtitle_shadow_opacity: settings.subtitle_shadow_opacity,
      subtitle_shadow_size: settings.subtitle_shadow_size,
      subtitle_max_chars_per_line: settings.subtitle_max_chars_per_line,
      subtitle_max_lines: settings.subtitle_max_lines,
      subtitle_cover_enabled: settings.subtitle_cover_enabled,
      subtitle_cover_mode: settings.subtitle_cover_mode,
      subtitle_cover_blur_strength: settings.subtitle_cover_blur_strength,
      subtitle_cover_color: settings.subtitle_cover_color,
      subtitle_cover_opacity: settings.subtitle_cover_opacity,
      subtitle_cover_auto_position: settings.subtitle_cover_auto_position,
      subtitle_cover_probe_if_no_ocr: settings.subtitle_cover_probe_if_no_ocr,
      subtitle_cover_probe_sample_fps: settings.subtitle_cover_probe_sample_fps,
      subtitle_cover_height_ratio: settings.subtitle_cover_height_ratio,
      subtitle_cover_bottom_ratio: settings.subtitle_cover_bottom_ratio,
      subtitle_cover_padding_ratio: settings.subtitle_cover_padding_ratio,
      subtitle_cover_lead_seconds: settings.subtitle_cover_lead_seconds,
      subtitle_cover_tail_seconds: settings.subtitle_cover_tail_seconds,
      subtitle_cover_radius_ratio: settings.subtitle_cover_radius_ratio,
      subtitle_cover_text_y_offset_ratio: settings.subtitle_cover_text_y_offset_ratio,
      add_overlay: settings.add_overlay,
      overlay_mode: settings.overlay_mode,
      generate_voiceover_for_silent_video: settings.generate_voiceover_for_silent_video,
      silent_voiceover_provider: settings.silent_voiceover_provider,
      silent_voiceover_voice: settings.silent_voiceover_voice,
      voiceover_auto_slow_video: settings.voiceover_auto_slow_video,
      voiceover_max_video_slowdown: settings.voiceover_max_video_slowdown,
      voiceover_comfort_speedup: settings.voiceover_comfort_speedup,
      auto_route_speech_to_voice_reup: settings.auto_route_speech_to_voice_reup,
      auto_route_no_speech_to_silent_reup: settings.auto_route_no_speech_to_silent_reup,
      auto_route_speech_threshold: settings.auto_route_speech_threshold,
      asr_max_audio_seconds: settings.asr_max_audio_seconds,
      batch_performance_mode: settings.batch_performance_mode,
      batch_chunk_size: settings.batch_chunk_size,
      batch_ffmpeg_timeout_seconds: settings.batch_ffmpeg_timeout_seconds,
      batch_item_timeout_seconds: settings.batch_item_timeout_seconds,
      batch_watchdog_stale_minutes: settings.batch_watchdog_stale_minutes,
      batch_pause_on_repeated_failures: settings.batch_pause_on_repeated_failures,
      batch_max_consecutive_failures: settings.batch_max_consecutive_failures,
      keep_temp: settings.keep_temp,
    };
  }

  function buildSubtitleSourceOverrides(): Record<string, unknown> {
    return {
      subtitle_source_priority: settings.subtitle_source_priority,
      use_sidecar_srt: settings.use_sidecar_srt,
      use_embedded_subtitle: settings.use_embedded_subtitle,
      use_asr_if_no_subtitle: settings.use_asr_if_no_subtitle,
      asr_vad_filter: settings.asr_vad_filter,
      asr_max_audio_seconds: settings.asr_max_audio_seconds,
      asr_subtitle_offset_seconds: settings.asr_subtitle_offset_seconds,
      use_ocr_if_asr_failed: settings.use_ocr_if_asr_failed,
      use_ocr_if_no_subtitle: settings.use_ocr_if_no_subtitle,
      ocr_provider: settings.ocr_provider,
      ocr_language: settings.ocr_language,
      ocr_sample_fps: settings.ocr_sample_fps,
      ocr_subprocess_isolation: settings.ocr_subprocess_isolation,
      ocr_timeout_seconds: settings.ocr_timeout_seconds,
      ocr_region_mode: settings.ocr_region_mode,
      ocr_manual_region: settings.ocr_manual_region,
      ocr_min_confidence: settings.ocr_min_confidence,
      ocr_dedupe_similarity: settings.ocr_dedupe_similarity,
      ocr_min_text_length: settings.ocr_min_text_length,
      ocr_merge_gap_ms: settings.ocr_merge_gap_ms,
      ocr_min_duration_ms: settings.ocr_min_duration_ms,
      ocr_max_duration_ms: settings.ocr_max_duration_ms,
      ocr_filter_watermarks: settings.ocr_filter_watermarks,
      ocr_watermark_terms: settings.ocr_watermark_terms,
      prefer_ocr_over_asr_when_text_visible: settings.prefer_ocr_over_asr_when_text_visible,
    };
  }

  function updateVoiceChoice(value: string) {
    const match = VIETNAMESE_TTS_VOICES.find((item) => `${item.provider}:${item.voice}` === value);
    if (!match) {
      const [provider, ...voiceParts] = value.split(':');
      const voice = voiceParts.join(':');
      if (!provider || !voice) return;
      updateSettings({
        silent_voiceover_provider: provider,
        silent_voiceover_voice: voice,
      });
      return;
    }
    updateSettings({
      silent_voiceover_provider: match.provider,
      silent_voiceover_voice: match.voice,
    });
  }

  function updateVoiceoverEnabled(value: boolean) {
    if (workflowMode === 'douyin_voice') {
      updateSettings({
        generate_voiceover_for_silent_video: value,
        keep_original_audio: !value,
        original_audio_volume: value ? 0.18 : DEFAULT_SETTINGS.original_audio_volume,
      });
      return;
    }
    updateSettings({ generate_voiceover_for_silent_video: value });
  }

  async function browseSourceFolder() {
    const path = await browseStartFolder('Chọn folder video', sourceFolder);
    if (path) setSourceFolder(path);
  }

  async function browseOutputFolder() {
    const path = await browseStartFolder('Chọn thư mục đầu ra', outputFolder);
    if (path) {
      setOutputFolder(path);
      setRecentOutputFolders((current) => addRecentFolder(RECENT_OUTPUT_KEY, current, path));
      syncRecentPath('output', path);
    }
  }

  async function browseMusicFolder() {
    const path = await browseStartFolder('Chọn music folder', settings.music_folder || '');
    if (path) {
      updateSettings({ music_folder: path });
      setRecentMusicFolders((current) => addRecentFolder(RECENT_MUSIC_KEY, current, path));
      syncRecentPath('music', path);
    }
  }

  async function browseCustomOverlay(mode: 'file' | 'folder') {
    setError(null);
    try {
      const response = await browsePath({
        mode,
        title: mode === 'file' ? 'Chọn ảnh overlay custom' : 'Chọn thư mục overlay custom',
        initial_path: settings.custom_overlay_path || 'examples/overlay',
        extensions: mode === 'file' ? ['.png', '.jpg', '.jpeg', '.webp'] : [],
      });
      if (!response.cancelled && response.path) {
        updateAdvancedSettings({
          add_overlay: true,
          overlay_mode: 'custom',
          custom_overlay_path: response.path,
          custom_overlay_height_percent: settings.custom_overlay_height_percent ?? 100,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể mở hộp thoại chọn overlay custom.');
    }
  }

  function requestStart() {
    if (riskyPreset) {
      setRiskyConfirmOpen(true);
      return;
    }
    void startCurrentWorkflow();
  }

  async function startCurrentWorkflow() {
    setRiskyConfirmOpen(false);
    await (mode === 'simple' ? handleOneClickStart() : handleStart());
  }

  async function handleGenerateCaptionPreview() {
    const videoPath = selectedPaths[0] || videos.find((video) => video.status === 'valid')?.path;
    if (!videoPath) {
      setError('Hãy scan thư mục và chọn ít nhất một video để tạo caption preview.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await buildSilentReupPlan({
        video_path: videoPath,
        settings: {
          ...settings,
          silent_caption_tone: settings.silent_caption_tone,
        },
        product_context: buildSilentProductContext(silentProductContext),
      });
      setCaptionPreview(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo caption preview.');
    } finally {
      setBusy(false);
    }
  }

  async function handleRegenerateCaptionPreview() {
    if (!captionPreview) return;
    setBusy(true);
    setError(null);
    try {
      const response = await regenerateSilentReupCaptions(captionPreview.plan_id, {
        industry: silentProductContext.industry,
        tone: settings.silent_caption_tone,
        strategy: settings.silent_mode_strategy,
        use_visual_tags: true,
        respect_user_tag_overrides: true,
      });
      setCaptionPreview(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo lại captions.');
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveSegmentTags(segmentId: string, payload: {
    tags: string[];
    primary_industry: string | null;
    primary_scene: string | null;
    primary_action: string | null;
  }) {
    if (!captionPreview) return;
    setBusy(true);
    setError(null);
    try {
      const response = await updateSilentSegmentVisualTags(captionPreview.plan_id, segmentId, payload);
      setCaptionPreview(response);
      setEditingSegmentId(null);
      setActionMessage(`Updated visual tags for ${segmentId}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể lưu visual tags.');
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateCaptionReviewDocument() {
    if (!captionPreview) return;
    setBusy(true);
    setError(null);
    try {
      const response = await createSilentReupReviewDocument(captionPreview.plan_id);
      navigate(`/subtitle-review/${response.document_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo review document.');
    } finally {
      setBusy(false);
    }
  }

  async function handleRunFinalQA() {
    if (!jobId) return;
    setBusy(true);
    setError(null);
    setActionMessage(null);
    try {
      const response = await runFinalOutputQAForJob(jobId, platformTarget);
      await loadResults(jobId);
      setResultsTab('final_qa');
      setActionMessage(`Đã kiểm tra chất lượng ${response.summary.total_checked} video.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể kiểm tra chất lượng video.');
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateExportPack() {
    if (!jobId) return;
    setBusy(true);
    setError(null);
    setActionMessage(null);
    try {
      const response = await createDouyinExportPack(jobId, {
        platform_target: platformTarget,
        output_dir: null,
        ...exportOptions,
        output_indexes: exportOutputIndexes,
      });
      setExportPack(response.export_pack);
      await loadResults(jobId);
      setActionMessage(`Đã tạo gói xuất bản: ${response.export_pack.output_dir}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo gói xuất bản.');
    } finally {
      setBusy(false);
    }
  }

  async function handleOpenExportPack() {
    if (!jobId) return;
    try {
      await openDouyinExportPack(jobId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open export pack folder.');
    }
  }

  function toggleExportOutput(index: number) {
    setExportOutputIndexes((current) => current.includes(index) ? current.filter((item) => item !== index) : [...current, index]);
  }

  function updateOcrManualRegion(key: 'x' | 'y' | 'width' | 'height', value: number) {
    setSettings((current) => {
      const next = {
        ...current,
        ocr_manual_region: {
          x: current.ocr_manual_region?.x ?? 0,
          y: current.ocr_manual_region?.y ?? 1200,
          width: current.ocr_manual_region?.width ?? 1080,
          height: current.ocr_manual_region?.height ?? 500,
          [key]: value,
        },
      };
      saveDouyinSettings(next);
      return next;
    });
  }

  function toggleResultIndex(index: number) {
    setSelectedResultIndexes((current) => (current.includes(index) ? current.filter((item) => item !== index) : [...current, index]));
  }

  function selectFailedOrQaResults() {
    const indexes = [
      ...new Set(
        results
          .filter((output) => output.status === 'failed' || output.final_output_qa?.status === 'failed')
          .map((output) => output.index),
      ),
    ];
    setSelectedResultIndexes(indexes);
  }

  function prioritizeOcrBeforeAsrForRetry(priority: string[]) {
    const cleaned = priority.filter((item) => item !== 'ocr_hardsub');
    const asrIndex = cleaned.indexOf('asr');
    if (asrIndex >= 0) cleaned.splice(asrIndex, 0, 'ocr_hardsub');
    else cleaned.push('ocr_hardsub');
    return cleaned;
  }

  function buildCustomRetrySettings(mode: DouyinRetryCustomMode): Partial<DouyinReupSettings> {
    const next: Partial<DouyinReupSettings> = {
      ...settings,
      enabled: true,
      review_subtitles_before_render: false,
      silent_review_before_render: false,
      auto_render_after_translation: true,
      music_folder: settings.music_folder?.trim() || null,
    };
    if (mode === 'read_screen_text') {
      next.use_ocr_if_no_subtitle = true;
      next.use_ocr_if_asr_failed = true;
      next.prefer_ocr_over_asr_when_text_visible = true;
      next.ocr_region_mode = settings.ocr_region_mode || 'full_frame';
      next.subtitle_source_priority = prioritizeOcrBeforeAsrForRetry(settings.subtitle_source_priority || []);
    }
    return next;
  }

  async function handleCustomRetry(mode: DouyinRetryCustomMode, videoIds: string[], includeUnfinished: boolean) {
    if (!jobId) return;
    if (retryBusy) return;
    if (!includeUnfinished && !videoIds.length) {
      setError('Hãy chọn ít nhất một video trong danh sách kết quả để render lại.');
      return;
    }
    setRetryBusy(true);
    setError(null);
    try {
      const response = await retryDouyinReupJobCustom(jobId, {
        retry_mode: mode,
        video_ids: videoIds,
        include_unfinished: includeUnfinished,
        settings: buildCustomRetrySettings(mode),
      });
      const modeLabel = CUSTOM_RETRY_MODE_OPTIONS.find((option) => option.value === mode)?.label || 'Chạy lại';
      emitNotification({
        variant: 'success',
        title: 'Đã đưa vào hàng đợi',
        message: `${modeLabel}: ${response.retry_outputs} video.`,
      });
      navigate(`/queue/douyin-reup/${response.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo lô chạy lại với cài đặt hiện tại.');
    } finally {
      setRetryBusy(false);
    }
  }

  async function handleRetryFailed() {
    if (!jobId || !failedResults.length) return;
    setBusy(true);
    setError(null);
    try {
      const response = await retryFailedDouyinReupJob(jobId, {
        retry_steps: ['asr', 'translation', 'render'],
        settings: settings.music_folder ? { music_folder: settings.music_folder } : {},
      });
      navigate(`/queue/douyin-reup/${response.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể retry video lỗi.');
    } finally {
      setBusy(false);
    }
  }

  async function handleRetryWithPreset(output?: DouyinOutputResult) {
    if (!jobId) return;
    const presetId = output ? retryPresetByOutput[output.index] || selectedPresetId : selectedPresetId;
    await handleRetryOutputWithPreset(output, presetId);
  }

  async function handleRetryOutputWithPreset(output: DouyinOutputResult | undefined, presetId: string) {
    if (!jobId) return;
    setBusy(true);
    setError(null);
    try {
      const response = await retryDouyinReupJobWithPreset(jobId, {
        preset_id: presetId,
        video_ids: output ? [`video_${output.index.toString().padStart(3, '0')}`] : [],
        retry_steps: ['asr', 'translation', 'render'],
        settings,
      });
      navigate(`/queue/douyin-reup/${response.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể retry bằng preset mới.');
    } finally {
      setBusy(false);
    }
  }

  async function handleRenderApproved() {
    if (!jobId) return;
    setBusy(true);
    setError(null);
    try {
      const response = await renderApprovedSubtitleReviewDocuments({
        job_id: jobId,
        output_folder: outputFolder,
        settings: { ...settings, review_subtitles_before_render: false, auto_render_after_translation: true },
      });
      navigate(`/queue/douyin-reup/${response.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể render subtitle đã approve.');
    } finally {
      setBusy(false);
    }
  }

  function updateAdvancedSettings(updates: Partial<DouyinReupSettings>) {
    setMode('advanced');
    updateSettings(updates);
  }

  function saveCurrentReupSettings() {
    saveDouyinSettings(settings);
    setActionMessage('Đã lưu cài đặt reup hiện tại. Lần sau mở lại tool sẽ tự dùng cấu hình này.');
  }

  function clearCurrentReupSettings() {
    clearSavedDouyinSettings();
    setActionMessage('Đã xóa cài đặt reup đã lưu. Cấu hình hiện tại vẫn giữ nguyên cho phiên này.');
  }

  function applyVietnameseSubtitleStylePreset(preset: VietnameseSubtitleStylePreset) {
    updateAdvancedSettings({
      burn_subtitle: true,
      subtitle_cover_auto_position: true,
      subtitle_cover_probe_if_no_ocr: true,
      ...preset.settings,
    });
  }

  function renderAdvancedSettings() {
    const coverHeightPercent = clampNumber(settings.subtitle_cover_height_ratio * 100, 5, 45);
    const coverBottomPercent = clampNumber(settings.subtitle_cover_bottom_ratio * 100, 0, 35);
    const coverTextTopPercent = clampNumber(
      50 + (settings.subtitle_cover_text_y_offset_ratio / Math.max(0.05, settings.subtitle_cover_height_ratio)) * 100,
      12,
      88,
    );
    const selectedSubtitleFontIsPreset = VIETNAMESE_SUBTITLE_FONT_OPTIONS.includes(settings.subtitle_font_family);
    const subtitlePreviewVideoPath = subtitlePreviewVideo?.path || '';
    const coverAutoPosition = settings.subtitle_cover_auto_position;
    const coverPreviewCanDrag = settings.subtitle_cover_enabled && !coverAutoPosition;
    function enableManualCoverPosition() {
      updateAdvancedSettings({ subtitle_cover_auto_position: false });
      setActionMessage('Đã chuyển sang chỉnh vùng che thủ công. Vùng này sẽ áp dụng cố định cho video có bật che sub.');
    }
    function restoreAutoCoverPosition() {
      updateAdvancedSettings({ subtitle_cover_auto_position: true, subtitle_cover_probe_if_no_ocr: true });
      setActionMessage('Đã bật lại tự tìm phụ đề Trung. Video không có sub Trung sẽ không bị vẽ nền che.');
    }
    function updateCoverPositionFromPreview(event: PointerEvent<HTMLDivElement>) {
      if (!coverPreviewCanDrag) return;
      const rect = event.currentTarget.getBoundingClientRect();
      if (!rect.height) return;
      const yRatio = clampNumber((event.clientY - rect.top) / rect.height, 0, 1);
      const nextBottomRatio = clampNumber(1 - yRatio - settings.subtitle_cover_height_ratio / 2, 0, 0.35);
      updateAdvancedSettings({
        subtitle_cover_bottom_ratio: Number(nextBottomRatio.toFixed(3)),
      });
    }

    return (
      <>
        <GlassCard className="grid gap-3 p-4" strong>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold text-white">Cài đặt đã lưu</h3>
              <p className="mt-1 text-sm leading-6 text-slate-400">
                Tool tự lưu các chỉnh sửa nâng cao trên máy này để lần sau dùng nhanh, không phải cấu hình lại từ đầu.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button className="rounded-md border border-cyan-300/50 bg-cyan-300/15 px-3 py-2 text-sm font-semibold text-cyan-50 hover:bg-cyan-300/25" type="button" onClick={saveCurrentReupSettings}>
                Lưu cài đặt
              </button>
              <button className="rounded-md border border-white/15 px-3 py-2 text-sm font-semibold text-slate-200 hover:border-rose-300/60 hover:text-rose-100" type="button" onClick={clearCurrentReupSettings}>
                Xóa bản đã lưu
              </button>
            </div>
          </div>
        </GlassCard>
        <PostProcessCleanupCard
          autoCleanup={!settings.keep_temp}
          onAutoCleanupChange={(value) => updateAdvancedSettings({ keep_temp: !value })}
        />
        <GlassCard className="grid gap-4 p-4" strong>
          <h3 className="font-semibold text-white">Phụ đề và chữ trên video</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-200">Ngôn ngữ nguồn</span>
              <input className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white" value={settings.source_language} onChange={(event) => updateAdvancedSettings({ source_language: event.target.value })} />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-200">Ngôn ngữ đích</span>
              <input className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white" value={settings.target_language} onChange={(event) => updateAdvancedSettings({ target_language: event.target.value })} />
            </label>
            <Toggle
              label={workflowMode === 'silent_immersive' ? 'Duyệt caption trước khi xuất video' : 'Duyệt phụ đề trước khi xuất video'}
              checked={usesManualSubtitleReview}
              onChange={(value) => updateRenderFlow(value ? 'review' : 'auto', true)}
            />
            <Toggle label="Xuất MP4 ngay sau khi dịch" checked={currentAutoRender} onChange={(value) => updateRenderFlow(value ? 'auto' : 'review', true)} />
            <Toggle label="Gắn phụ đề vào video" checked={settings.burn_subtitle} onChange={(value) => updateAdvancedSettings({ burn_subtitle: value })} />
            <Toggle
              label="Che phụ đề Trung nếu phát hiện"
              checked={settings.subtitle_cover_enabled}
              onChange={(value) => updateAdvancedSettings({ subtitle_cover_enabled: value })}
            />
            <Toggle label="Dùng khung phủ" checked={settings.add_overlay} onChange={(value) => updateAdvancedSettings({ add_overlay: value, overlay_mode: value ? settings.overlay_mode || 'preset' : 'none' })} />
          </div>
          {settings.subtitle_cover_enabled ? (
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-md border border-cyan-300/20 bg-cyan-300/8 p-3 text-sm leading-6 text-cyan-50 sm:col-span-3">
                <div className="font-semibold">
                  {coverAutoPosition ? 'Đang dùng tự động theo từng video' : 'Đang dùng vùng che thủ công cố định'}
                </div>
                <p className="mt-1 text-xs leading-5 text-cyan-100/85">
                  {coverAutoPosition
                    ? 'Có phụ đề Trung thì tool che đúng vùng đó và đặt sub Việt lên vùng che. Không thấy phụ đề Trung thì không vẽ nền che, sub Việt giữ vị trí hiển thị bình thường.'
                    : 'Vùng che thủ công sẽ luôn dùng vị trí bạn chỉnh. Chỉ dùng khi auto không bắt đúng vị trí sub Trung.'}
                </p>
              </div>
              <div className="grid gap-2 rounded-md border border-white/10 bg-slate-950/45 p-3 sm:col-span-3 md:grid-cols-2">
                {[
                  { value: 'solid', label: 'Nền màu', detail: 'Che chữ Trung bằng nền màu rõ, dễ đọc nhất.' },
                  { value: 'blur', label: 'Làm mờ', detail: 'Làm nhòe chữ Trung, giữ cảm giác tự nhiên hơn.' },
                ].map((option) => (
                  <button
                    className={`rounded-md border px-3 py-2 text-left transition ${
                      settings.subtitle_cover_mode === option.value
                        ? 'border-cyan-300/65 bg-cyan-300/15 text-cyan-50'
                        : 'border-white/10 bg-white/5 text-slate-300 hover:border-cyan-300/35 hover:bg-white/8'
                    }`}
                    key={option.value}
                    type="button"
                    onClick={() => updateAdvancedSettings({ subtitle_cover_mode: option.value })}
                  >
                    <span className="block text-sm font-semibold">{option.label}</span>
                    <span className="mt-1 block text-xs leading-5 text-slate-400">{option.detail}</span>
                  </button>
                ))}
              </div>
              <Toggle
                label="Tự động tìm sub Trung"
                checked={coverAutoPosition}
                onChange={(value) => updateAdvancedSettings({ subtitle_cover_auto_position: value, subtitle_cover_probe_if_no_ocr: value ? true : settings.subtitle_cover_probe_if_no_ocr })}
              />
              {coverAutoPosition ? (
                <Toggle
                  label="Quét nhanh khi chưa có OCR"
                  checked={settings.subtitle_cover_probe_if_no_ocr}
                  onChange={(value) => updateAdvancedSettings({ subtitle_cover_probe_if_no_ocr: value })}
                />
              ) : null}
              <SliderInput
                label={`${coverAutoPosition ? 'Độ cao nền khi thấy sub Trung' : 'Chiều cao nền che thủ công'}: ${Math.round(settings.subtitle_cover_height_ratio * 100)}%`}
                min={0.05}
                max={0.36}
                step={0.01}
                value={settings.subtitle_cover_height_ratio}
                onChange={(value) => updateAdvancedSettings({ subtitle_cover_height_ratio: value })}
              />
              {coverAutoPosition ? (
                <div className="rounded-md border border-white/10 bg-white/5 p-3 text-xs leading-5 text-slate-300">
                  Vị trí nền che sẽ lấy từ OCR từng video. Kéo preview chỉ bật khi bạn chuyển sang chỉnh thủ công.
                </div>
              ) : (
                <SliderInput
                  label={`Vị trí nền che thủ công: cách đáy ${Math.round(settings.subtitle_cover_bottom_ratio * 100)}%`}
                  min={0}
                  max={0.35}
                  step={0.005}
                  value={settings.subtitle_cover_bottom_ratio}
                  onChange={(value) => updateAdvancedSettings({ subtitle_cover_bottom_ratio: value })}
                />
              )}
              <SliderInput
                label={`Dịch chữ Việt trong vùng che: ${Math.round(settings.subtitle_cover_text_y_offset_ratio * 100)}%`}
                min={-0.12}
                max={0.12}
                step={0.005}
                value={settings.subtitle_cover_text_y_offset_ratio}
                onChange={(value) => updateAdvancedSettings({ subtitle_cover_text_y_offset_ratio: value })}
              />
              {settings.subtitle_cover_mode === 'blur' ? (
                <SliderInput
                  label={`Mức làm mờ chữ Trung: ${settings.subtitle_cover_blur_strength}`}
                  min={2}
                  max={30}
                  step={1}
                  value={settings.subtitle_cover_blur_strength}
                  onChange={(value) => updateAdvancedSettings({ subtitle_cover_blur_strength: Math.round(value) })}
                />
              ) : (
                <SliderInput
                  label={`Độ đậm nền che sub: ${Math.round(settings.subtitle_cover_opacity * 100)}%`}
                  min={0.2}
                  max={1}
                  step={0.01}
                  value={settings.subtitle_cover_opacity}
                  onChange={(value) => updateAdvancedSettings({ subtitle_cover_opacity: value })}
                />
              )}
              {coverAutoPosition ? (
                <SliderInput
                  label={`Nới rộng vùng che quanh chữ Trung: ${Math.round(settings.subtitle_cover_padding_ratio * 100)}%`}
                  min={0.01}
                  max={0.08}
                  step={0.005}
                  value={settings.subtitle_cover_padding_ratio}
                  onChange={(value) => updateAdvancedSettings({ subtitle_cover_padding_ratio: value })}
                />
              ) : null}
              <SliderInput
                label={`Che sớm hơn sub Việt: ${settings.subtitle_cover_lead_seconds.toFixed(2)}s`}
                min={0}
                max={2}
                step={0.05}
                value={settings.subtitle_cover_lead_seconds}
                onChange={(value) => updateAdvancedSettings({ subtitle_cover_lead_seconds: value })}
              />
              <SliderInput
                label={`Giữ nền sau sub Việt: ${settings.subtitle_cover_tail_seconds.toFixed(2)}s`}
                min={0}
                max={2}
                step={0.05}
                value={settings.subtitle_cover_tail_seconds}
                onChange={(value) => updateAdvancedSettings({ subtitle_cover_tail_seconds: value })}
              />
              <SliderInput
                label={`Bo góc nền sub: ${Math.round(settings.subtitle_cover_radius_ratio * 100)}%`}
                min={0}
                max={0.12}
                step={0.005}
                value={settings.subtitle_cover_radius_ratio}
                onChange={(value) => updateAdvancedSettings({ subtitle_cover_radius_ratio: value })}
              />
              {coverAutoPosition && settings.subtitle_cover_probe_if_no_ocr ? (
                <SliderInput
                  label={`Số lần quét vị trí mỗi giây: ${settings.subtitle_cover_probe_sample_fps.toFixed(1)}`}
                  min={0.5}
                  max={1.5}
                  step={0.1}
                  value={settings.subtitle_cover_probe_sample_fps}
                  onChange={(value) => updateAdvancedSettings({ subtitle_cover_probe_sample_fps: value })}
                />
              ) : null}
              {settings.subtitle_cover_mode !== 'blur' ? (
                <label className="block">
                  <span className="mb-1.5 block text-sm font-medium text-slate-200">Màu nền che sub</span>
                  <input
                    className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white"
                    type="color"
                    value={settings.subtitle_cover_color || '#000000'}
                    onChange={(event) => updateAdvancedSettings({ subtitle_cover_color: event.target.value })}
                  />
                </label>
              ) : null}
              <div className="grid gap-3 rounded-md border border-white/10 bg-slate-950/45 p-3 sm:col-span-3 lg:grid-cols-[220px_1fr]">
                <div>
                  <div className="text-sm font-semibold text-white">{coverAutoPosition ? 'Xem thử cách che tự động' : 'Xem thử vùng che thủ công'}</div>
                  <p className="mt-1 text-xs leading-5 text-slate-400">
                    {coverAutoPosition
                      ? 'Khung này chỉ minh họa. Khi render, tool tự tìm sub Trung trong từng video; nếu không có sub Trung thì bỏ qua nền che.'
                      : 'Kéo vùng nền trong khung để chỉnh vị trí thủ công cho cả lô video. Dùng khi auto không bắt đúng vùng sub Trung.'}
                  </p>
                  <div className="mt-3 grid gap-1 text-xs text-slate-400">
                    <span>Nền: {Math.round(settings.subtitle_cover_height_ratio * 100)}% chiều cao video</span>
                    <span>{coverAutoPosition ? 'Vị trí: tự lấy theo OCR từng video' : `Cách đáy: ${Math.round(settings.subtitle_cover_bottom_ratio * 100)}%`}</span>
                    <span>Chữ Việt: {Math.round(settings.subtitle_cover_text_y_offset_ratio * 100)}%</span>
                    {subtitlePreviewVideo ? <span className="truncate text-cyan-100">Video mẫu: {subtitlePreviewVideo.filename || subtitlePreviewVideo.path}</span> : <span>Scan video để xem mẫu thật.</span>}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {coverAutoPosition ? (
                      <button className="rounded-md border border-white/15 px-3 py-2 text-xs font-semibold text-slate-200 hover:border-cyan-300/50 hover:text-cyan-100" type="button" onClick={enableManualCoverPosition}>
                        Chỉnh vùng che thủ công
                      </button>
                    ) : (
                      <button className="rounded-md border border-cyan-300/50 bg-cyan-300/12 px-3 py-2 text-xs font-semibold text-cyan-50 hover:bg-cyan-300/18" type="button" onClick={restoreAutoCoverPosition}>
                        Dùng tự động theo sub Trung
                      </button>
                    )}
                  </div>
                </div>
                <div
                  className={`relative mx-auto aspect-[9/16] h-[320px] overflow-hidden rounded-lg border border-white/15 bg-gradient-to-b from-slate-700 via-slate-900 to-slate-950 ${coverPreviewCanDrag ? 'cursor-ns-resize' : 'cursor-default'}`}
                  onPointerDown={(event) => {
                    if (coverPreviewCanDrag) event.currentTarget.setPointerCapture(event.pointerId);
                    updateCoverPositionFromPreview(event);
                  }}
                  onPointerMove={(event) => {
                    if (event.buttons === 1) updateCoverPositionFromPreview(event);
                  }}
                  role="presentation"
                >
                  {subtitlePreviewVideoPath ? (
                    <video
                      key={subtitlePreviewVideoPath}
                      className="absolute inset-0 h-full w-full object-cover opacity-70"
                      src={sourceVideoFileUrl(subtitlePreviewVideoPath)}
                      autoPlay
                      loop
                      muted
                      playsInline
                      preload="metadata"
                      onError={() => setSubtitlePreviewVideoError(true)}
                    />
                  ) : null}
                  {subtitlePreviewVideoError ? (
                    <div className="absolute inset-x-3 top-3 rounded-md border border-amber-300/30 bg-amber-300/15 px-3 py-2 text-xs leading-5 text-amber-100">
                      Không xem được video nguồn mẫu. Hãy kiểm tra quyền đọc file hoặc thử chọn video MP4 khác.
                    </div>
                  ) : null}
                  <div className="absolute left-1/2 top-[18%] -translate-x-1/2 rounded-full bg-white/10 px-3 py-1 text-[10px] text-slate-200">
                    watermark / tên kênh
                  </div>
                  <div className="absolute left-1/2 top-[70%] -translate-x-1/2 rounded bg-white/80 px-3 py-1 text-center text-[11px] font-semibold text-slate-950">
                    字幕 Trung gốc
                  </div>
                  <div
                    className="absolute left-0 right-0 grid place-items-center px-3 text-center"
                    style={{
                      bottom: `${coverBottomPercent}%`,
                      height: `${coverHeightPercent}%`,
                      backgroundColor: settings.subtitle_cover_mode === 'blur'
                        ? 'rgba(15, 23, 42, 0.16)'
                        : settings.subtitle_cover_enabled ? hexToRgba(settings.subtitle_cover_color, settings.subtitle_cover_opacity) : 'rgba(15, 23, 42, 0.85)',
                      backdropFilter: settings.subtitle_cover_mode === 'blur' ? `blur(${Math.max(2, Math.round(settings.subtitle_cover_blur_strength / 2))}px)` : undefined,
                      WebkitBackdropFilter: settings.subtitle_cover_mode === 'blur' ? `blur(${Math.max(2, Math.round(settings.subtitle_cover_blur_strength / 2))}px)` : undefined,
                      borderRadius: `${Math.round(Math.max(0, settings.subtitle_cover_radius_ratio || 0) * 220)}px`,
                    }}
                  >
                    <span
                      className="absolute left-2 right-2 leading-tight"
                      style={{
                        top: `${coverTextTopPercent}%`,
                        transform: 'translateY(-50%)',
                        color: settings.subtitle_font_color,
                        fontFamily: settings.subtitle_font_family || 'Arial',
                        fontSize: `${Math.max(13, Math.min(24, Math.round(settings.subtitle_font_size * 0.36)))}px`,
                        fontWeight: 800,
                        textShadow: settings.subtitle_shadow_enabled
                          ? `0 2px ${settings.subtitle_shadow_size}px ${hexToRgba(settings.subtitle_shadow_color, settings.subtitle_shadow_opacity)}`
                          : 'none',
                        WebkitTextStroke: `${Math.max(0, Math.min(2, settings.subtitle_stroke_width))}px ${settings.subtitle_stroke_color}`,
                      }}
                    >
                      Sub Việt mẫu
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
          <div className="grid gap-3 border-t border-white/10 pt-4">
            <div className="grid gap-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h4 className="font-semibold text-white">Mẫu sub Việt</h4>
                  <p className="mt-1 text-sm leading-6 text-slate-400">Chọn nhanh style theo màu chữ, nền, viền và bóng. Tool tự lưu mẫu đã chọn hoặc phần bạn chỉnh tay để lần sau dùng lại.</p>
                </div>
              </div>
              <div className="grid gap-2 md:grid-cols-2">
                {VIETNAMESE_SUBTITLE_STYLE_PRESETS.map((preset) => {
                  const active = isVietnameseSubtitleStylePresetActive(preset, settings);
                  const presetBackground = String(preset.settings.subtitle_cover_color || '#000000');
                  const presetOpacity = Number(preset.settings.subtitle_cover_opacity ?? 0.8);
                  const presetFontFamily = String(preset.settings.subtitle_font_family || 'Arial');
                  return (
                    <button
                      className={`grid gap-2 rounded-md border p-3 text-left transition ${
                        active
                          ? 'border-cyan-300/70 bg-cyan-300/12 text-cyan-50'
                          : 'border-white/10 bg-slate-950/45 text-slate-200 hover:border-cyan-300/35 hover:bg-white/8'
                      }`}
                      key={preset.id}
                      type="button"
                      onClick={() => applyVietnameseSubtitleStylePreset(preset)}
                    >
                      <div className="flex items-center gap-3">
                        <span
                          className="grid h-14 w-24 shrink-0 place-items-center rounded-md border border-white/15 px-2 text-center text-[12px] font-black leading-4"
                          style={{
                            backgroundColor: hexToRgba(presetBackground, presetOpacity),
                            color: String(preset.settings.subtitle_font_color || '#FFFFFF'),
                            fontFamily: presetFontFamily,
                            textShadow: preset.settings.subtitle_shadow_enabled
                              ? `0 2px ${preset.settings.subtitle_shadow_size || 2}px ${hexToRgba(String(preset.settings.subtitle_shadow_color || '#000000'), Number(preset.settings.subtitle_shadow_opacity ?? 0.35))}`
                              : 'none',
                            WebkitTextStroke: `${Math.max(0, Math.min(3, Number(preset.settings.subtitle_stroke_width || 0)))}px ${String(preset.settings.subtitle_stroke_color || '#000000')}`,
                          }}
                        >
                          {preset.previewText}
                        </span>
                        <span className="min-w-0">
                          <span className="block text-sm font-semibold">{preset.name}</span>
                          <span className="mt-0.5 block text-xs leading-5 text-slate-400">{preset.description}</span>
                        </span>
                      </div>
                      <span className="h-1 rounded-full" style={{ backgroundColor: preset.accentColor, boxShadow: `0 0 14px ${preset.accentColor}` }} />
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Toggle
                label="Tùy chỉnh style sub Việt"
                checked={settings.subtitle_style_custom_enabled}
                onChange={(value) => updateAdvancedSettings({ subtitle_style_custom_enabled: value })}
              />
              <div
                className="min-w-[220px] rounded-md border border-white/10 px-4 py-3 text-center"
                style={{
                  backgroundColor: settings.subtitle_cover_mode === 'blur'
                    ? 'rgba(15, 23, 42, 0.16)'
                    : settings.subtitle_cover_enabled ? hexToRgba(settings.subtitle_cover_color, settings.subtitle_cover_opacity) : 'rgba(15, 23, 42, 0.85)',
                  backdropFilter: settings.subtitle_cover_mode === 'blur' ? `blur(${Math.max(2, Math.round(settings.subtitle_cover_blur_strength / 2))}px)` : undefined,
                  WebkitBackdropFilter: settings.subtitle_cover_mode === 'blur' ? `blur(${Math.max(2, Math.round(settings.subtitle_cover_blur_strength / 2))}px)` : undefined,
                  borderRadius: `${Math.round(Math.max(0, settings.subtitle_cover_radius_ratio || 0) * 220)}px`,
                  color: settings.subtitle_font_color,
                  fontFamily: settings.subtitle_font_family || 'Arial',
                  fontSize: `${Math.max(18, Math.min(34, Math.round(settings.subtitle_font_size * 0.5)))}px`,
                  fontWeight: 700,
                  textShadow: settings.subtitle_shadow_enabled
                    ? `0 2px ${settings.subtitle_shadow_size}px ${hexToRgba(settings.subtitle_shadow_color, settings.subtitle_shadow_opacity)}`
                    : 'none',
                  WebkitTextStroke: `${Math.max(0, Math.min(3, settings.subtitle_stroke_width))}px ${settings.subtitle_stroke_color}`,
                }}
              >
                Săn deal hôm nay
              </div>
            </div>
            {settings.subtitle_style_custom_enabled ? (
              <div className="grid gap-3 sm:grid-cols-3">
                <label className="block">
                  <span className="mb-1.5 block text-sm font-medium text-slate-200">Font sub Việt</span>
                  <select
                    className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white"
                    value={selectedSubtitleFontIsPreset ? settings.subtitle_font_family : '__custom'}
                    onChange={(event) => {
                      if (event.target.value === '__custom') return;
                      updateAdvancedSettings({ subtitle_font_family: event.target.value });
                    }}
                  >
                    {VIETNAMESE_SUBTITLE_FONT_OPTIONS.map((font) => (
                      <option key={font} value={font}>{font}</option>
                    ))}
                    <option value="__custom">Font tự nhập</option>
                  </select>
                  <input
                    className="mt-2 h-10 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white"
                    value={settings.subtitle_font_family}
                    onChange={(event) => updateAdvancedSettings({ subtitle_font_family: event.target.value })}
                    placeholder="Nhập tên font đã cài trên Windows"
                  />
                  <span className="mt-1.5 block text-xs leading-5 text-slate-500">Font cần được cài trên Windows để render đúng trong video.</span>
                </label>
                <SliderInput
                  label={`Cỡ chữ sub Việt: ${settings.subtitle_font_size}px`}
                  min={28}
                  max={96}
                  step={1}
                  value={settings.subtitle_font_size}
                  onChange={(value) => updateAdvancedSettings({ subtitle_font_size: Math.round(value) })}
                />
                <SliderInput
                  label={`Ký tự mỗi dòng: ${settings.subtitle_max_chars_per_line}`}
                  min={12}
                  max={42}
                  step={1}
                  value={settings.subtitle_max_chars_per_line}
                  onChange={(value) => updateAdvancedSettings({ subtitle_max_chars_per_line: Math.round(value) })}
                />
                <label className="block">
                  <span className="mb-1.5 block text-sm font-medium text-slate-200">Màu chữ sub Việt</span>
                  <input
                    className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white"
                    type="color"
                    value={settings.subtitle_font_color || '#FFFFFF'}
                    onChange={(event) => updateAdvancedSettings({ subtitle_font_color: event.target.value })}
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-sm font-medium text-slate-200">Màu viền chữ</span>
                  <input
                    className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white"
                    type="color"
                    value={settings.subtitle_stroke_color || '#000000'}
                    onChange={(event) => updateAdvancedSettings({ subtitle_stroke_color: event.target.value })}
                  />
                </label>
                <SliderInput
                  label={`Độ dày viền: ${settings.subtitle_stroke_width}px`}
                  min={0}
                  max={8}
                  step={1}
                  value={settings.subtitle_stroke_width}
                  onChange={(value) => updateAdvancedSettings({ subtitle_stroke_width: Math.round(value) })}
                />
                <Toggle
                  label="Bật đổ bóng chữ"
                  checked={settings.subtitle_shadow_enabled}
                  onChange={(value) => updateAdvancedSettings({ subtitle_shadow_enabled: value })}
                />
                <label className="block">
                  <span className="mb-1.5 block text-sm font-medium text-slate-200">Màu đổ bóng</span>
                  <input
                    className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white"
                    type="color"
                    value={settings.subtitle_shadow_color || '#000000'}
                    onChange={(event) => updateAdvancedSettings({ subtitle_shadow_color: event.target.value })}
                    disabled={!settings.subtitle_shadow_enabled}
                  />
                </label>
                <SliderInput
                  label={`Độ mờ bóng: ${Math.round(settings.subtitle_shadow_opacity * 100)}%`}
                  min={0}
                  max={1}
                  step={0.05}
                  value={settings.subtitle_shadow_opacity}
                  onChange={(value) => updateAdvancedSettings({ subtitle_shadow_opacity: value })}
                />
                <SliderInput
                  label={`Độ lớn bóng: ${settings.subtitle_shadow_size}px`}
                  min={0}
                  max={8}
                  step={1}
                  value={settings.subtitle_shadow_size}
                  onChange={(value) => updateAdvancedSettings({ subtitle_shadow_size: Math.round(value) })}
                />
                <label className="block">
                  <span className="mb-1.5 block text-sm font-medium text-slate-200">Số dòng tối đa</span>
                  <select
                    className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white"
                    value={settings.subtitle_max_lines}
                    onChange={(event) => updateAdvancedSettings({ subtitle_max_lines: Number(event.target.value) })}
                  >
                    <option value={1}>1 dòng</option>
                    <option value={2}>2 dòng</option>
                    <option value={3}>3 dòng</option>
                  </select>
                </label>
              </div>
            ) : null}
          </div>
        </GlassCard>

        <GlassCard className="grid gap-4 p-4" strong>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-semibold text-white">Khung phủ / ảnh trang trí</h3>
              <p className="mt-1 text-sm text-slate-400">
                Dùng ảnh PNG/WebP nền trong suốt kích thước 1080x1920 để thay khung phủ mặc định.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {[
                { value: 'preset', label: 'Khung mặc định' },
                { value: 'custom', label: 'Khung tự chọn' },
                { value: 'none', label: 'Không dùng' },
              ].map((option) => (
                <button
                  key={option.value}
                  className={`rounded-md border px-3 py-2 text-xs font-semibold ${
                    (settings.overlay_mode || 'preset') === option.value
                      ? 'border-cyan-300 bg-cyan-300 text-slate-950'
                      : 'border-white/15 bg-slate-950/70 text-slate-200 hover:border-cyan-300/60'
                  }`}
                  type="button"
                  onClick={() => updateAdvancedSettings({ overlay_mode: option.value, add_overlay: option.value !== 'none' })}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
          {settings.overlay_mode === 'custom' ? (
            <div className="grid gap-3">
              <label className="block">
                  <span className="mb-1.5 block text-sm font-medium text-slate-200">Đường dẫn khung phủ tự chọn</span>
                <input
                  className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white"
                  type="text"
                  value={settings.custom_overlay_path || ''}
                  placeholder="examples/overlay hoặc D:\\Overlay\\khung_1080x1920.png"
                  onChange={(event) => updateAdvancedSettings({ custom_overlay_path: event.target.value })}
                />
              </label>
              <div className="flex flex-wrap gap-2">
                <button className="rounded-md border border-white/15 px-3 py-2 text-sm font-semibold text-slate-100 hover:border-cyan-300/60" type="button" onClick={() => void browseCustomOverlay('file')}>
                  Chọn ảnh
                </button>
                <button className="rounded-md border border-white/15 px-3 py-2 text-sm font-semibold text-slate-100 hover:border-cyan-300/60" type="button" onClick={() => void browseCustomOverlay('folder')}>
                  Chọn thư mục
                </button>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <SliderInput label="Chiều cao khung phủ tự chọn (%)" min={5} max={100} step={1} value={settings.custom_overlay_height_percent ?? 100} onChange={(value) => updateAdvancedSettings({ custom_overlay_height_percent: value })} />
                <label className="block">
                  <span className="mb-1.5 block text-sm font-medium text-slate-200">Cách đặt khung phủ</span>
                  <select className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white" value={settings.custom_overlay_fit_mode || 'cover'} onChange={(event) => updateAdvancedSettings({ custom_overlay_fit_mode: event.target.value })}>
                    <option value="cover">Phủ kín video</option>
                    <option value="contain">Giữ toàn bộ ảnh</option>
                    <option value="stretch">Kéo đúng 1080x1920</option>
                  </select>
                </label>
              </div>
            </div>
          ) : null}
        </GlassCard>

        <GlassCard className="grid gap-4 p-4" strong>
          <h3 className="font-semibold text-white">{friendlyTermLabel('asr')}</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <SliderInput label="Dịch thời gian phụ đề" min={-1} max={1} step={0.05} value={settings.asr_subtitle_offset_seconds} onChange={(value) => updateAdvancedSettings({ asr_subtitle_offset_seconds: value })} />
            <Toggle label="Bỏ qua đoạn im lặng khi nghe lời thoại" checked={settings.asr_vad_filter} onChange={(value) => updateAdvancedSettings({ asr_vad_filter: value })} />
            <Toggle label="Tự chuyển video có thoại sang quy trình có thoại" checked={settings.auto_route_speech_to_voice_reup} onChange={(value) => updateAdvancedSettings({ auto_route_speech_to_voice_reup: value })} />
            <Toggle label="Tự chuyển video không thoại sang Silent Mode" checked={settings.auto_route_no_speech_to_silent_reup} onChange={(value) => updateAdvancedSettings({ auto_route_no_speech_to_silent_reup: value })} />
            <SliderInput label="Độ nhạy tự chuyển quy trình" min={0.1} max={0.6} step={0.01} value={settings.auto_route_speech_threshold} onChange={(value) => updateAdvancedSettings({ auto_route_speech_threshold: value })} />
            <Toggle label="Dùng file .srt đi kèm" checked={settings.use_sidecar_srt} onChange={(value) => updateAdvancedSettings({ use_sidecar_srt: value })} />
            <Toggle label="Dùng phụ đề có sẵn trong video" checked={settings.use_embedded_subtitle} onChange={(value) => updateAdvancedSettings({ use_embedded_subtitle: value })} />
            <Toggle label="Nghe lời thoại nếu thiếu phụ đề" checked={settings.use_asr_if_no_subtitle} onChange={(value) => updateAdvancedSettings({ use_asr_if_no_subtitle: value })} />
          </div>
        </GlassCard>

        <GlassCard className="grid gap-4 p-4" strong>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold text-white">{friendlyTermLabel('ocr')}</h3>
              <div className={dependencyStatus?.ocr_available ? 'mt-1 text-xs text-emerald-300' : 'mt-1 text-xs text-amber-300'}>{formatOcrDependencyStatus(dependencyStatus)}</div>
            </div>
            <Toggle label="Đọc chữ trên video khi cần" checked={settings.use_ocr_if_no_subtitle || settings.use_ocr_if_asr_failed} onChange={(value) => updateAdvancedSettings({ use_ocr_if_no_subtitle: value, use_ocr_if_asr_failed: value })} />
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-200">{friendlyTermLabel('provider')} đọc chữ</span>
              <select className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white" value={settings.ocr_provider} onChange={(event) => updateAdvancedSettings({ ocr_provider: event.target.value })}>
                <option value="paddleocr">PaddleOCR</option>
                <option value="easyocr">EasyOCR</option>
                <option value="mock_ocr">Chế độ thử nghiệm</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-200">{friendlyTermLabel('region')} đọc chữ</span>
              <select
                className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white"
                value={settings.ocr_region_mode}
                onChange={(event) => {
                  const regionMode = event.target.value;
                  updateAdvancedSettings({
                    ocr_region_mode: regionMode,
                    ...(regionMode === 'full_frame'
                      ? {
                          use_ocr_if_no_subtitle: true,
                          use_ocr_if_asr_failed: true,
                          prefer_ocr_over_asr_when_text_visible: true,
                          subtitle_source_priority: prioritizeOcrBeforeAsr(settings.subtitle_source_priority),
                        }
                      : {}),
                  });
                }}
              >
                <option value="bottom_auto">Tự tìm vùng dưới</option>
                <option value="middle_lower">Vùng giữa thấp</option>
                <option value="full_frame">Toàn bộ video</option>
                <option value="manual">Tự nhập vùng</option>
              </select>
            </label>
            <SliderInput label={friendlyTermLabel('fps')} min={0.5} max={5} step={0.5} value={settings.ocr_sample_fps} onChange={(value) => updateAdvancedSettings({ ocr_sample_fps: value })} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <SliderInput label={`Độ chắc chắn tối thiểu khi đọc chữ`} min={0} max={1} step={0.05} value={settings.ocr_min_confidence} onChange={(value) => updateAdvancedSettings({ ocr_min_confidence: value })} />
            <Toggle label="Ưu tiên chữ trên màn hình" checked={settings.prefer_ocr_over_asr_when_text_visible} onChange={(value) => updateAdvancedSettings({ prefer_ocr_over_asr_when_text_visible: value })} />
            <div className="rounded-md border border-white/10 bg-slate-950/60 p-3">
              <Toggle label="Tự lọc watermark / tên kênh" checked={settings.ocr_filter_watermarks} onChange={(value) => updateAdvancedSettings({ ocr_filter_watermarks: value })} />
              <p className="mt-2 text-xs leading-5 text-slate-400">
                Tool tự nhận diện chữ lặp ở nhiều frame, logo chữ chạy quanh màn hình và các watermark phổ biến. Không cần nhập tay cho từng video.
              </p>
            </div>
            <details className="rounded-md border border-white/10 bg-slate-950/40 p-3 text-sm text-slate-300">
              <summary className="cursor-pointer font-medium text-slate-200">Thêm từ khóa bỏ qua thủ công (hiếm khi cần)</summary>
              <label className="mt-3 block">
                <span className="mb-1.5 block text-xs text-slate-400">Chỉ dùng khi watermark quá đặc biệt và tool chưa tự lọc được</span>
                <input
                  className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white"
                  value={settings.ocr_watermark_terms.join(', ')}
                  onChange={(event) => updateAdvancedSettings({ ocr_watermark_terms: splitWatermarkTerms(event.target.value) })}
                  placeholder="Ví dụ: tên kênh, tên shop..."
                />
              </label>
            </details>
          </div>
          {settings.ocr_region_mode === 'manual' ? (
            <div className="grid gap-3">
              <p className="rounded-md border border-cyan-300/20 bg-cyan-300/10 px-3 py-2 text-xs leading-5 text-cyan-100">
                Tự nhập vùng dùng tọa độ theo video gốc: x/y là góc trên bên trái, width/height là kích thước vùng. Ví dụ video 1080x1920 quét nửa trên: x=0, y=0, width=1080, height=900.
              </p>
              <div className="grid gap-2 sm:grid-cols-4">
                {(['x', 'y', 'width', 'height'] as const).map((key) => (
                  <label className="block" key={key}>
                    <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">{key}</span>
                    <input
                      className="h-10 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white"
                      type="number"
                      min={0}
                      value={settings.ocr_manual_region?.[key] ?? (key === 'width' ? 1080 : key === 'height' ? 500 : 0)}
                      onChange={(event) => updateOcrManualRegion(key, Number(event.target.value || 0))}
                    />
                  </label>
                ))}
              </div>
            </div>
          ) : null}
        </GlassCard>

        <GlassCard className="grid gap-4 p-4" strong>
          <h3 className="font-semibold text-white">Âm thanh và đầu ra</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <SliderInput label="Âm lượng nhạc nền" min={0} max={1} step={0.01} value={settings.bgm_volume} onChange={(value) => updateAdvancedSettings({ bgm_volume: value })} />
            <SliderInput label="Âm lượng audio gốc" min={0} max={1} step={0.01} value={settings.original_audio_volume} onChange={(value) => updateAdvancedSettings({ original_audio_volume: value })} />
            <Toggle
              label="Giảm giọng Trung trong audio gốc"
              checked={settings.reduce_original_voice}
              onChange={(value) => updateAdvancedSettings({ reduce_original_voice: value })}
            />
            {settings.reduce_original_voice ? (
              <SliderInput
                label={`Mức giảm giọng Trung: ${Math.round(settings.original_voice_reduction_strength * 100)}%`}
                min={0.2}
                max={0.95}
                step={0.05}
                value={settings.original_voice_reduction_strength}
                onChange={(value) => updateAdvancedSettings({ original_voice_reduction_strength: value })}
              />
            ) : null}
            <Toggle
              label="Tự làm chậm video nếu voice Việt quá nhanh"
              checked={settings.voiceover_auto_slow_video}
              onChange={(value) => updateAdvancedSettings({ voiceover_auto_slow_video: value })}
            />
            <SliderInput
              label={`Video chậm tối đa: ${settings.voiceover_max_video_slowdown.toFixed(2)}x`}
              min={1}
              max={1.5}
              step={0.01}
              value={settings.voiceover_max_video_slowdown}
              onChange={(value) => updateAdvancedSettings({ voiceover_max_video_slowdown: value })}
            />
            <SliderInput
              label={`Tốc độ voice dễ nghe: ${settings.voiceover_comfort_speedup.toFixed(2)}x`}
              min={1}
              max={1.8}
              step={0.01}
              value={settings.voiceover_comfort_speedup}
              onChange={(value) => updateAdvancedSettings({ voiceover_comfort_speedup: value })}
            />
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-200">Mẫu hiển thị phụ đề</span>
              <select className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white" value={settings.visual_style_preset_id} onChange={(event) => updateAdvancedSettings({ visual_style_preset_id: event.target.value })}>
                {visualStyles.map((preset) => <option key={preset.id} value={preset.id}>{preset.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-200">Giới hạn số video</span>
              <input className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white" type="number" min={1} value={settings.max_videos ?? ''} onChange={(event) => updateAdvancedSettings({ max_videos: event.target.value ? Number(event.target.value) : null })} />
            </label>
          </div>
        </GlassCard>
      </>
    );
  }

  return (
    <>
      <StartWorkflowLayout
        hero={<WorkflowHero mode={workflowMode} onFocusStart={() => document.getElementById('start-source-folder')?.scrollIntoView({ behavior: 'smooth', block: 'start' })} />}
        main={
          <>
            <div id="start-source-folder" />
            <ApiErrorBox error={error} />
            <NotifyOnChange value={actionMessage} variant="success" />
            {actionMessage ? <div className="rounded-md border border-emerald-300/20 bg-emerald-300/10 px-4 py-3 text-sm text-emerald-100">{actionMessage}</div> : null}
            <WorkflowStepper steps={[
              { label: 'Nguồn', status: sourceFolder ? 'done' : 'active' },
              { label: 'Cấu hình', status: selectedPresetCard ? 'done' : 'pending' },
              { label: 'Đầu ra', status: outputFolder ? 'done' : 'pending' },
              { label: 'Kiểm tra', status: checklist.some((item) => item.status === 'missing') ? 'pending' : 'done' },
              { label: 'Bắt đầu', status: jobStatus && !done ? 'active' : done ? 'done' : 'pending' },
              { label: 'Xuất bản', status: exportPack ? 'done' : 'pending' },
            ]} />
            <SourceFolderCard
              mode={workflowMode}
              value={sourceFolder}
              busy={busy && !jobStatus}
              scanSummary={scanSummary}
              videos={videos}
              scanErrors={scanErrors}
              recentFolders={recentSourceFolders}
              onBrowse={() => void browseSourceFolder()}
              onChange={setSourceFolder}
              onScan={() => void handleScan()}
              onUseRecent={setSourceFolder}
              onRemoveRecent={(path) => setRecentSourceFolders((current) => removeRecentFolder(RECENT_SOURCE_KEY, current, path))}
            />
            <StartPresetSelector
              mode={workflowMode}
              presets={startPresetCards}
              selectedPresetId={selectedPresetId}
              recommendedPreset={recommendedPresetCard}
              recommendationReason={recommendation?.reason ?? recommendationReason(workflowMode, sourceFolder, recommendedPresetCard)}
              onSelect={(presetId) => void handlePresetSelect(presetId)}
            />
            <RenderFlowCard
              mode={workflowMode}
              reviewMode={usesManualSubtitleReview}
              onModeChange={(renderMode) => updateRenderFlow(renderMode)}
            />
            <OutputFolderCard
              mode={workflowMode}
              outputFolder={outputFolder}
              projectName={projectName}
              recentFolders={recentOutputFolders}
              onBrowse={() => void browseOutputFolder()}
              onOutputFolderChange={setOutputFolder}
              onProjectNameChange={setProjectName}
              onUseRecent={setOutputFolder}
              onRemoveRecent={(path) => setRecentOutputFolders((current) => removeRecentFolder(RECENT_OUTPUT_KEY, current, path))}
            />
            <AdvancedTuningSection
              hasCustomSettings={mode === 'advanced'}
              onOpenAdvanced={() => setAdvancedOpen(true)}
            >
              <ProductContextCard
                value={silentProductContext}
                industries={withAutoIndustry(silentIndustries.length ? silentIndustries : DEFAULT_SILENT_INDUSTRIES)}
                tone={settings.silent_caption_tone}
                busy={busy || videos.length === 0}
                hasPreview={Boolean(captionPreview)}
                onChange={updateSilentProductContext}
                onToneChange={(value) => updateSettings({ silent_caption_tone: value })}
                onPreview={() => void handleGenerateCaptionPreview()}
                onRegenerate={() => void handleRegenerateCaptionPreview()}
                onCreateReview={() => void handleCreateCaptionReviewDocument()}
              />
              {workflowMode === 'silent_immersive' ? (
                <AutoRouteSpeechCard
                  enabled={settings.auto_route_speech_to_voice_reup}
                  threshold={settings.auto_route_speech_threshold}
                  voiceoverEnabled={settings.generate_voiceover_for_silent_video}
                  onEnabledChange={(value) => updateSettings({ auto_route_speech_to_voice_reup: value })}
                  onThresholdChange={(value) => updateSettings({ auto_route_speech_threshold: value })}
                />
              ) : (
                <AutoRouteNoSpeechCard
                  enabled={settings.auto_route_no_speech_to_silent_reup}
                  onEnabledChange={(value) => updateSettings({ auto_route_no_speech_to_silent_reup: value })}
                />
              )}
              <MusicFolderCard
                musicFolder={settings.music_folder || ''}
                addMusic={addMusicEnabled}
                recentFolders={recentMusicFolders}
                onAddMusicChange={(value) => updateSettings(initialWorkflow === 'silent' ? { add_bgm_for_silent_video: value, add_bgm: value } : { add_bgm: value })}
                onBrowse={() => void browseMusicFolder()}
                onMusicFolderChange={(value) => updateSettings({ music_folder: value })}
                onUseRecent={(path) => updateSettings({ music_folder: path })}
                onRemoveRecent={(path) => setRecentMusicFolders((current) => removeRecentFolder(RECENT_MUSIC_KEY, current, path))}
              />
              <VoiceoverCard
                mode={workflowMode}
                enabled={settings.generate_voiceover_for_silent_video}
                provider={settings.silent_voiceover_provider}
                voice={settings.silent_voiceover_voice}
                onEnabledChange={updateVoiceoverEnabled}
                onVoiceChange={updateVoiceChoice}
              />
              <BatchReliabilityCard
                mode={settings.batch_performance_mode}
                chunkSize={settings.batch_chunk_size}
                ffmpegTimeoutSeconds={settings.batch_ffmpeg_timeout_seconds}
                watchdogMinutes={settings.batch_watchdog_stale_minutes}
                asrMaxAudioSeconds={settings.asr_max_audio_seconds}
                pauseOnRepeatedFailures={settings.batch_pause_on_repeated_failures}
                maxConsecutiveFailures={settings.batch_max_consecutive_failures}
                onChange={updateSettings}
              />
              <PostProcessCleanupCard
                autoCleanup={!settings.keep_temp}
                onAutoCleanupChange={(value) => updateSettings({ keep_temp: !value })}
              />
            </AdvancedTuningSection>
            {captionPreview ? (
              <SilentPlanPreview
                preview={captionPreview}
                editingSegmentId={editingSegmentId}
                onEditSegment={setEditingSegmentId}
                onRegenerate={() => void handleRegenerateCaptionPreview()}
                disabled={busy}
                renderEditor={(segmentId) => {
                  const segment = captionPreview.plan.visual_segments.find((item) => item.id === segmentId);
                  return segment ? <SegmentTagEditor segment={segment} vocabulary={visualTagVocabulary} disabled={busy} onSave={(payload) => handleSaveSegmentTags(segment.id, payload)} onRegenerate={handleRegenerateCaptionPreview} /> : null;
                }}
              />
            ) : null}
          </>
        }
        side={
          <>
            <RunSummaryPanel
              mode={workflowMode}
              preset={workflowPreviewPreset}
              sourceFolder={sourceFolder}
              outputFolder={outputFolder}
              scanSummary={scanSummary}
              checklist={checklist}
              validationMessages={validationMessages}
              job={jobStartedView}
              jobStatus={jobStatus}
              disabled={startDisabled}
              loading={busy && !jobStatus}
              startLabel={currentAutoRender ? 'Bắt đầu xuất MP4 ngay' : 'Tạo phụ đề để duyệt'}
              addMusic={addMusicEnabled}
              musicFolder={settings.music_folder || ''}
              voiceoverEnabled={settings.generate_voiceover_for_silent_video}
              autoRouteEnabled={workflowMode === 'silent_immersive' ? settings.auto_route_speech_to_voice_reup : settings.auto_route_no_speech_to_silent_reup}
              reviewMode={usesManualSubtitleReview}
              onOpenAdvanced={() => setAdvancedOpen(true)}
              onStart={requestStart}
            />
            <StartAdvancedSettingsDrawer
              open={advancedOpen}
              custom={mode === 'advanced'}
              onClose={() => setAdvancedOpen(false)}
              onReset={() => void handlePresetSelect(selectedPresetId)}
            >
              {renderAdvancedSettings()}
            </StartAdvancedSettingsDrawer>
          </>
        }
      />

      <GlassModal open={riskyConfirmOpen} title="Xác nhận mẫu xử lý nhanh" onClose={() => setRiskyConfirmOpen(false)}>
        <div className="grid gap-4 text-sm leading-6 text-slate-300">
          <p>Mẫu này sẽ xử lý nhanh và có thể bỏ qua bước duyệt phụ đề. Bạn vẫn có thể kiểm tra video ở trang kết quả sau khi xuất.</p>
          <div className="flex flex-wrap gap-2">
            <GlassButton variant="primary" onClick={() => void startCurrentWorkflow()}>Tiếp tục</GlassButton>
            <GlassButton variant="secondary" onClick={() => { setRiskyConfirmOpen(false); void handlePresetSelect(initialWorkflow === 'silent' ? 'silent_chill_immersive' : 'safe_review'); }}>
              {initialWorkflow === 'silent' ? 'Đổi sang Chill Immersive' : 'Đổi sang Safe Review'}
            </GlassButton>
          </div>
        </div>
      </GlassModal>
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
                    {video.sidecar_srt_path ? 'SRT đi kèm' : video.embedded_subtitle_found ? 'Nhúng' : 'Cần nghe thoại'}
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

      {jobId && (results.length || jobStatus) ? (
        <section className="rounded-md border border-line bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button className={`px-3 py-2 text-sm font-semibold ${resultsTab === 'results' ? 'border-b-2 border-brand text-brand' : 'text-muted'}`} type="button" onClick={() => setResultsTab('results')}>
                Kết quả
              </button>
              <button className={`px-3 py-2 text-sm font-semibold ${resultsTab === 'final_qa' ? 'border-b-2 border-brand text-brand' : 'text-muted'}`} type="button" onClick={() => setResultsTab('final_qa')}>
                Đánh giá QA
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {failedResults.length ? (
                <button
                  className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand disabled:text-muted"
                  type="button"
                  disabled={busy || !jobId}
                  onClick={() => void handleRetryFailed()}
                >
                  Thử lại các video lỗi
                </button>
              ) : null}
              {reviewDocuments.length > 0 && jobId ? (
                <>
                  <button
                    className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand disabled:text-muted"
                    type="button"
                    disabled={busy}
                    onClick={() => void handleRenderApproved()}
                  >
                    Render các file đã duyệt
                  </button>
                  <Link
                    className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                    to={`/subtitle-review?job_id=${encodeURIComponent(jobId)}`}
                  >
                    Mở Subtitle Review
                  </Link>
                </>
              ) : null}
            </div>
          </div>
          <CustomRetryPanel
            busy={retryBusy}
            retryMode={retryMode}
            selectedCount={selectedResultIndexes.length}
            totalResults={results.length}
            onModeChange={setRetryMode}
            onContinueUnfinished={() => void handleCustomRetry(retryMode, [], true)}
            onRetrySelected={() => void handleCustomRetry(retryMode, selectedResultVideoIds, false)}
            onSelectProblemResults={selectFailedOrQaResults}
            onClearSelection={() => setSelectedResultIndexes([])}
            onOpenAdvanced={() => setAdvancedOpen(true)}
          />
          {resultsTab === 'results' && summary ? (
            <div className="mt-4 grid gap-2 text-sm sm:grid-cols-5">
              <Stat label="Cần duyệt" value={summary.needs_review ?? reviewDocuments.length} />
              <Stat label="Đã xuất" value={summary.rendered ?? results.filter((output) => output.status === 'success').length} />
              <Stat label="Lỗi" value={summary.failed ?? failedResults.length} />
              <Stat label="Im lặng" value={summary.silent_immersive?.videos_processed_silent ?? results.filter((output) => output.reup_mode === 'silent_immersive').length} />
              <Stat label="Chậm nhất" value={summary.performance?.slowest_step ?? '-'} />
            </div>
          ) : null}
          {resultsTab === 'results' ? <div className="mt-4 grid gap-5">
            {!results.length ? (
              <div className="rounded-md border border-dashed border-line p-4 text-sm text-muted">
                Chưa có video hoàn tất trong kết quả. Nếu lô bị dừng giữa chừng, hãy chỉnh cài đặt rồi bấm “Chạy tiếp phần còn lại”.
              </div>
            ) : null}
            {resultGroups.map((group) => group.items.length ? (
              <div key={group.title} className="grid gap-3">
                <div className="text-sm font-semibold text-ink">{group.title} ({group.items.length})</div>
                <div className="grid gap-4 lg:grid-cols-2">
            {group.items.map((output) => (
              <article key={output.index} className="rounded-md border border-line p-4">
                <div className="flex items-center justify-between gap-3">
                  <label className="flex items-center gap-2 text-sm font-semibold text-ink">
                    <input
                      type="checkbox"
                      checked={selectedResultIndexes.includes(output.index)}
                      onChange={() => toggleResultIndex(output.index)}
                    />
                    Video {output.index.toString().padStart(3, '0')}
                  </label>
                  <span className={statusClass(output.status)}>
                    {output.status}
                  </span>
                </div>
                {output.path ? (
                  <video className="mt-3 aspect-[9/16] max-h-[520px] w-full rounded-md bg-black object-contain" src={videoFileUrl(output.path)} controls />
                ) : null}
                <div className="mt-3 grid gap-1 break-all text-xs text-muted">
                  <div>Video đầu ra: {output.path || '-'}</div>
                  <div>Nguồn phụ đề: {formatSourceType(output.subtitle_source)}</div>
                  <div>SRT nguồn: {output.source_srt_file || '-'}</div>
                  <div>Phụ đề dịch: {output.translated_srt_file || '-'}</div>
                  <div>SRT đã sửa: {output.corrected_srt_file || '-'}</div>
                  <div>ASS: {output.corrected_ass_file || output.subtitle_ass_file || '-'}</div>
                  <div>Nhạc nền: {output.bgm_file || '-'}</div>
                  <div>Nhật ký: {output.log_file || '-'}</div>
                  <div>Bước lỗi: {output.failed_step || '-'}</div>
                </div>
                <CleanupResultNote output={output} />
                {output.reup_mode === 'silent_immersive' ? (
                  <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-900">
                    <div className="font-semibold">Chế độ: Video không thoại</div>
                    <div>Cách xử lý: {formatSilentStrategy(output.silent_strategy)}</div>
                    <div>Điểm phát hiện lời thoại: {Math.round((output.speech_score ?? 0) * 100)}%</div>
                    <div>Nguồn caption: {formatCaptionSource(output.caption_source)}</div>
                    {output.product_detection?.top_candidate ? (
                      <div>
                        Nhận diện sản phẩm: {formatProductDetectionLabel(output.product_detection)}
                        {' '}({Math.round((output.product_detection.average_confidence ?? 0) * 100)}%)
                      </div>
                    ) : null}
                    <div>Giọng đọc: {output.voiceover_file ? 'Có' : 'Không'}</div>
                    <div>BGM: {output.bgm_file ? 'Đã thêm' : 'Không'}</div>
                    <div className="break-all">Kế hoạch dựng: {output.silent_plan_file || '-'}</div>
                    <div className="break-all">Kịch bản giọng đọc: {output.voiceover_script_file || '-'}</div>
                    <div className="break-all">Phụ đề giọng đọc: {output.voiceover_subtitle_file || '-'}</div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {output.subtitle_review_document_id ? (
                        <button
                          className="rounded-md border border-emerald-300 bg-white px-3 py-1.5 text-xs font-semibold text-emerald-900 disabled:text-muted"
                          type="button"
                          disabled={busy || !jobId}
                          onClick={() => void handleRenderApproved()}
                        >
                          Xuất các file đã duyệt
                        </button>
                      ) : null}
                      <button
                        className="rounded-md border border-emerald-300 bg-white px-3 py-1.5 text-xs font-semibold text-emerald-900 disabled:text-muted"
                        type="button"
                        disabled={busy || !jobId}
                        onClick={() => void handleRetryOutputWithPreset(output, 'silent_product_voiceover')}
                      >
                        Thử lại với giọng đọc
                      </button>
                      <button
                        className="rounded-md border border-emerald-300 bg-white px-3 py-1.5 text-xs font-semibold text-emerald-900 disabled:text-muted"
                        type="button"
                        disabled={busy || !jobId}
                        onClick={() => void handleRetryOutputWithPreset(output, 'voice_priority')}
                      >
                        Thử lại bằng cách nghe thoại
                      </button>
                    </div>
                  </div>
                ) : null}
                {output.subtitle_source === 'ocr_hardsub' || output.ocr_debug_json_path ? (
                  <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                    <div className="font-semibold">Thông tin đọc chữ</div>
                    <div>Bộ đọc chữ: {output.ocr_provider || settings.ocr_provider}</div>
                    <div>Vùng quét: {output.ocr_region_mode || settings.ocr_region_mode}</div>
                    <div>Số khung hình đã quét: {output.ocr_frame_count ?? 0}</div>
                    <div>Số dòng chữ tìm thấy: {output.ocr_detected_line_count ?? 0}</div>
                    <div>Độ chắc chắn trung bình: {Math.round((output.ocr_average_confidence ?? 0) * 100)}%</div>
                    <div className="break-all">Debug JSON: {output.ocr_debug_json_path || '-'}</div>
                  </div>
                ) : null}
                {output.error_message ? <div className="mt-2 text-xs text-red-700">{output.error_message}</div> : null}
                {output.warnings.length ? <div className="mt-3 text-xs text-amber-700">{output.warnings.join('; ')}</div> : null}
                {output.errors.length ? <div className="mt-3 text-xs text-red-700">{output.errors.join('; ')}</div> : null}
                {output.status === 'failed' ? (
                  <div className="mt-3 flex flex-wrap items-end gap-2">
                    <label className="block">
                      <span className="mb-1 block text-xs font-semibold text-muted">Đổi Preset</span>
                      <select
                        className="h-9 rounded-md border border-line bg-white px-2 text-xs"
                        value={retryPresetByOutput[output.index] || selectedPresetId}
                        onChange={(event) =>
                          setRetryPresetByOutput((current) => ({ ...current, [output.index]: event.target.value }))
                        }
                      >
                        {presets.map((preset) => (
                          <option key={preset.id} value={preset.id}>
                            {preset.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      className="h-9 rounded-md border border-line px-3 text-xs font-semibold text-ink hover:border-brand disabled:text-muted"
                      type="button"
                      disabled={busy || !jobId}
                      onClick={() => void handleRetryWithPreset(output)}
                    >
                      Thử lại
                    </button>
                  </div>
                ) : null}
                {output.path ? (
                  <button
                    className="mt-3 rounded-md border border-line px-3 py-2 text-xs font-semibold text-ink hover:border-brand"
                    type="button"
                    onClick={() => copyToClipboard(output.path)}
                  >
                    Sao chép đường dẫn
                  </button>
                ) : null}
                {output.subtitle_review_document_id ? (
                  <Link
                    className="ml-2 mt-3 inline-block rounded-md bg-brand px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700"
                    to={`/subtitle-review/${output.subtitle_review_document_id}`}
                  >
                    {output.reup_mode === 'silent_immersive' ? 'Duyệt caption' : 'Duyệt phụ đề'}
                  </Link>
                ) : null}
              </article>
            ))}
                </div>
              </div>
            ) : null)}
          </div> : <FinalQAPanel
            busy={busy}
            jobId={jobId}
            outputs={results}
            summary={summary}
            platformTarget={platformTarget}
            setPlatformTarget={setPlatformTarget}
            selectedIndexes={exportOutputIndexes}
            toggleSelectedIndex={toggleExportOutput}
            onRunQA={handleRunFinalQA}
            onRetry={handleRetryWithPreset}
            exportOptions={exportOptions}
            setExportOptions={setExportOptions}
            onCreatePack={handleCreateExportPack}
            exportPack={exportPack}
            onOpenPack={handleOpenExportPack}
          />}
        </section>
      ) : null}
    </>
  );
}

function CleanupResultNote({ output }: { output: DouyinOutputResult }) {
  const report = output.cleanup_report;
  const manifestFile = output.publish_manifest_file || report?.publish_manifest_file;
  if (!report && !manifestFile) return null;
  const cleaned = report?.status === 'completed' && report.deleted_file_count > 0;
  const skipped = report?.status === 'skipped';
  return (
    <div className={`mt-3 rounded-md border p-3 text-xs leading-5 ${
      cleaned
        ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
        : skipped
        ? 'border-slate-200 bg-slate-50 text-slate-700'
        : 'border-amber-200 bg-amber-50 text-amber-900'
    }`}>
      <div className="font-semibold">Dọn file sau xử lý</div>
      {report ? (
        <div>
          {cleaned
            ? `Đã xóa ${report.deleted_file_count} file tạm, tiết kiệm ${formatBytes(report.deleted_size_bytes)}.`
            : skipped
            ? `Chưa xóa file tạm: ${cleanupSkipReasonLabel(report.skipped_reason)}.`
            : `Đã tạo báo cáo cleanup, cần kiểm tra thêm: ${cleanupSkipReasonLabel(report.skipped_reason)}.`}
        </div>
      ) : null}
      {manifestFile ? <div className="break-all">Hồ sơ xuất bản: {manifestFile}</div> : null}
      {report?.warnings?.length ? <div>Cảnh báo: {report.warnings.join('; ')}</div> : null}
      {report?.errors?.length ? <div>Lỗi cleanup: {report.errors.join('; ')}</div> : null}
    </div>
  );
}

function cleanupSkipReasonLabel(reason?: string | null): string {
  const labels: Record<string, string> = {
    keep_temp_enabled: 'đang bật giữ file tạm để debug',
    final_qa_failed: 'QA cuối chưa đạt nên giữ file debug',
    missing_final_mp4: 'chưa thấy MP4 cuối hợp lệ',
    empty_final_mp4: 'MP4 cuối đang rỗng',
  };
  return reason ? labels[reason] ?? reason.replaceAll('_', ' ') : 'không có file tạm cần xóa';
}

function CustomRetryPanel({
  busy,
  retryMode,
  selectedCount,
  totalResults,
  onModeChange,
  onContinueUnfinished,
  onRetrySelected,
  onSelectProblemResults,
  onClearSelection,
  onOpenAdvanced,
}: {
  busy: boolean;
  retryMode: DouyinRetryCustomMode;
  selectedCount: number;
  totalResults: number;
  onModeChange: (mode: DouyinRetryCustomMode) => void;
  onContinueUnfinished: () => void;
  onRetrySelected: () => void;
  onSelectProblemResults: () => void;
  onClearSelection: () => void;
  onOpenAdvanced: () => void;
}) {
  const currentMode = CUSTOM_RETRY_MODE_OPTIONS.find((option) => option.value === retryMode) ?? CUSTOM_RETRY_MODE_OPTIONS[0];

  return (
    <div className="mt-4 rounded-md border border-cyan-300/20 bg-slate-950/65 p-4 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-200">Chỉnh lại kết quả</div>
          <h3 className="mt-1 text-lg font-semibold text-white">Render lại video đã chọn</h3>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">
            Chọn video chưa ưng ý trong danh sách bên dưới, chỉnh cài đặt nếu cần rồi render lại ngay trong cùng lô.
          </p>
        </div>
        <button
          className="rounded-md border border-white/15 bg-white/8 px-3 py-2 text-sm font-semibold text-white hover:border-cyan-300/35 hover:bg-white/12"
          type="button"
          onClick={onOpenAdvanced}
        >
          Chỉnh vị trí sub
        </button>
      </div>

      <div className="mt-4 grid gap-3 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="grid gap-2 sm:grid-cols-3">
          {CUSTOM_RETRY_MODE_OPTIONS.map((option) => {
            const active = option.value === retryMode;
            return (
              <button
                key={option.value}
                aria-pressed={active}
                className={`min-h-28 rounded-md border p-3 text-left transition ${
                  active
                    ? 'border-cyan-300/70 bg-cyan-300/12 text-white shadow-[0_0_0_1px_rgba(103,232,249,0.16)]'
                    : 'border-white/10 bg-white/5 text-slate-300 hover:border-cyan-300/35 hover:bg-white/8'
                }`}
                type="button"
                onClick={() => onModeChange(option.value)}
              >
                <span className="block text-sm font-semibold">{option.label}</span>
                <span className="mt-2 block text-xs leading-5 text-slate-400">{option.description}</span>
              </button>
            );
          })}
        </div>

        <div className="rounded-md border border-white/10 bg-white/5 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Đang áp dụng</div>
              <div className="mt-1 text-sm font-semibold text-white">{currentMode.label}</div>
            </div>
            <span className="rounded-full border border-cyan-300/30 bg-cyan-300/10 px-3 py-1 text-xs font-semibold text-cyan-100">
              {selectedCount}/{totalResults} đã chọn
            </span>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-400">{currentMode.description}</p>
          <button
            className="mt-4 min-h-11 w-full rounded-md bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-200 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
            type="button"
            disabled={busy || selectedCount === 0}
            onClick={onRetrySelected}
          >
            {busy ? 'Đang tạo lô render lại...' : `Render lại đã chọn (${selectedCount})`}
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          className="rounded-md border border-white/15 bg-white/8 px-3 py-2 text-sm font-semibold text-white hover:border-cyan-300/35 hover:bg-white/12 disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
          disabled={busy}
          onClick={onContinueUnfinished}
        >
          Chạy tiếp phần còn lại
        </button>
        <button
          className="rounded-md border border-white/15 bg-white/8 px-3 py-2 text-sm font-semibold text-white hover:border-cyan-300/35 hover:bg-white/12 disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
          disabled={busy || totalResults === 0}
          onClick={onSelectProblemResults}
        >
          Chọn lỗi/QA fail
        </button>
        <button
          className="rounded-md border border-white/15 bg-transparent px-3 py-2 text-sm font-semibold text-slate-300 hover:border-cyan-300/35 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
          disabled={busy || selectedCount === 0}
          onClick={onClearSelection}
        >
          Bỏ chọn
        </button>
      </div>
    </div>
  );
}

function RunSummaryPanel({
  mode,
  preset,
  sourceFolder,
  outputFolder,
  scanSummary,
  checklist,
  validationMessages,
  job,
  jobStatus,
  disabled,
  loading,
  startLabel,
  addMusic,
  musicFolder,
  voiceoverEnabled,
  autoRouteEnabled,
  reviewMode,
  onOpenAdvanced,
  onStart,
}: {
  mode: StartWorkflowMode;
  preset?: StartPresetViewModel;
  sourceFolder: string;
  outputFolder: string;
  scanSummary: StartScanSummary | null;
  checklist: StartChecklistItem[];
  validationMessages: StartValidationMessage[];
  job: JobStartedView | null;
  jobStatus: JobStatus | null;
  disabled: boolean;
  loading: boolean;
  startLabel: string;
  addMusic: boolean;
  musicFolder: string;
  voiceoverEnabled: boolean;
  autoRouteEnabled: boolean;
  reviewMode: boolean;
  onOpenAdvanced: () => void;
  onStart: () => void;
}) {
  const blockingItems = checklist.filter((item) => item.status === 'missing');
  const warningItems = checklist.filter((item) => item.status === 'warning');
  const steps = compactWorkflowSteps(mode, preset);
  const ready = !disabled && !loading;
  const missingMusicFolder = addMusic && !musicFolder.trim();
  const visibleWarningItems = warningItems.filter((item) => !(missingMusicFolder && isMusicFolderWarning(`${item.id} ${item.label} ${item.message || ''}`)));
  const importantMessages = validationMessages
    .filter((message) => message.tone !== 'info')
    .filter((message) => !(missingMusicFolder && isMusicFolderWarning(message.message)))
    .slice(0, 3);

  return (
    <GlassCard className="grid content-start gap-4 p-5" strong>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-200">Trước khi chạy</div>
          <h2 className="mt-1 text-xl font-semibold text-white">Tóm tắt lô video</h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            Chỉ cần kiểm tra nhanh các mục dưới đây rồi bấm chạy.
          </p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${reviewMode ? 'border-amber-300/35 bg-amber-300/10 text-amber-100' : 'border-emerald-300/35 bg-emerald-300/10 text-emerald-100'}`}>
          {reviewMode ? 'Duyệt trước' : 'Xuất MP4'}
        </span>
      </div>

      {reviewMode ? (
        <div className="rounded-md border border-amber-300/25 bg-amber-300/10 p-3 text-sm leading-6 text-amber-100">
          <div className="flex gap-2">
            <AlertTriangle className="mt-1 shrink-0" size={16} />
            <span>Chế độ này sẽ tạo phụ đề để bạn duyệt trước. Tool chưa xuất MP4 final cho tới khi bạn bấm render sau khi duyệt.</span>
          </div>
        </div>
      ) : null}

      {job ? (
        <div className="rounded-md border border-emerald-300/20 bg-emerald-300/10 p-4 text-sm text-emerald-100">
          <div className="font-semibold">Batch đã bắt đầu</div>
          <div className="mt-1 break-all text-xs">Job: {job.jobId}</div>
          <div className="mt-1 text-xs">Project: {job.projectName}</div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link className="inline-flex min-h-10 items-center gap-2 rounded-md border border-white/15 bg-white/8 px-3 py-2 text-sm font-semibold text-white hover:bg-white/12" to={`/queue/douyin-reup/${job.jobId}`}>
              <Route size={16} />
              Xem tiến trình
            </Link>
            <Link className="inline-flex min-h-10 items-center gap-2 rounded-md border border-cyan-300/50 bg-cyan-300 px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-200" to={`/results/${job.jobId}`}>
              Mở kết quả
            </Link>
          </div>
        </div>
      ) : null}

      <div className="grid gap-2">
        <SummaryLine label="Nguồn video" value={sourceFolder ? scanSummary ? `${scanSummary.valid}/${scanSummary.total} video hợp lệ` : 'Đã chọn, nên scan trước' : 'Chưa chọn'} tone={sourceFolder ? 'ok' : 'missing'} />
        <SummaryLine label="Mẫu xử lý" value={preset?.name || 'Chưa chọn'} tone={preset ? 'ok' : 'missing'} />
        <SummaryLine label="Thư mục đầu ra" value={outputFolder ? compactPath(outputFolder) : 'Chưa chọn'} tone={outputFolder ? 'ok' : 'missing'} />
        <SummaryLine label="Nhạc nền" value={missingMusicFolder ? 'Bật, chưa chọn thư mục' : addMusic ? 'Bật' : 'Tắt'} tone={missingMusicFolder ? 'warning' : 'ok'} />
        <SummaryLine label="Tự phân luồng" value={autoRouteEnabled ? 'Bật' : 'Tắt'} tone="ok" />
        <SummaryLine label="Voiceover" value={voiceoverEnabled ? 'Bật' : 'Tắt'} tone={voiceoverEnabled ? 'warning' : 'ok'} />
      </div>

      <div className="grid gap-2 border-t border-white/10 pt-4">
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm font-semibold text-white">Quy trình sẽ chạy</div>
          {preset ? <span className="text-xs text-slate-400">{preset.autoRender ? 'Tự động xuất' : 'Có bước duyệt'}</span> : null}
        </div>
        <div className="grid gap-2">
          {steps.map((step, index) => (
            <div className="flex items-center gap-3 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" key={step}>
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-cyan-300/15 text-xs font-semibold text-cyan-100">{index + 1}</span>
              <span>{step}</span>
            </div>
          ))}
        </div>
      </div>

      {blockingItems.length || visibleWarningItems.length || importantMessages.length || missingMusicFolder ? (
        <div className="grid gap-2 border-t border-white/10 pt-4">
          <div className="text-sm font-semibold text-white">Cần chú ý</div>
          {missingMusicFolder ? <NoticeRow tone="warning" text="Bạn đang bật nhạc nền nhưng chưa chọn thư mục nhạc. Tool vẫn có thể chạy, nhưng nên chọn thư mục để tránh thiếu BGM." /> : null}
          {blockingItems.slice(0, 3).map((item) => <NoticeRow key={item.id} tone="error" text={`${item.label}: ${item.message || 'Chưa đủ thông tin.'}`} />)}
          {visibleWarningItems.slice(0, 3).map((item) => <NoticeRow key={item.id} tone="warning" text={`${item.label}: ${item.message || 'Nên kiểm tra lại.'}`} />)}
          {importantMessages.map((message) => <NoticeRow key={message.id} tone={message.tone} text={message.message} />)}
        </div>
      ) : (
        <div className="flex items-start gap-2 rounded-md border border-emerald-300/20 bg-emerald-300/10 p-3 text-sm text-emerald-100">
          <CheckCircle2 className="mt-0.5 shrink-0" size={16} />
          <span>Cấu hình chính đã sẵn sàng để chạy.</span>
        </div>
      )}

      {jobStatus ? (
        <div className="grid gap-3 border-t border-white/10 pt-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <Info size={16} className="text-cyan-200" />
            {jobStatus.status === 'queued' ? 'Batch đã bắt đầu' : jobStatus.status}
          </div>
          <JobProgressPanel progress={jobStatus.progress} currentStep={jobStatus.current_step} completed={jobStatus.completed_outputs} total={jobStatus.total_outputs} failed={jobStatus.failed_outputs} warnings={jobStatus.logs.filter((log) => log.level.toLowerCase() === 'warning').length} />
        </div>
      ) : null}

      <div className="grid gap-2 border-t border-white/10 pt-4">
        <GlassButton className="min-h-12 w-full text-base" variant="primary" loading={loading} disabled={!ready} onClick={onStart}>
          {loading ? <RefreshCw size={18} /> : <Play size={18} />}
          {loading ? 'Đang tạo job...' : startLabel}
        </GlassButton>
        <GlassButton className="w-full" variant="secondary" onClick={onOpenAdvanced}>
          <Settings2 size={16} />
          Mở cài đặt chuyên sâu
        </GlassButton>
      </div>
    </GlassCard>
  );
}

function SummaryLine({ label, value, tone }: { label: string; value: string; tone: 'ok' | 'warning' | 'missing' }) {
  const toneClass = tone === 'ok' ? 'text-emerald-200' : tone === 'warning' ? 'text-amber-200' : 'text-rose-200';
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-white/10 bg-slate-950/45 px-3 py-2 text-sm">
      <span className="text-slate-400">{label}</span>
      <span className={`max-w-[58%] truncate text-right font-semibold ${toneClass}`} title={value}>{value}</span>
    </div>
  );
}

function NoticeRow({ tone, text }: { tone: 'error' | 'warning' | 'info'; text: string }) {
  const className = tone === 'error' ? 'border-rose-300/20 bg-rose-400/10 text-rose-100' : tone === 'warning' ? 'border-amber-300/20 bg-amber-400/10 text-amber-100' : 'border-cyan-300/20 bg-cyan-300/10 text-cyan-100';
  const Icon = tone === 'error' || tone === 'warning' ? AlertTriangle : Info;
  return (
    <div className={`flex items-start gap-2 rounded-md border px-3 py-2 text-sm leading-6 ${className}`}>
      <Icon className="mt-1 shrink-0" size={15} />
      <span>{text}</span>
    </div>
  );
}

function compactWorkflowSteps(mode: StartWorkflowMode, preset?: StartPresetViewModel): string[] {
  if (mode === 'silent_immersive') {
    return ['Quét video', 'Tạo caption Việt', preset?.reviewRequired ? 'Duyệt caption' : 'Xuất MP4', 'Kiểm tra cuối'];
  }
  if (preset?.autoRender) return ['Quét video', 'Nghe/dịch phụ đề', 'Xuất MP4', 'Kiểm tra cuối'];
  return ['Quét video', 'Nghe/dịch phụ đề', 'Duyệt phụ đề', 'Xuất MP4'];
}

function isMusicFolderWarning(text: string): boolean {
  const normalized = text.toLowerCase();
  return (normalized.includes('music') || normalized.includes('nhạc')) && normalized.includes('thư mục');
}

function compactPath(path: string): string {
  const parts = path.replaceAll('\\', '/').split('/').filter(Boolean);
  if (parts.length <= 2) return path;
  return `${parts[0]}/.../${parts.at(-1)}`;
}

function AdvancedTuningSection({
  children,
  hasCustomSettings,
  onOpenAdvanced,
}: {
  children: ReactNode;
  hasCustomSettings: boolean;
  onOpenAdvanced: () => void;
}) {
  return (
    <details className="group grid gap-3 rounded-md border border-white/10 bg-white/[0.03]">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 p-5 marker:hidden">
        <span>
          <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-cyan-200">Không bắt buộc</span>
          <span className="mt-1 block text-lg font-semibold text-white">Tinh chỉnh thêm</span>
          <span className="mt-1 block text-sm leading-6 text-slate-400">
            Nhạc nền, tự phân luồng, ngữ cảnh sản phẩm và hiệu năng batch được giữ ở đây để màn chính gọn hơn.
          </span>
        </span>
        <span className="shrink-0 rounded-md border border-white/15 bg-white/8 px-3 py-2 text-sm font-semibold text-slate-100 group-open:hidden">
          Mở
        </span>
        <span className="hidden shrink-0 rounded-md border border-cyan-300/40 bg-cyan-300/10 px-3 py-2 text-sm font-semibold text-cyan-100 group-open:inline-flex">
          Thu gọn
        </span>
      </summary>
      <div className="grid gap-4 border-t border-white/10 p-5 pt-4">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-cyan-300/20 bg-cyan-300/8 p-3 text-sm text-cyan-100">
          <span>{hasCustomSettings ? 'Bạn đang dùng cấu hình đã tùy chỉnh.' : 'Các tinh chỉnh phổ biến nằm ngay bên dưới.'}</span>
          <GlassButton variant="secondary" onClick={onOpenAdvanced}>
            <Settings2 size={16} />
            Cài đặt chuyên sâu
          </GlassButton>
        </div>
        {children}
      </div>
    </details>
  );
}

function QuickTuningCard({
  mode,
  hasCustomSettings,
  autoRender,
  addMusic,
  voiceoverEnabled,
  autoRouteEnabled,
  onOpenAdvanced,
}: {
  mode: StartWorkflowMode;
  hasCustomSettings: boolean;
  autoRender: boolean;
  addMusic: boolean;
  voiceoverEnabled: boolean;
  autoRouteEnabled: boolean;
  onOpenAdvanced: () => void;
}) {
  const routeLabel = mode === 'silent_immersive' ? 'Tự chuyển video có thoại' : 'Tự chuyển video không thoại';
  const items = [
    { label: 'Xuất video', value: autoRender ? 'Tự động' : 'Duyệt trước' },
    { label: 'Nhạc nền', value: addMusic ? 'Bật' : 'Tắt' },
    { label: 'Giọng đọc', value: voiceoverEnabled ? 'Bật' : 'Tắt' },
    { label: routeLabel, value: autoRouteEnabled ? 'Bật' : 'Tắt' },
  ];

  return (
    <GlassCard className="grid content-start gap-4 p-5" strong>
      <div>
        <h2 className="font-semibold text-white">Tinh chỉnh nhanh</h2>
        <p className="mt-1 text-sm leading-6 text-slate-400">
          Các lựa chọn ảnh hưởng trực tiếp đến lô video lớn được gom ở đây để bạn không phải kéo sâu xuống dưới.
        </p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 2xl:grid-cols-1">
        {items.map((item) => (
          <div className="rounded-md border border-white/10 bg-slate-950/45 px-3 py-2" key={item.label}>
            <div className="text-xs uppercase tracking-wide text-slate-500">{item.label}</div>
            <div className="mt-1 text-sm font-semibold text-slate-100">{item.value}</div>
          </div>
        ))}
      </div>
      <button
        className="inline-flex min-h-10 items-center justify-center rounded-md border border-cyan-300/40 bg-cyan-300/10 px-4 py-2 text-sm font-semibold text-cyan-100 hover:bg-cyan-300/15"
        type="button"
        onClick={onOpenAdvanced}
      >
        {hasCustomSettings ? 'Mở cấu hình đã tùy chỉnh' : 'Mở cài đặt nâng cao'}
      </button>
    </GlassCard>
  );
}

function FinalQAPanel({
  busy,
  jobId,
  outputs,
  summary,
  platformTarget,
  setPlatformTarget,
  selectedIndexes,
  toggleSelectedIndex,
  onRunQA,
  onRetry,
  exportOptions,
  setExportOptions,
  onCreatePack,
  exportPack,
  onOpenPack,
}: {
  busy: boolean;
  jobId: string | null;
  outputs: DouyinOutputResult[];
  summary: DouyinReupSummary | null;
  platformTarget: PlatformTarget;
  setPlatformTarget: (value: PlatformTarget) => void;
  selectedIndexes: number[];
  toggleSelectedIndex: (index: number) => void;
  onRunQA: () => Promise<void>;
  onRetry: (output?: DouyinOutputResult) => Promise<void>;
  exportOptions: ExportOptions;
  setExportOptions: (updater: (current: ExportOptions) => ExportOptions) => void;
  onCreatePack: () => Promise<void>;
  exportPack: PlatformExportPack | null;
  onOpenPack: () => Promise<void>;
}) {
  const checkedOutputs = outputs.filter((output) => output.final_output_qa);
  const qaSummary = summary?.final_output_qa;
  const qaFailed = outputs.filter((output) => output.final_output_qa?.status === 'failed').length;
  const optionRows: Array<[keyof ExportOptions, string]> = [
    ['copy_videos', 'Bao gồm video'],
    ['include_subtitles', 'Bao gồm phụ đề'],
    ['include_logs', 'Bao gồm nhật ký'],
    ['include_captions', 'Bao gồm caption'],
    ['include_posting_checklist', 'Bao gồm checklist đăng bài'],
  ];
  return (
    <div className="mt-4 grid gap-5">
      <div className="grid gap-3 sm:grid-cols-5">
        <Stat label="Đã kiểm tra" value={qaSummary?.total_checked ?? checkedOutputs.length} />
        <Stat label="Đạt" value={qaSummary?.passed ?? checkedOutputs.filter((item) => item.final_output_qa?.status === 'passed').length} />
        <Stat label="Cảnh báo" value={qaSummary?.passed_with_warnings ?? checkedOutputs.filter((item) => item.final_output_qa?.status === 'passed_with_warnings').length} />
        <Stat label="Lỗi" value={qaSummary?.failed ?? qaFailed} />
        <Stat label="Trung bình" value={`${Math.round((qaSummary?.average_score ?? 0) * 100)}%`} />
      </div>
      <div className="flex flex-wrap items-end gap-3 border-y border-line py-4">
        <label>
          <span className="mb-1 block text-xs font-semibold uppercase text-muted">Nền tảng</span>
          <select className="h-10 rounded-md border border-line bg-white px-3 text-sm" value={platformTarget} onChange={(event) => setPlatformTarget(event.target.value as PlatformTarget)}>
            <option value="tiktok">TikTok</option>
            <option value="instagram_reels">Instagram Reels</option>
            <option value="youtube_shorts">YouTube Shorts</option>
            <option value="generic_vertical">Generic Vertical</option>
          </select>
        </label>
        <button className="h-10 rounded-md border border-line px-4 text-sm font-semibold text-ink hover:border-brand disabled:text-muted" type="button" disabled={busy || !jobId} onClick={() => void onRunQA()}>
          Chạy đánh giá QA
        </button>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {outputs.filter((output) => output.path).map((output) => {
          const qa = output.final_output_qa;
          return (
            <article className="rounded-md border border-line p-4" key={output.index}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-semibold text-ink">{output.path.split(/[\\/]/).pop() || `Video ${output.index}`}</div>
                  <div className={qaStatusClass(qa?.status)}>QA: {formatQaStatus(qa?.status)}</div>
                </div>
                <label className="flex items-center gap-2 text-xs text-muted">
                  <input type="checkbox" checked={selectedIndexes.includes(output.index)} onChange={() => toggleSelectedIndex(output.index)} />
                  Xuất file
                </label>
              </div>
              <div className="mt-3 text-sm font-semibold text-ink">Điểm số: {qa ? `${Math.round(qa.score * 100)}%` : 'Chưa kiểm tra'}</div>
              {qa?.issues.length ? (
                <div className="mt-3 grid gap-2 text-xs">
                  {qa.issues.map((issue, index) => (
                    <div className={issue.severity === 'critical' ? 'text-red-700' : 'text-amber-700'} key={`${issue.issue_type}-${index}`}>
                      <div className="font-semibold">{issue.message}</div>
                      {issue.suggestion ? <div className="text-muted">{issue.suggestion}</div> : null}
                    </div>
                  ))}
                </div>
              ) : <div className="mt-3 text-xs text-green-700">Không có vấn đề kỹ thuật.</div>}
              <div className="mt-4 flex flex-wrap gap-2">
                {qa?.report_path ? <a className="rounded-md border border-line px-3 py-2 text-xs font-semibold text-ink hover:border-brand" href={finalOutputQAReportUrl(qa.report_path)} target="_blank" rel="noreferrer">Mở báo cáo QA</a> : null}
                {qa?.status === 'failed' ? <button className="rounded-md border border-line px-3 py-2 text-xs font-semibold text-ink hover:border-brand disabled:text-muted" type="button" disabled={busy || !jobId} onClick={() => void onRetry(output)}>Render lại</button> : null}
              </div>
            </article>
          );
        })}
      </div>
      <div className="grid gap-4 border-t border-line pt-5">
        <div>
          <h3 className="text-base font-semibold text-ink">Gói xuất tệp tin cho nền tảng</h3>
          <p className="mt-1 text-xs text-muted">Chuẩn bị các tệp tin cục bộ để kiểm tra và đăng tải.</p>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {optionRows.map(([key, label]) => (
            <label className="flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-2 text-sm" key={key}>
              <input type="checkbox" checked={exportOptions[key]} onChange={(event) => setExportOptions((current) => ({ ...current, [key]: event.target.checked }))} />
              <span>{label}</span>
            </label>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white disabled:bg-blue-200" type="button" disabled={busy || !jobId || !selectedIndexes.length} onClick={() => void onCreatePack()}>
            Tạo gói xuất file
          </button>
          {exportPack ? <button className="rounded-md border border-line px-4 py-2 text-sm font-semibold text-ink" type="button" onClick={() => copyToClipboard(exportPack.output_dir)}>Sao chép đường dẫn</button> : null}
          {exportPack ? <button className="rounded-md border border-line px-4 py-2 text-sm font-semibold text-ink" type="button" onClick={() => void onOpenPack()}>Mở thư mục</button> : null}
        </div>
        {exportPack ? (
          <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-800">
            <div className="font-semibold">Đã tạo gói xuất file</div>
            <div className="break-all text-xs">{exportPack.output_dir}</div>
            <div className="mt-1 text-xs">{exportPack.items.filter((item) => item.exists).length} tệp tin sẵn sàng.</div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function copyToClipboard(value?: string | null) {
  if (!value) return;
  void navigator.clipboard?.writeText(value);
  emitNotification({ variant: 'success', message: 'Đã sao chép đường dẫn.' });
}

function toStartPresetViewModel(
  preset: DouyinReupPreset,
  mode: StartWorkflowMode,
  recommended: boolean,
): StartPresetViewModel {
  const autoRender = Boolean(
    preset.settings.auto_render_after_translation
    || preset.id === 'fast_auto'
    || preset.id === 'music_recut'
    || preset.id === 'silent_sales_recut'
  );
  return {
    id: preset.id,
    name: presetDisplayName(preset),
    description: shortPresetDescription(preset),
    badge: recommended ? undefined : presetBadge(preset),
    recommended,
    reviewRequired: Boolean((preset.settings.review_subtitles_before_render || preset.settings.silent_review_before_render) && !autoRender),
    autoRender,
    mode,
  };
}

function presetDisplayName(preset: DouyinReupPreset): string {
  const names: Record<string, string> = {
    safe_review: 'An toàn, có duyệt',
    fast_auto: 'Tự động nhanh',
    ocr_priority: 'Ưu tiên đọc chữ trên video',
    voice_priority: 'Ưu tiên nghe lời thoại',
    clean_subtitle_only: 'Chỉ làm phụ đề sạch',
    music_recut: 'Cắt lại kèm nhạc',
    silent_chill_immersive: 'Không thoại nhẹ nhàng',
    silent_product_voiceover: 'Giọng đọc sản phẩm',
    silent_sales_recut: 'Bán hàng ngắn gọn',
  };
  return names[preset.id] ?? preset.name;
}

function shortPresetDescription(preset: DouyinReupPreset): string {
  const descriptions: Record<string, string> = {
    safe_review: 'Dịch xong cho bạn kiểm tra trước khi render.',
    fast_auto: 'Tự dịch và render nhanh.',
    ocr_priority: 'Dành cho video có nhiều chữ Trung trên màn hình.',
    voice_priority: 'Dành cho video có lời thoại tiếng Trung rõ.',
    clean_subtitle_only: 'Chỉ tạo phụ đề sạch, ít hiệu ứng.',
    music_recut: 'Giữ sub, thêm nhạc nền nổi bật hơn.',
    silent_chill_immersive: 'Giữ vibe gốc, thêm caption Việt nhẹ.',
    silent_product_voiceover: 'Tạo voice review tiếng Việt từ cảnh quay.',
    silent_sales_recut: 'Caption ngắn, có hook và CTA.',
  };
  return descriptions[preset.id] ?? preset.description;
}

function presetBadge(preset: DouyinReupPreset): string {
  const badges: Record<string, string> = {
    safe_review: 'Khuyên dùng',
    fast_auto: 'Nhanh',
    ocr_priority: 'Đọc chữ',
    voice_priority: 'Nghe thoại',
    clean_subtitle_only: 'Chỉ phụ đề',
    music_recut: 'Nhạc',
    silent_chill_immersive: 'Khuyên dùng',
    silent_product_voiceover: 'Giọng đọc',
    silent_sales_recut: 'Bán hàng',
  };
  return badges[preset.id] ?? preset.ui_badge;
}

function strategyFromSilentPreset(presetId: string): string {
  if (presetId === 'silent_product_voiceover') return 'product_review_voiceover';
  if (presetId === 'silent_sales_recut') return 'sales_recut';
  return 'chill_immersive';
}

function pickRecommendedPresetId(
  mode: StartWorkflowMode,
  sourceFolder: string,
  recommendation: DouyinPresetRecommendationResponse | null,
  presets: DouyinReupPreset[],
): string {
  const presetIds = new Set(presets.map((preset) => preset.id));
  const lower = sourceFolder.toLowerCase();
  if (mode === 'silent_immersive') return presetIds.has('silent_chill_immersive') ? 'silent_chill_immersive' : presets.find((preset) => preset.id.startsWith('silent_'))?.id ?? '';
  if (recommendation?.preset_id && presetIds.has(recommendation.preset_id) && !recommendation.preset_id.startsWith('silent_')) return recommendation.preset_id;
  if (/(ocr|subtitle|sub|chinese|text|trung|zh)/i.test(lower) && presetIds.has('ocr_priority')) return 'ocr_priority';
  if (/(fast|quick|nhanh)/i.test(lower) && presetIds.has('fast_auto')) return 'fast_auto';
  return presetIds.has('safe_review') ? 'safe_review' : presets.find((preset) => !preset.id.startsWith('silent_'))?.id ?? '';
}

function recommendationReason(
  mode: StartWorkflowMode,
  sourceFolder: string,
  preset?: StartPresetViewModel,
): string {
  if (!preset) return '';
  if (mode === 'silent_immersive') return 'Video không thoại nên bắt đầu bằng mẫu nhẹ, giữ cảm giác gốc và cho bạn duyệt caption.';
  if (preset.id === 'ocr_priority') return 'Tên thư mục có tín hiệu chữ/phụ đề, nên ưu tiên đọc chữ trên video.';
  if (preset.id === 'fast_auto') return 'Tên thư mục có tín hiệu cần xử lý nhanh, mẫu này bỏ qua bớt bước duyệt.';
  if (sourceFolder.trim()) return 'An toàn hơn vì bạn có thể kiểm tra phụ đề trước khi xuất video.';
  return 'Mẫu mặc định an toàn cho lô mới.';
}

function buildChecklist({
  sourceFolder,
  outputFolder,
  selectedPreset,
  scanSummary,
  scanErrors,
  musicFolder,
  addMusic,
  backendReady,
  backendHealth,
  translationProvider,
  voiceoverEnabled,
  voiceProvider,
  autoRender,
}: {
  sourceFolder: string;
  outputFolder: string;
  selectedPreset?: StartPresetViewModel;
  scanSummary: StartScanSummary | null;
  scanErrors: string[];
  musicFolder: string;
  addMusic: boolean;
  backendReady: boolean;
  backendHealth: HealthResponse | null;
  translationProvider: string;
  voiceoverEnabled: boolean;
  voiceProvider: string;
  autoRender: boolean;
}): StartChecklistItem[] {
  const needsGemini = normalizeProviderId(translationProvider) === 'gemini';
  const hasGemini = backendHealth?.capabilities?.translation === true;
  const needsGoogleTts = voiceoverEnabled && normalizeProviderId(voiceProvider) === 'google_cloud_tts';
  const hasGoogleTts = backendHealth?.capabilities?.google_cloud_tts === true;
  return [
    {
      id: 'source',
      label: 'Folder video',
      status: sourceFolder.trim() ? (scanErrors.length ? 'missing' : scanSummary?.invalid ? 'warning' : 'ok') : 'missing',
      message: sourceFolder.trim()
        ? scanErrors.length
          ? scanErrors[0]
          : scanSummary
          ? `${scanSummary.valid} video hợp lệ${scanSummary.invalid ? `, ${scanSummary.invalid} file lỗi` : ''}.`
          : 'Có folder, hãy scan để kiểm tra nhanh.'
        : 'Chưa chọn folder video.',
    },
    {
      id: 'preset',
      label: 'Mẫu cấu hình',
      status: selectedPreset ? (autoRender ? 'warning' : 'ok') : 'missing',
      message: selectedPreset ? selectedPreset.name : 'Chưa chọn mẫu cấu hình.',
    },
    {
      id: 'output',
      label: 'Thư mục đầu ra',
      status: outputFolder.trim() ? 'ok' : 'missing',
      message: outputFolder.trim() ? 'Tool sẽ kiểm tra quyền ghi khi bắt đầu xử lý.' : 'Chưa chọn thư mục đầu ra.',
    },
    {
      id: 'music',
      label: 'Music',
      status: addMusic ? (musicFolder.trim() ? 'ok' : 'missing') : 'ok',
      message: addMusic
        ? musicFolder.trim()
          ? 'Đã chọn thư mục nhạc nền.'
          : 'Đang bật nhạc nền nhưng chưa chọn thư mục nhạc.'
        : 'Không thêm nhạc nền.',
    },
    {
      id: 'translation',
      label: 'Dịch thuật',
      status: needsGemini ? (hasGemini ? 'ok' : 'warning') : 'ok',
      message: needsGemini
        ? hasGemini
          ? 'Gemini đã sẵn sàng để dịch hoặc tạo nội dung.'
          : 'Chưa xác nhận được khóa API Gemini. Nếu quy trình cần Gemini, tool sẽ dừng trước khi chạy.'
        : 'Flow hiện tại không yêu cầu Gemini.',
    },
    {
      id: 'tts',
      label: 'Giọng đọc',
      status: needsGoogleTts ? (hasGoogleTts ? 'ok' : 'missing') : 'ok',
      message: voiceoverEnabled
        ? needsGoogleTts
          ? hasGoogleTts
            ? 'Google Cloud TTS đã có thông tin đăng nhập.'
            : 'Bạn đã chọn Google Cloud TTS nhưng chưa cấu hình API key, access token hoặc file service account.'
          : 'Đã chọn dịch vụ giọng đọc không cần Google credential.'
        : 'Không tạo giọng đọc tiếng Việt.',
    },
    {
      id: 'backend',
      label: 'Bộ xử lý',
      status: backendReady ? 'ok' : 'warning',
      message: backendReady ? 'Đã kết nối.' : 'Bộ xử lý sẽ được kiểm tra lại khi bắt đầu.',
    },
  ];
}

function normalizeProviderId(value: string | null | undefined): string {
  return (value || '').trim().toLowerCase().replace(/-/g, '_');
}

function buildValidationMessages(
  checklist: StartChecklistItem[],
  preset: StartPresetViewModel | undefined,
  dependencyStatus: SystemDependencyStatusResponse | null,
  scanSummary: StartScanSummary | null,
  autoRender: boolean,
): StartValidationMessage[] {
  const messages: StartValidationMessage[] = [];
  checklist
    .filter((item) => item.status === 'missing')
    .forEach((item) => messages.push({ id: `missing-${item.id}`, tone: 'error', message: item.message || `${item.label} đang thiếu.` }));
  if (!dependencyStatus) messages.push({ id: 'backend', tone: 'warning', message: 'Bộ xử lý đang tắt hoặc chưa phản hồi. Hãy khởi động lại tool rồi thử lại.' });
  if (scanSummary?.invalid) messages.push({ id: 'scan-invalid', tone: 'warning', message: `Folder có ${scanSummary.invalid} file không đọc được. Tool sẽ bỏ qua hoặc bạn có thể kiểm tra lại.` });
  if (autoRender) messages.push({ id: 'auto-render', tone: 'warning', message: `${preset?.name ?? 'Chế độ hiện tại'} sẽ xuất MP4 ngay, không chờ duyệt phụ đề/caption.` });
  if (preset?.id === 'ocr_priority' && dependencyStatus && !dependencyStatus.ocr_available) {
    messages.push({ id: 'ocr', tone: 'warning', message: 'Mẫu ưu tiên đọc chữ cần bộ đọc chữ trên video. Nếu bộ đọc chữ chưa sẵn sàng, tool có thể dùng phương án dự phòng hoặc báo lỗi rõ.' });
  }
  return messages.slice(0, 4);
}

function RenderFlowCard({
  mode,
  reviewMode,
  onModeChange,
}: {
  mode: StartWorkflowMode;
  reviewMode: boolean;
  onModeChange: (mode: 'review' | 'auto') => void;
}) {
  const isSilent = mode === 'silent_immersive';
  const reviewTitle = isSilent ? 'Tạo caption để duyệt trước' : 'Tạo phụ đề để duyệt trước';
  const reviewDescription = isSilent
    ? 'Batch sẽ dừng ở bước duyệt caption. Chưa có MP4 final cho tới khi bạn duyệt và render.'
    : 'Batch sẽ dừng ở màn Sửa phụ đề. Chưa có MP4 final cho tới khi bạn duyệt và render.';
  const autoDescription = isSilent
    ? 'Tool tạo caption và xuất MP4 luôn. Phù hợp khi cần xử lý nhanh.'
    : 'Tool nghe lời thoại hoặc đọc chữ, dịch phụ đề và xuất MP4 luôn.';

  return (
    <GlassCard className="grid gap-4 p-5" strong>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">Cách xuất video</div>
          <h2 className="mt-2 text-xl font-semibold text-white">{reviewMode ? 'Tạo phụ đề để duyệt, chưa xuất MP4' : 'Xuất MP4 ngay sau khi dịch'}</h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            Đây là lựa chọn quan trọng nhất trước khi chạy batch.
          </p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${reviewMode ? 'border-amber-300/35 bg-amber-300/10 text-amber-100' : 'border-emerald-300/35 bg-emerald-300/10 text-emerald-100'}`}>
          {reviewMode ? 'Chưa có MP4' : 'Xuất ngay'}
        </span>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <RenderFlowOption
          active={reviewMode}
          title={reviewTitle}
          description={reviewDescription}
          onClick={() => onModeChange('review')}
        />
        <RenderFlowOption
          active={!reviewMode}
          title="Xuất MP4 ngay sau khi dịch"
          description={autoDescription}
          onClick={() => onModeChange('auto')}
        />
      </div>
    </GlassCard>
  );
}

function RenderFlowOption({
  active,
  title,
  description,
  onClick,
}: {
  active: boolean;
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-pressed={active}
      className={`min-h-28 rounded-md border p-4 text-left transition ${
        active
          ? 'border-cyan-300/70 bg-cyan-300/12 shadow-[0_0_0_1px_rgba(103,232,249,0.16)]'
          : 'border-white/10 bg-white/5 hover:border-cyan-300/35 hover:bg-white/8'
      }`}
      type="button"
      onClick={onClick}
    >
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border ${active ? 'border-cyan-200 bg-cyan-300 text-slate-950' : 'border-white/25 text-transparent'}`}>
          <span className="h-2 w-2 rounded-full bg-current" />
        </span>
        <span>
          <span className="block text-sm font-semibold text-white">{title}</span>
          <span className="mt-1 block text-sm leading-6 text-slate-400">{description}</span>
        </span>
      </div>
    </button>
  );
}

function AutoRouteSpeechCard({
  enabled,
  threshold,
  voiceoverEnabled,
  onEnabledChange,
  onThresholdChange,
}: {
  enabled: boolean;
  threshold: number;
  voiceoverEnabled: boolean;
  onEnabledChange: (value: boolean) => void;
  onThresholdChange: (value: number) => void;
}) {
  return (
    <GlassCard className="grid gap-4 p-5" strong>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">Tự phân luồng</div>
          <h2 className="mt-2 text-xl font-semibold text-white">Tự chuyển video có thoại</h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            Khi chạy lô video không thoại, tool sẽ kiểm tra nhanh từng video. Video có dấu hiệu lời thoại sẽ tự chuyển sang quy trình có thoại để dịch và xuất video, không cần bạn chọn tay.
          </p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${enabled ? 'border-emerald-300/35 bg-emerald-300/10 text-emerald-100' : 'border-white/15 bg-white/5 text-slate-300'}`}>
          {enabled ? 'Đang bật' : 'Đang tắt'}
        </span>
      </div>
      <label className="flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
        <input type="checkbox" checked={enabled} onChange={(event) => onEnabledChange(event.target.checked)} />
        <span>Tự động chuyển video có thoại sang quy trình có thoại</span>
      </label>
      <SliderInput
        label={`Ngưỡng nhận diện thoại: ${Math.round(threshold * 100)}%`}
        min={0.1}
        max={0.6}
        step={0.01}
        value={threshold}
        onChange={(value) => {
          if (enabled) onThresholdChange(value);
        }}
      />
      {enabled && voiceoverEnabled ? (
        <div className="rounded-md border border-emerald-300/20 bg-emerald-300/10 p-3 text-xs leading-5 text-emerald-100">
          Nếu video được chuyển sang quy trình có thoại và đang bật giọng đọc tiếng Việt, audio gốc sẽ được tắt cho video đó để tránh hai giọng chồng nhau.
        </div>
      ) : null}
    </GlassCard>
  );
}

function BatchReliabilityCard({
  mode,
  chunkSize,
  ffmpegTimeoutSeconds,
  watchdogMinutes,
  asrMaxAudioSeconds,
  pauseOnRepeatedFailures,
  maxConsecutiveFailures,
  onChange,
}: {
  mode: string;
  chunkSize: number;
  ffmpegTimeoutSeconds: number;
  watchdogMinutes: number;
  asrMaxAudioSeconds: number;
  pauseOnRepeatedFailures: boolean;
  maxConsecutiveFailures: number;
  onChange: (updates: Partial<DouyinReupSettings>) => void;
}) {
  function applyMode(nextMode: 'safe' | 'balanced' | 'fast') {
    const presets = {
      safe: {
        batch_performance_mode: 'safe',
        batch_chunk_size: 25,
        batch_ffmpeg_timeout_seconds: 900,
        batch_item_timeout_seconds: 1800,
        batch_watchdog_stale_minutes: 20,
        asr_max_audio_seconds: 180,
        batch_pause_on_repeated_failures: true,
        batch_max_consecutive_failures: 5,
      },
      balanced: {
        batch_performance_mode: 'balanced',
        batch_chunk_size: 50,
        batch_ffmpeg_timeout_seconds: 900,
        batch_item_timeout_seconds: 1800,
        batch_watchdog_stale_minutes: 20,
        asr_max_audio_seconds: 180,
        batch_pause_on_repeated_failures: true,
        batch_max_consecutive_failures: 10,
      },
      fast: {
        batch_performance_mode: 'fast',
        batch_chunk_size: 100,
        batch_ffmpeg_timeout_seconds: 1200,
        batch_item_timeout_seconds: 2400,
        batch_watchdog_stale_minutes: 30,
        asr_max_audio_seconds: 240,
        batch_pause_on_repeated_failures: true,
        batch_max_consecutive_failures: 15,
      },
    } satisfies Record<string, Partial<DouyinReupSettings>>;
    onChange(presets[nextMode]);
  }

  return (
    <GlassCard className="grid gap-4 p-5" strong>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">Batch lớn</div>
          <h2 className="mt-2 text-xl font-semibold text-white">Hiệu năng và chống kẹt</h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            Dùng cho lô nhiều video chạy qua đêm. Tool sẽ chia nhỏ, giới hạn bước xuất video/nghe thoại và tự tạm dừng nếu lỗi lặp lại.
          </p>
        </div>
        <span className="rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1 text-xs font-semibold text-cyan-100">
          {mode === 'fast' ? 'Nhanh' : mode === 'balanced' ? 'Cân bằng' : 'An toàn'}
        </span>
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        {(['safe', 'balanced', 'fast'] as const).map((item) => (
          <button
            key={item}
            type="button"
            className={`rounded-md border px-3 py-2 text-sm font-semibold transition ${
              mode === item
                ? 'border-cyan-300/70 bg-cyan-300/15 text-cyan-50'
                : 'border-white/10 bg-white/5 text-slate-300 hover:border-cyan-300/35'
            }`}
            onClick={() => applyMode(item)}
          >
            {item === 'safe' ? 'An toàn' : item === 'balanced' ? 'Cân bằng' : 'Nhanh'}
          </button>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SliderInput
          label={`Kích thước mỗi lô: ${chunkSize} video`}
          min={10}
          max={200}
          step={5}
          value={chunkSize}
          onChange={(value) => onChange({ batch_chunk_size: Math.round(value) })}
        />
        <SliderInput
          label={`Giới hạn thời lượng nghe thoại: ${asrMaxAudioSeconds}s`}
          min={60}
          max={600}
          step={30}
          value={asrMaxAudioSeconds}
          onChange={(value) => onChange({ asr_max_audio_seconds: Math.round(value) })}
        />
        <SliderInput
          label={`Thời gian chờ xuất video: ${Math.round(ffmpegTimeoutSeconds / 60)} phút`}
          min={300}
          max={3600}
          step={60}
          value={ffmpegTimeoutSeconds}
          onChange={(value) => onChange({ batch_ffmpeg_timeout_seconds: Math.round(value), batch_item_timeout_seconds: Math.max(Math.round(value) * 2, 600) })}
        />
        <SliderInput
          label={`Watchdog cảnh báo sau: ${watchdogMinutes} phút`}
          min={5}
          max={120}
          step={5}
          value={watchdogMinutes}
          onChange={(value) => onChange({ batch_watchdog_stale_minutes: Math.round(value) })}
        />
      </div>

      <div className="grid gap-3 rounded-md border border-white/10 bg-white/5 p-3">
        <label className="flex items-center gap-2 text-sm text-slate-200">
          <input
            type="checkbox"
            checked={pauseOnRepeatedFailures}
            onChange={(event) => onChange({ batch_pause_on_repeated_failures: event.target.checked })}
          />
          <span>Tự tạm dừng khi nhiều video liên tiếp bị lỗi</span>
        </label>
        {pauseOnRepeatedFailures ? (
          <SliderInput
            label={`Ngưỡng lỗi liên tiếp: ${maxConsecutiveFailures} video`}
            min={3}
            max={30}
            step={1}
            value={maxConsecutiveFailures}
            onChange={(value) => onChange({ batch_max_consecutive_failures: Math.round(value) })}
          />
        ) : null}
      </div>
    </GlassCard>
  );
}

function PostProcessCleanupCard({
  autoCleanup,
  onAutoCleanupChange,
}: {
  autoCleanup: boolean;
  onAutoCleanupChange: (value: boolean) => void;
}) {
  return (
    <GlassCard className="grid gap-4 p-5" strong>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">Dung lượng</div>
          <h2 className="mt-2 text-xl font-semibold text-white">Dọn file tạm sau xử lý</h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            Sau khi video đã render thành công, tool giữ lại MP4 cuối, phụ đề, log và hồ sơ xuất bản. Các frame/crop/audio tạm sẽ được xóa để tiết kiệm ổ cứng.
          </p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${autoCleanup ? 'border-emerald-300/35 bg-emerald-300/10 text-emerald-100' : 'border-amber-300/35 bg-amber-300/10 text-amber-100'}`}>
          {autoCleanup ? 'Tự dọn' : 'Giữ file tạm'}
        </span>
      </div>
      <label className="flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
        <input type="checkbox" checked={autoCleanup} onChange={(event) => onAutoCleanupChange(event.target.checked)} />
        <span>Tự dọn file tạm sau khi render thành công</span>
      </label>
      <div className="grid gap-2 text-xs leading-5 text-slate-400 sm:grid-cols-2">
        <div className="rounded-md border border-emerald-300/20 bg-emerald-300/10 p-3 text-emerald-100">
          Giữ lại: MP4 cuối, phụ đề, log, QA report, manifest để sau này đăng video hoặc lên lịch.
        </div>
        <div className="rounded-md border border-slate-500/20 bg-slate-950/45 p-3">
          Xóa khi an toàn: frame quét, crop OCR, bản copy source.mp4 trong output và audio trung gian.
        </div>
      </div>
      {!autoCleanup ? (
        <div className="rounded-md border border-amber-300/25 bg-amber-300/10 p-3 text-xs leading-5 text-amber-100">
          Chỉ nên tắt khi bạn đang debug lỗi render hoặc cần giữ toàn bộ file trung gian để kiểm tra sâu.
        </div>
      ) : null}
    </GlassCard>
  );
}

function AutoRouteNoSpeechCard({
  enabled,
  onEnabledChange,
}: {
  enabled: boolean;
  onEnabledChange: (value: boolean) => void;
}) {
  return (
    <GlassCard className="grid gap-4 p-5" strong>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">Tự phân luồng</div>
          <h2 className="mt-2 text-xl font-semibold text-white">Tự chuyển video không thoại</h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            Khi chạy lô video có thoại nhưng một video không có phụ đề hoặc lời thoại đủ rõ, tool sẽ tự chuyển video đó sang quy trình không thoại để tạo caption theo cảnh thay vì đánh lỗi.
          </p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${enabled ? 'border-emerald-300/35 bg-emerald-300/10 text-emerald-100' : 'border-white/15 bg-white/5 text-slate-300'}`}>
          {enabled ? 'Đang bật' : 'Đang tắt'}
        </span>
      </div>
      <label className="flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
        <input type="checkbox" checked={enabled} onChange={(event) => onEnabledChange(event.target.checked)} />
        <span>Tự động chuyển video không thoại sang Silent Mode</span>
      </label>
      {enabled ? (
        <div className="rounded-md border border-sky-300/20 bg-sky-300/10 p-3 text-xs leading-5 text-sky-100">
          Video được chuyển sẽ dùng cài đặt nhạc, khung phủ và giọng đọc hiện tại. Tool vẫn ghi log nội bộ để bạn dễ lọc lại nhóm video này trong kết quả, không cần nhớ mã kỹ thuật.
        </div>
      ) : null}
    </GlassCard>
  );
}

function VoiceoverCard({
  mode,
  enabled,
  provider,
  voice,
  onEnabledChange,
  onVoiceChange,
}: {
  mode: StartWorkflowMode;
  enabled: boolean;
  provider: string;
  voice: string;
  onEnabledChange: (value: boolean) => void;
  onVoiceChange: (value: string) => void;
}) {
  const isSilent = mode === 'silent_immersive';
  const selectedValue = `${provider}:${voice}`;
  const [favoriteGoogleVoices, setFavoriteGoogleVoices] = useState<string[]>([]);
  useEffect(() => {
    let mounted = true;
    getAppSettings()
      .then((settings) => {
        if (mounted) setFavoriteGoogleVoices(settings.google_tts_favorite_voices ?? []);
      })
      .catch(() => {
        if (mounted) setFavoriteGoogleVoices([]);
      });
    return () => {
      mounted = false;
    };
  }, []);
  const voiceOptions = useMemo(() => {
    const options = [...VIETNAMESE_TTS_VOICES];
    const existing = new Set(options.map((item) => `${item.provider}:${item.voice}`));
    for (const favoriteVoice of favoriteGoogleVoices) {
      const value = favoriteVoice.trim();
      const key = `google_cloud_tts:${value}`;
      if (!value || existing.has(key)) continue;
      options.push({
        provider: 'google_cloud_tts',
        voice: value,
        label: `Google Cloud - ${value} (đã đánh dấu sao)`,
      });
      existing.add(key);
    }
    return options;
  }, [favoriteGoogleVoices]);
  return (
    <GlassCard className="grid gap-4 p-5" strong>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">Giọng đọc</div>
          <h2 className="mt-2 text-xl font-semibold text-white">Voiceover tiếng Việt</h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            {isSilent
              ? 'Tạo lời đọc tiếng Việt từ caption/kịch bản của video không thoại.'
              : 'Tạo lời đọc tiếng Việt từ phụ đề đã dịch và trộn vào video có thoại.'}
          </p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${enabled ? 'border-emerald-300/35 bg-emerald-300/10 text-emerald-100' : 'border-white/15 bg-white/5 text-slate-300'}`}>
          {enabled ? 'Có voice' : 'Không voice'}
        </span>
      </div>
      <label className="flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
        <input type="checkbox" checked={enabled} onChange={(event) => onEnabledChange(event.target.checked)} />
        <span>Tạo giọng đọc tiếng Việt</span>
      </label>
      <label className="block">
        <span className="mb-1.5 block text-sm font-medium text-slate-200">Chọn giọng đọc</span>
        <select
          className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white"
          disabled={!enabled}
          value={selectedValue}
          onChange={(event) => onVoiceChange(event.target.value)}
        >
          {voiceOptions.map((item) => (
            <option key={`${item.provider}:${item.voice}`} value={`${item.provider}:${item.voice}`}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      {enabled && provider === 'google_cloud_tts' ? (
        <div className="rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-xs leading-5 text-amber-100">
          Google Cloud TTS cần khóa API hoặc Service Account trong Cài đặt hệ thống. Nếu chưa cấu hình, tool sẽ dừng trước khi render.
        </div>
      ) : null}
    </GlassCard>
  );
}

function isVietnameseSubtitleStylePresetActive(preset: VietnameseSubtitleStylePreset, settings: DouyinReupSettings): boolean {
  return Object.entries(preset.settings).every(([key, expected]) => {
    const current = settings[key as keyof DouyinReupSettings];
    if (typeof expected === 'number' && typeof current === 'number') {
      return Math.abs(current - expected) < 0.001;
    }
    return current === expected;
  });
}

function hexToRgba(hexColor: string | undefined, opacity = 1): string {
  const cleaned = (hexColor || '#000000').trim().replace('#', '');
  if (!/^[0-9a-fA-F]{6}$/.test(cleaned)) {
    return `rgba(0, 0, 0, ${Math.max(0, Math.min(1, opacity))})`;
  }
  const red = parseInt(cleaned.slice(0, 2), 16);
  const green = parseInt(cleaned.slice(2, 4), 16);
  const blue = parseInt(cleaned.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${Math.max(0, Math.min(1, opacity))})`;
}

function clampNumber(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-2">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md bg-surface p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="text-lg font-semibold text-ink">{value}</div>
    </div>
  );
}

function statusClass(status: string): string {
  if (status === 'success') return 'text-sm font-semibold text-green-700';
  if (status === 'needs_review') return 'text-sm font-semibold text-amber-700';
  return 'text-sm font-semibold text-red-700';
}

function qaStatusClass(status?: string): string {
  if (status === 'passed') return 'mt-1 text-xs font-semibold text-green-700';
  if (status === 'failed') return 'mt-1 text-xs font-semibold text-red-700';
  return 'mt-1 text-xs font-semibold text-amber-700';
}

function formatQaStatus(status?: string): string {
  if (!status) return 'Chưa kiểm tra';
  const labels: Record<string, string> = {
    passed: 'Đạt',
    failed: 'Thất bại',
    passed_with_warnings: 'Đạt (có cảnh báo)',
  };
  return labels[status] ?? status.replaceAll('_', ' ');
}

function formatSourceType(source?: string | null): string {
  const labels: Record<string, string> = {
    sidecar_srt: 'File .srt đi kèm',
    embedded_subtitle: 'Phụ đề có sẵn trong video',
    asr: 'Nghe lời thoại',
    ocr_hardsub: 'Đọc chữ dính trên video',
    ocr_translation: 'Chữ trên video đã dịch',
    visual_generated: 'Caption tạo từ cảnh quay',
    template: 'Caption theo mẫu',
    none: 'Không có',
  };
  return source ? labels[source] ?? source : '-';
}

function formatSilentStrategy(strategy?: string | null): string {
  const labels: Record<string, string> = {
    chill_immersive: 'Chill immersive',
    product_review_voiceover: 'Tạo voice review Việt',
    sales_recut: 'Recut bán hàng nhanh',
  };
  return strategy ? labels[strategy] ?? strategy : '-';
}

function formatCaptionSource(source?: string | null): string {
  const labels: Record<string, string> = {
    ocr_translation: 'Chữ trên video đã dịch',
    visual_generated: 'Caption tạo từ cảnh quay',
    template: 'Theo mẫu',
    manual: 'Tự chỉnh',
  };
  return source ? labels[source] ?? source : '-';
}

function formatProductDetectionLabel(report?: DouyinOutputResult['product_detection'] | null): string {
  const candidate = report?.top_candidate;
  if (!candidate) return 'Chưa nhận diện';
  return candidate.product_name || candidate.product_type || candidate.display_name || 'Sản phẩm trong video';
}

function buildSilentProductContext(context: SilentProductContext): Record<string, unknown> {
  const features = context.features
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  const selectedIndustry = context.industry && !['auto', 'general_product'].includes(context.industry)
    ? context.industry
    : null;
  const hasManualContext = Boolean(context.product_name.trim() || features.length || selectedIndustry);
  const lockContext = Boolean(selectedIndustry);
  return {
    product_name: context.product_name.trim(),
    category: selectedIndustry,
    industry: selectedIndustry,
    features,
    cta: context.cta.trim(),
    product_context_lock_enabled: lockContext,
    auto_detect_product_context: !hasManualContext,
    locked_product_name: context.product_name.trim() || null,
    locked_industry: selectedIndustry,
    locked_product_keywords: features,
  };
}

function withAutoIndustry(items: Array<{ id: string; name: string }>): Array<{ id: string; name: string }> {
  const auto = { id: 'auto', name: 'Tự nhận diện từ video' };
  const cleaned = items.filter((item) => item.id !== 'auto');
  return [auto, ...cleaned.map((item) => ({
    ...item,
    name: VIETNAMESE_INDUSTRY_LABELS[item.id] || item.name,
  }))];
}

const VIETNAMESE_INDUSTRY_LABELS: Record<string, string> = {
  general_product: 'Sản phẩm chung',
  home_goods: 'Đồ gia dụng',
  kitchen_goods: 'Đồ nhà bếp',
  storage_organization: 'Đồ sắp xếp/lưu trữ',
  desk_setup: 'Góc bàn/làm việc',
  dorm_goods: 'Phòng nhỏ/ký túc xá',
  beauty_goods: 'Mỹ phẩm/làm đẹp',
  cleaning_goods: 'Đồ vệ sinh/lau dọn',
};

function formatCaptionTime(seconds: number): string {
  const safe = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(safe / 60);
  const remainder = safe % 60;
  return `${minutes}:${String(remainder).padStart(2, '0')}`;
}

function formatVisualTag(value?: string | null): string {
  if (!value) return '-';
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatTagSourceSummary(sources: Record<string, number>): string {
  const entries = Object.entries(sources).filter(([, count]) => count > 0);
  if (!entries.length) return 'No strong keyword source; visual rules were used.';
  return entries.map(([source, count]) => `${source.replaceAll('_', ' ')} (${count})`).join(', ');
}

function formatOcrDependencyStatus(status: SystemDependencyStatusResponse | null): string {
  if (!status) return 'Đang kiểm tra bộ đọc chữ trên video khi khởi động.';
  if (status.ocr_available) return `Bộ đọc chữ đã sẵn sàng: ${status.ocr_provider || 'mặc định'}.`;
  return status.ocr_message || 'Tool đang tự chuẩn bị bộ đọc chữ trong nền.';
}
