# Auto Tool Manual QA Report

**Phiên bản:** Auto Tool v0.1.0-rc1  
**Ngày kiểm tra:** _______________

---

## Environment

| Mục | Giá trị |
|-----|---------|
| OS | |
| Python version | |
| Node version | |
| FFmpeg version | |
| Ngày kiểm tra | |
| Người kiểm tra | |

---

## Test Project

| Mục | Giá trị |
|-----|---------|
| Tên sản phẩm | |
| Số video đầu vào | |
| Số video đầu ra (output_count) | |
| Độ dài video (giây) | |
| Phong cách video (template) | |
| Mức độ chỉnh sửa | |
| Nhà cung cấp TTS | |
| Giọng đọc | |
| Config file | |

---

## Kết quả Render

| Mục | Giá trị |
|-----|---------|
| Preview render thành công | Có / Không |
| Full batch render thành công | Có / Không |
| Tổng số video thành công | / |
| Tổng số video thất bại | |
| Thời gian render trung bình (giây) | |
| Điểm chất lượng trung bình (%) | |
| Thư mục đầu ra | |

---

## Kiểm tra Smoke Test

```bash
cd backend
py -m app.tools.smoke_test --config ../examples/qa_projects/projector_config.json
```

| Bước | Kết quả |
|------|---------|
| load_config | ok / fail |
| check_env | ok / fail |
| scan | ok / skip / fail |
| segment | ok / fail |
| segment_scoring | ok / fail |
| timeline | ok / fail |
| script | ok / fail |
| tts | ok / skip / fail |
| subtitle | ok / fail |
| render_preview | ok / skip / fail |
| qa | ok / skip / fail |

**Tổng kết:** Pass / Fail

---

## Kiểm tra Automated Tests

```bash
cd backend
py -m pytest -v
```

| Mục | Giá trị |
|-----|---------|
| Tổng số test | |
| Passed | |
| Failed | |
| Skipped | |

---

## Kiểm tra Frontend Build

```bash
cd frontend
npm run build
```

- [ ] Build thành công (exit code 0)
- [ ] Không có TypeScript error
- [ ] Bundle size hợp lý (< 5MB)

---

## Lỗi và Vấn đề Phát hiện

| # | Lỗi / Vấn đề | Mức độ | Bước tái hiện | Kết quả mong đợi | Kết quả thực tế | Ghi chú |
|---|--------------|--------|---------------|-----------------|-----------------|---------|
| 1 | | Critical / High / Medium / Low | | | | |
| 2 | | | | | | |
| 3 | | | | | | |

**Mức độ ưu tiên:**
- **Critical** — Không render được, data mất
- **High** — Tính năng cốt lõi bị hỏng
- **Medium** — Tính năng phụ bị hỏng hoặc UX xấu
- **Low** — Cosmetic, typo, cải thiện nhỏ

---

## Performance Metrics (từ project_summary.json)

| Mục | Giá trị |
|-----|---------|
| Tổng thời gian render (giây) | |
| Thời gian trung bình/video (giây) | |
| Bước chậm nhất | |
| Video chậm nhất (index) | |

---

## Quyết định Cuối cùng

- [ ] **PASS** — Sẵn sàng phát hành
- [ ] **PASS WITH WARNINGS** — Có vấn đề nhỏ, có thể phát hành
- [ ] **FAIL** — Cần sửa trước khi phát hành

**Lý do / Ghi chú:**

_______________________________________________
_______________________________________________
_______________________________________________

---

*Report này được tạo theo template `docs/MANUAL_QA_REPORT_TEMPLATE.md`*
