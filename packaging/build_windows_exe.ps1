param(
  [string]$Name = "AutoTool"
)

$ErrorActionPreference = "Stop"

$Root     = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Backend  = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Dist     = Join-Path $Frontend "dist"
$Vendor   = Join-Path $Backend "vendor"

function Test-NodeVersionSupported($VersionText) {
  $clean = ($VersionText -replace '^v', '').Trim()
  $parts = $clean.Split('.')
  if ($parts.Count -lt 2) { return $false }
  $major = [int]$parts[0]
  $minor = [int]$parts[1]
  if ($major -gt 22) { return $true }
  if ($major -eq 22 -and $minor -ge 12) { return $true }
  if ($major -eq 20 -and $minor -ge 19) { return $true }
  return $false
}

function Assert-NodeVersionForFrontendBuild {
  $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
  if (-not $nodeCommand) {
    throw "Node.js is not installed or not available in PATH. Install Node.js 20.19+ or 22.12+ before building."
  }
  $nodeVersion = (& node -v).Trim()
  $npmVersion = (& npm -v).Trim()
  Write-Host "  Node.js: $nodeVersion ($($nodeCommand.Source))" -ForegroundColor DarkGray
  Write-Host "  npm    : $npmVersion" -ForegroundColor DarkGray
  if (-not (Test-NodeVersionSupported $nodeVersion)) {
    throw "Node.js $nodeVersion is too old for Vite 7. Use Node.js 20.19+ or 22.12+."
  }
}

function Invoke-BuildPython {
  $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
  if (-not $pythonCommand) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
  }
  if (-not $pythonCommand) {
    throw "Python is not installed or not available in PATH."
  }
  & $pythonCommand.Source @args
}

# â”€â”€â”€ Helper: download with progress â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function Download-File($Url, $OutFile, $Label) {
  if (Test-Path $OutFile) {
    Write-Host "  [skip] $Label already downloaded." -ForegroundColor DarkGray
    return
  }
  Write-Host "  Downloading $Label ..." -ForegroundColor Yellow
  $tmp = "$OutFile.download"
  Remove-Item $tmp -ErrorAction SilentlyContinue
  try {
    Invoke-WebRequest -Uri $Url -OutFile $tmp -UseBasicParsing
    Move-Item $tmp $OutFile
    Write-Host "  [ok] $Label" -ForegroundColor Green
  } catch {
    Remove-Item $tmp -ErrorAction SilentlyContinue
    throw "Failed to download $Label`: $_"
  }
}

# â”€â”€â”€ 1. Build frontend â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Write-Host ""
Write-Host "=== [1/4] Building frontend ===" -ForegroundColor Cyan
Push-Location $Frontend
try {
  Assert-NodeVersionForFrontendBuild
  npm install
  npm run build
} finally {
  Pop-Location
}

# â”€â”€â”€ 2. Download & prepare vendor tools â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Write-Host ""
Write-Host "=== [2/4] Preparing vendor tools (FFmpeg, Piper, voice model) ===" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $Vendor | Out-Null

# â”€â”€ FFmpeg â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
$FfmpegVendor = Join-Path $Vendor "ffmpeg"
$FfmpegBin    = Join-Path $FfmpegVendor "bin"
$FfmpegExe    = Join-Path $FfmpegBin "ffmpeg.exe"
$FfprobeExe   = Join-Path $FfmpegBin "ffprobe.exe"

