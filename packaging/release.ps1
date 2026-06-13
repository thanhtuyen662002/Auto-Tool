param(
  [Parameter(Mandatory=$true)]
  [string]$Version,
  [switch]$SkipBuild,
  [switch]$SkipUpload
)

$ErrorActionPreference = "Stop"

# Chuyển về thư mục root của dự án
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

# Validate version format (e.g. 1.0.0 or 1.0.0-rc1)
if ($Version -notmatch '^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$') {
  Write-Error "Phiên bản '$Version' không hợp lệ. Vui lòng nhập định dạng SemVer (ví dụ: 1.0.0 hoặc 1.0.0-rc1)."
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Magenta
Write-Host "   BẮT ĐẦU QUY TRÌNH PHÁT HÀNH PHIÊN BẢN v$Version" -ForegroundColor Magenta
Write-Host "==================================================" -ForegroundColor Magenta
Write-Host ""

# ─── 1. Kiểm tra trạng thái Git ───────────────────────────────────────────────
Write-Host "=== [1/6] Kiểm tra trạng thái Git ===" -ForegroundColor Cyan
$GitStatus = git status --porcelain
if ($GitStatus) {
  Write-Host "Cảnh báo: Bạn đang có những thay đổi chưa commit trong repo:" -ForegroundColor Yellow
  Write-Host $GitStatus -ForegroundColor DarkYellow
  $Confirm = Read-Host "Bạn vẫn muốn tiếp tục phát hành phiên bản mới? (y/N)"
  if ($Confirm -ne "y" -and $Confirm -ne "Y") {
    Write-Host "Đã hủy quy trình phát hành." -ForegroundColor Red
    exit 0
  }
}

# ─── 2. Cập nhật file VERSION ────────────────────────────────────────────────
Write-Host ""
Write-Host "=== [2/6] Cập nhật phiên bản trong file VERSION ===" -ForegroundColor Cyan
$VersionFile = Join-Path $Root "VERSION"
$Version | Out-File -FilePath $VersionFile -Encoding utf8 -NoNewline
Write-Host "Đã cập nhật file VERSION thành: $Version" -ForegroundColor Green

# ─── 3. Build EXE ứng dụng ───────────────────────────────────────────────────
Write-Host ""
Write-Host "=== [3/6] Build ứng dụng Windows EXE ===" -ForegroundColor Cyan
if ($SkipBuild) {
  Write-Host "[Bỏ qua] Không build EXE theo tham số -SkipBuild." -ForegroundColor Yellow
} else {
  $BuildScript = Join-Path $Root "packaging\build_windows_exe.ps1"
  if (-not (Test-Path $BuildScript)) {
    Write-Error "Không tìm thấy script build tại: $BuildScript"
  }
  Write-Host "Đang chạy build_windows_exe.ps1..." -ForegroundColor Yellow
  & $BuildScript
  Write-Host "Build EXE thành công!" -ForegroundColor Green
}

# ─── 4. Nén thư mục dist thành file ZIP ───────────────────────────────────────
Write-Host ""
Write-Host "=== [4/6] Tạo file nén ứng dụng ZIP ===" -ForegroundColor Cyan
$BackendDist = Join-Path $Root "backend\dist"
$SourceFolder = Join-Path $BackendDist "AutoTool"
$ZipName = "AutoTool-v$Version-windows.zip"
$ZipPath = Join-Path $BackendDist $ZipName

if (-not $SkipBuild) {
  if (-not (Test-Path $SourceFolder)) {
    Write-Error "Không tìm thấy thư mục build tại: $SourceFolder"
  }
  Write-Host "Đang nén $SourceFolder thành $ZipPath ..." -ForegroundColor Yellow
  if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
  }
  # Nén folder AutoTool
  Compress-Archive -Path $SourceFolder -DestinationPath $ZipPath
  Write-Host "Đã tạo file nén: $ZipName" -ForegroundColor Green
} else {
  Write-Host "[Bỏ qua] Không có bản build mới để nén do -SkipBuild." -ForegroundColor Yellow
}

# ─── 5. Commit và Push Git ────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== [5/6] Cập nhật Git Repository ===" -ForegroundColor Cyan
try {
  git add VERSION
  git commit -m "chore: bump version to v$Version"
  
  # Tạo tag
  $TagName = "v$Version"
  # Xóa tag local nếu đã tồn tại để tránh lỗi trùng lặp
  git tag -d $TagName 2>$null
  git tag $TagName
  
  # Push lên remote
  Write-Host "Đang push code và tag lên GitHub..." -ForegroundColor Yellow
  git push origin main
  git push origin $TagName
  Write-Host "Push Git thành công!" -ForegroundColor Green
} catch {
  Write-Host "Lỗi khi tương tác với Git: $_" -ForegroundColor Red
  Write-Host "Vui lòng tự thực hiện commit, tag và push thủ công." -ForegroundColor Yellow
}

# ─── 6. Upload lên GitHub Releases ────────────────────────────────────────────
Write-Host ""
Write-Host "=== [6/6] Tạo Release và tải lên file ZIP ===" -ForegroundColor Cyan
if ($SkipUpload) {
  Write-Host "[Bỏ qua] Bỏ qua upload theo tham số -SkipUpload." -ForegroundColor Yellow
} elseif (-not (Test-Path $ZipPath)) {
  Write-Host "Không tìm thấy file ZIP tại: $ZipPath. Không thể tự động upload." -ForegroundColor Yellow
} else {
  $TagName = "v$Version"
  if (Get-Command gh -ErrorAction SilentlyContinue) {
    Write-Host "Phát hiện GitHub CLI (gh). Đang tạo Release và upload ZIP..." -ForegroundColor Yellow
    try {
      # Đợi 2 giây cho git đồng bộ tag
      Start-Sleep -Seconds 2
      # Tạo release bằng gh CLI
      gh release create $TagName $ZipPath --title "Auto Tool v$Version" --notes "Release v$Version"
      Write-Host "Đã tạo Release và upload file ZIP thành công lên GitHub!" -ForegroundColor Green
    } catch {
      Write-Host "Lỗi khi upload bằng GitHub CLI: $_" -ForegroundColor Red
      Write-Host "Vui lòng upload thủ công file ZIP tại: $ZipPath lên Release trên GitHub." -ForegroundColor Yellow
    }
  } else {
    Write-Host "Không tìm thấy GitHub CLI (gh) trên hệ thống." -ForegroundColor Yellow
    Write-Host "-> Bước tiếp theo dành cho bạn:" -ForegroundColor Yellow
    Write-Host "   1. Truy cập trang GitHub Releases của repo." -ForegroundColor Yellow
    Write-Host "   2. Bạn sẽ thấy một Release mới đã được tạo tự động bởi GitHub Actions khi nhận tag $TagName." -ForegroundColor Yellow
    Write-Host "   3. Hãy upload file ZIP sau lên Release đó:" -ForegroundColor Yellow
    Write-Host "      $ZipPath" -ForegroundColor Green
  }
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host "   QUY TRÌNH PHÁT HÀNH PHIÊN BẢN v$Version HOÀN TẤT!" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
