# Full UI Integration QA Checklist

Prompt 51 scope: full UI integration QA, bugfix pass, UX consistency pass and frontend stability pass.

## Navigation

- [x] Sidebar active đúng
- [x] Top bar đúng page
- [x] Breadcrumb đúng
- [x] Route reload không crash
- [x] Back/forward không phát hiện lỗi route trong QA browser

## Dashboard

- [x] Workflow cards hoạt động
- [x] First Run Checklist ổn
- [x] System status ổn
- [x] Recent projects fallback không crash
- [x] Recent outputs fallback không crash

## Start Workflow

- [x] Douyin Reup start flow load được
- [x] Douyin Reup scan folder mẫu thành công
- [x] Silent Mode start flow load được
- [x] Preset cards hoạt động
- [x] Checklist start hoạt động
- [x] Advanced settings mặc định đóng
- [x] Fast Auto confirm modal hoạt động
- [ ] Start job thật

## Subtitle Review

- [x] Document list hoạt động hoặc empty state hiển thị
- [x] Editor route không crash khi reload route list
- [ ] Save/Approve/Render subtitle document
- [ ] Rewrite panel với document thật

## Results

- [x] Gallery route load được
- [x] Missing job có empty/error state thân thiện
- [x] Technical log mặc định ẩn
- [ ] Filter/search với job có nhiều output
- [ ] Preview modal với video rendered thật
- [ ] QA panel với job thật
- [ ] Retry action với output lỗi thật

## Export

- [x] Empty state khi chưa có video
- [x] Export Pack UI không dùng copy auto posting
- [ ] Create export pack với video rendered thật
- [ ] Copy path với browser clipboard thật

## Settings / Help

- [x] Settings load được
- [x] System status load được
- [x] Help page mở được
- [x] Onboarding skip/modal mở được
- [x] Setup help modal đóng bằng Esc
- [x] Appearance settings áp dụng được

## Error / Offline

- [x] Backend status connected/offline UI không crash
- [x] Missing dependency hiển thị theo ready/missing/optional/unknown
- [x] Results missing job không hiện raw JSON

## Responsive

- [x] 1920x1080
- [x] 1440x900
- [x] 1366x768
- [x] 1280x720
- [x] 1024x768
- [x] 768x1024

## Build

- [x] npm run build pass
- [ ] npm run lint pass nếu có

Notes:
- Browser QA đã chạy trên `/`, `/dashboard`, `/douyin-reup`, `/silent-mode`, `/subtitle-review`, `/results`, `/results/demo-missing-job`, `/settings`, `/help`, `/onboarding`.
- Không bấm `Tiếp tục` để start job thật, không approve/render subtitle thật, không tạo export pack thật để tránh chạy pipeline hoặc tạo output ngoài ý muốn trong pass UI QA.
- Browser runtime trong Codex không cho nhập text bằng Playwright/CUA do thiếu virtual clipboard; các input path đã được test bằng route/state và thao tác recent folder `Use`.