if (-not (Test-Path $FfmpegExe) -or -not (Test-Path $FfprobeExe)) {
  Write-Host "  Preparing FFmpeg..." -ForegroundColor Yellow
  New-Item -ItemType Directory -Force -Path $FfmpegBin | Out-Null
  $FfmpegZip     = Join-Path $Vendor "ffmpeg-release-essentials.zip"
  $FfmpegExtract = Join-Path $Vendor "ffmpeg-extract"

  Download-File `
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" `
    $FfmpegZip "FFmpeg release-essentials"

  if (Test-Path $FfmpegExtract) { Remove-Item $FfmpegExtract -Recurse -Force }
  Write-Host "  Extracting FFmpeg..." -ForegroundColor Yellow
  Expand-Archive -Path $FfmpegZip -DestinationPath $FfmpegExtract -Force

  $ExtFfmpeg  = Get-ChildItem -Path $FfmpegExtract -Recurse -Filter "ffmpeg.exe"  | Select-Object -First 1
  $ExtFfprobe = Get-ChildItem -Path $FfmpegExtract -Recurse -Filter "ffprobe.exe" | Select-Object -First 1
  if (-not $ExtFfmpeg)  { throw "ffmpeg.exe not found in downloaded archive." }
  if (-not $ExtFfprobe) { throw "ffprobe.exe not found in downloaded archive." }

  Copy-Item $ExtFfmpeg.FullName  -Destination $FfmpegExe  -Force
  Copy-Item $ExtFfprobe.FullName -Destination $FfprobeExe -Force
  Remove-Item $FfmpegExtract -Recurse -Force
  Remove-Item $FfmpegZip -Force
  Write-Host "  [ok] FFmpeg ready at vendor/ffmpeg/bin/" -ForegroundColor Green
} else {
  Write-Host "  [skip] FFmpeg already in vendor/ffmpeg/bin/" -ForegroundColor DarkGray
}

# â”€â”€ Piper TTS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
$PiperVendor = Join-Path $Vendor "piper"
$PiperExe    = Join-Path $PiperVendor "piper.exe"

if (-not (Test-Path $PiperExe)) {
  Write-Host "  Preparing Piper TTS..." -ForegroundColor Yellow
  New-Item -ItemType Directory -Force -Path $PiperVendor | Out-Null
  $PiperZip     = Join-Path $Vendor "piper_windows_amd64.zip"
  $PiperExtract = Join-Path $Vendor "piper-extract"

  Download-File `
    "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip" `
    $PiperZip "Piper TTS"

  if (Test-Path $PiperExtract) { Remove-Item $PiperExtract -Recurse -Force }
  Write-Host "  Extracting Piper..." -ForegroundColor Yellow
  Expand-Archive -Path $PiperZip -DestinationPath $PiperExtract -Force

  # Piper zip thÆ°á»ng cÃ³ thÆ° má»¥c con "piper/" hoáº·c files náº±m trá»±c tiáº¿p
  $InnerDir = Get-ChildItem -Path $PiperExtract -Directory | Select-Object -First 1
  $CopyFrom = if ($InnerDir) { $InnerDir.FullName } else { $PiperExtract }
  Copy-Item -Path (Join-Path $CopyFrom "*") -Destination $PiperVendor -Recurse -Force

  Remove-Item $PiperExtract -Recurse -Force
  Remove-Item $PiperZip -Force
  Write-Host "  [ok] Piper ready at vendor/piper/" -ForegroundColor Green
} else {
  Write-Host "  [skip] Piper already in vendor/piper/" -ForegroundColor DarkGray
}

# â”€â”€ Piper Vietnamese voice model â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
$PiperModels    = Join-Path $PiperVendor "models"
$PiperModelFile = Join-Path $PiperModels "vi_VN-vais1000-medium.onnx"
$PiperCfgFile   = Join-Path $PiperModels "vi_VN-vais1000-medium.onnx.json"
New-Item -ItemType Directory -Force -Path $PiperModels | Out-Null

Download-File `
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx" `
  $PiperModelFile "Piper Vietnamese model (vi_VN-vais1000-medium.onnx)"

Download-File `
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx.json" `
  $PiperCfgFile "Piper Vietnamese config (vi_VN-vais1000-medium.onnx.json)"

Write-Host "  [ok] Piper Vietnamese model ready at vendor/piper/models/" -ForegroundColor Green

