# Windows Launcher QA Checklist

- [ ] Double-click launcher mở được app.
- [ ] Mỗi lần chạy tạo log trong `logs/launcher/`.
- [ ] Thiếu Python báo lỗi rõ và giữ cửa sổ mở.
- [ ] Thiếu Node nhưng frontend build có sẵn chỉ cảnh báo.
- [ ] Thiếu Node và frontend build thiếu thì báo lỗi.
- [ ] Thiếu FFmpeg chỉ cảnh báo, không block app.
- [ ] `.venv` tự tạo nếu thiếu.
- [ ] Backend requirements được cài thành công.
- [ ] `frontend/dist` thiếu thì tự build.
- [ ] Backend chỉ bind `127.0.0.1:8000`.
- [ ] Browser mở `http://127.0.0.1:8000`.
- [ ] Port 8000 bận bởi Auto Tool thì mở app hiện có.
- [ ] Port 8000 bận bởi app khác thì báo lỗi và không kill tiến trình.
- [ ] Debug launcher giữ console để đọc lỗi.
- [ ] Check System chỉ kiểm tra, không start app.
- [ ] Build Frontend chỉ build frontend.
- [ ] Reset cache backup recent paths và không xóa outputs/database/source videos.
- [ ] README Windows có hướng dẫn launcher, log và shortcut.
