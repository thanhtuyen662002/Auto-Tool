# Kế hoạch Triển khai Cân bằng Dòng thời gian Tự động (Voice Sync Revised Plan)

Bản kế hoạch này cập nhật chi tiết các bước thiết kế và triển khai tính năng **Timeline Auto-Balancer** (Cân bằng Dòng thời gian Tự động) theo cấu trúc module tinh chỉnh mới.

---

## 1. Cấu hình & Kiểu dữ liệu mới (Configuration & Schemas)

### 1.1. Backend Schemas
Trong [project_schema.py](file:///d:/Projects/Auto-Tool/backend/app/schemas/project_schema.py):
- `RenderSettings` bổ sung:
  ```python
  auto_balance_timeline: bool = True
  enable_end_zoom: bool = True
  max_auto_extension_seconds: float = 8.0
  ```
- `TimelineClip` bổ sung:
  ```python
  freeze_frame: bool = False
  slow_zoom: bool = False
  ```

### 1.2. Frontend Types & Defaults
Trong [project.ts](file:///d:/Projects/Auto-Tool/frontend/src/types/project.ts) và [defaults.ts](file:///d:/Projects/Auto-Tool/frontend/src/config/defaults.ts):
- Đồng bộ các trường cấu hình trên vào kiểu `RenderSettings` và `TimelineClip`.
- Bổ sung các thông số report cân bằng vào `JobOutput`:
  ```typescript
  voice_duration?: number | null;
  video_duration?: number | null;
  auto_balance_applied?: boolean | null;
  strategy?: string | null;
  added_duration?: number | null;
  ```
- Mặc định: `auto_balance_timeline = true`, `enable_end_zoom = true`, `max_auto_extension_seconds = 8.0`.

---

## 2. Thiết kế các Module mới (New Core Modules)

### 2.1. Module timeline_effects
Đặt tại `backend/app/modules/timeline_effects/`:

- **[NEW] freeze_frame_builder.py**:
  Hàm `build_freeze_frame_clip(last_clip: TimelineClip, freeze_duration: float, strategy_name: str) -> TimelineClip` trích xuất 0.05s cuối của clip gốc, co giãn nó thành `freeze_duration` bằng cách giảm tốc độ (`speed = 0.05 / freeze_duration`), và gắn nhãn `freeze_frame=True` cùng `slow_zoom` thích hợp.

- **[NEW] motion_effects.py**:
  Hàm `apply_motion_effects(filtergraph: str, clip: TimelineClip, fps: int, target_width: int, target_height: int) -> str`
  Nếu `clip.slow_zoom` là `True`, hàm này sẽ chèn thêm bộ lọc `zoompan` vào chuỗi filter FFMPEG:
  ```txt
  zoompan=z='1.0+0.05*(on/(duration*fps))':x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':fps=fps:s=widthxheight
  ```

### 2.2. Module timeline_balancer
Đặt tại `backend/app/modules/timeline_balancer/`:

- **[NEW] duration_analyzer.py**:
  Hàm `analyze(voice_duration: float, video_duration: float) -> DurationAnalysis` trả về delta thời gian và xác định bên nào dài hơn (ngưỡng lệch > 0.5s).

- **[NEW] sync_strategy.py**:
  Enum `SyncStrategy`: `trim_voice`, `extend_video`, `freeze_frame`, `slow_zoom`, `ambient_ending`, `cta_ending`, `keep_original`.

- **[NEW] timeline_balancer.py**:
  Thuật toán cân bằng dòng thời gian `balance(...)` thực hiện:
  - Nếu độ lệch `< 0.5s` hoặc tự động cân bằng tắt: Không thay đổi timeline.
  - **Trường hợp A (Voice > Video)**:
    - Nếu độ lệch vượt quá `max_auto_extension_seconds`: Dùng chiến lược `trim_voice` (hệ thống sẽ cắt thoại khi render).
    - Ngược lại, thử chiến lược **Extend Scene** trước (đọc thêm frame chưa dùng từ video gốc của clip cuối).
    - Nếu vẫn chưa đủ thời gian, tạo thêm clip **Freeze Frame** hoặc **Slow Zoom** ở cuối timeline.
  - **Trường hợp B (Video > Voice)**:
    - **Không cắt ngắn timeline**. Giữ nguyên 100% video gốc.
    - Đặt chiến lược là `ambient_ending` (hoặc `cta_ending` nếu cảnh cuối là CTA). Phụ đề và giọng đọc kết thúc tự nhiên, nhạc nền tiếp tục chạy và fade-out dần ở giây cuối.

---

## 3. Điều chỉnh Render Pipeline & QA

### 3.1. Đảo thứ tự render trong `output_pipeline.py`
Luồng cũ: `Render Visual` -> `Generate Voice` -> `Merge Final`.
Luồng mới:
1. `Generate Script` và `Generate Voice` (truyền `target_duration = 0.0` cho `VoiceGenerator` để xuất audio untrimmed đầy đủ).
2. Chuẩn hoá âm thanh (`normalize_voice`) để nhận thời lượng âm thanh chính xác (`voice_duration`).
3. Chạy `TimelineBalancer.balance` để nhận dòng thời gian mới (`active_timeline`).
4. `Render Visual` (dựa trên `active_timeline` đã được cân bằng).
5. Tạo phụ đề (`generate_subtitle`) khớp với độ dài video mới.
6. Kết hợp overlay, audio, video thô (`render_final`).

### 3.2. Báo cáo & QA Checker
- **Render Report:** Bổ sung các thông số chi tiết của quá trình cân bằng dòng thời gian vào JSON kết quả render.
- **QA Checker:** Bổ sung kiểm thử `voice_cut_detected` cảnh báo nếu giọng thoại dài hơn video thực tế.

---

## 4. Giao diện Người dùng (Frontend UI)

1. **Render Settings:**
   Trong trang [RenderSettingsPage.tsx](file:///d:/Projects/Auto-Tool/frontend/src/pages/RenderSettingsPage.tsx):
   - Bổ sung checkbox `☑ Auto Balance Timeline` và input nhập `max_auto_extension_seconds`.
   - Tooltip: "Tự động kéo dài hoặc cân bằng timeline để tránh cắt mất câu thoại cuối."

2. **Preview Panel:**
   Trong `PreviewSection`, hiển thị rõ ba thông số trạng thái:
   - **Voice Duration:** 22.4s
   - **Timeline Duration:** 18.1s
   - **Adjustment:** +4.3s (Freeze Frame / Slow Zoom / Extend Scene) hoặc giữ nguyên (Ambient Ending).

---

## 5. Kế hoạch Kiểm thử (Verification Plan)

### 5.1. Unit Tests
Tạo các tệp kiểm thử chuyên biệt tại `backend/tests/`:
- `test_duration_analyzer.py`: Kiểm thử so sánh thời lượng.
- `test_timeline_balancer.py`: Kiểm thử phân phối clip cho các chiến lược cân bằng (Case A, B, C).
- `test_sync_strategy.py`: Kiểm thử tính hợp lệ của enum.

### 5.2. Chạy Kiểm chứng mô phỏng thực tế (AULA F99 Validation)
Sau khi hoàn thành code, chúng tôi sẽ chạy lại lệnh mô phỏng dự án bàn phím cơ để đảm bảo:
- Hệ thống render hoàn tất thành công.
- Không còn lỗi cắt thoại cuối.
- QA Checker chấm PASS cho toàn bộ quy trình.