# â”€â”€â”€ 3. Install Python deps & PyInstaller build â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Write-Host ""
Write-Host "=== [3/4] Installing Python dependencies & building EXE ===" -ForegroundColor Cyan
Push-Location $Backend
try {
  Invoke-BuildPython -m pip install -r requirements.txt
  Invoke-BuildPython -m pip install -r requirements-build.txt
  Invoke-BuildPython -m PyInstaller `
    --noconfirm `
    --clean `
    --name $Name `
    --onedir `
    --noconsole `
    --add-data "$Dist;frontend/dist" `
    --add-data "$FfmpegVendor;vendor/ffmpeg" `
    --add-data "$PiperVendor;vendor/piper" `
    --paths "$Backend" `
    --collect-submodules edge_tts `
    --collect-submodules faster_whisper `
    --collect-data faster_whisper `
    --collect-all ctranslate2 `
    --collect-all tokenizers `
    --collect-binaries onnxruntime `
    --collect-data onnxruntime `
    --collect-all av `
    --collect-all easyocr `
    --collect-all torch `
    --collect-all torchvision `
    --collect-all scipy `
    --collect-all skimage `
    --collect-all selenium `
    --collect-all webdriver_manager `
    --collect-all yt_dlp `
    --hidden-import requests `
    --hidden-import huggingface_hub `
    --hidden-import huggingface_hub.utils `
    --hidden-import onnxruntime `
    --hidden-import onnxruntime.capi.onnxruntime_pybind11_state `
    --hidden-import cv2 `
    --hidden-import gtts `
    --hidden-import gtts.tts `
    app/launcher.py

  # â”€â”€â”€ 4. Copy examples & config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  Write-Host ""
  Write-Host "=== [4/4] Copying examples and config ===" -ForegroundColor Cyan

  $DistRoot    = Join-Path (Join-Path $Backend "dist") $Name
  $DistExamples = Join-Path $DistRoot "examples"
  New-Item -ItemType Directory -Force -Path $DistExamples | Out-Null
  foreach ($DirName in @("music", "overlay", "sample_videos", "outputs")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $DistExamples $DirName) | Out-Null
  }
  foreach ($DirName in @("music", "overlay", "sample_videos")) {
    $Src = Join-Path $Root "examples\$DirName"
    $Dst = Join-Path $DistExamples $DirName
    if (Test-Path $Src) {
      Copy-Item -Path (Join-Path $Src "*") -Destination $Dst -Recurse -Force
    }
  }
  $ExampleConfig = Join-Path $Root "examples\product_config.example.json"
  if (Test-Path $ExampleConfig) {
    Copy-Item -Path $ExampleConfig -Destination $DistExamples -Force
  }

  $DistConfig   = Join-Path $DistRoot "config"
  $DistPkg      = Join-Path $DistRoot "packaging"
  New-Item -ItemType Directory -Force -Path $DistConfig | Out-Null
  New-Item -ItemType Directory -Force -Path $DistPkg    | Out-Null
  Copy-Item -Path (Join-Path $Root "VERSION") -Destination (Join-Path $DistRoot "VERSION") -Force
  Copy-Item -Path (Join-Path $Root "packaging\local_app_config.example.json") -Destination $DistPkg -Force
  Copy-Item -Path (Join-Path $Root "packaging\README_LOCAL_APP.md")           -Destination $DistPkg -Force
  if (-not (Test-Path (Join-Path $DistConfig "local_app_config.json"))) {
    Copy-Item -Path (Join-Path $Root "packaging\local_app_config.example.json") `
              -Destination (Join-Path $DistConfig "local_app_config.json") -Force
  }
} finally {
  Pop-Location
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Build complete!" -ForegroundColor Green
Write-Host "  Output folder : $Backend\dist\$Name\" -ForegroundColor Green
Write-Host "  Run           : $Backend\dist\$Name\$Name.exe" -ForegroundColor Green
Write-Host "  Bundled       : FFmpeg, Piper TTS, Piper Vietnamese model" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green

