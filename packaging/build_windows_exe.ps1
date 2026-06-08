param(
  [string]$Name = "AutoTool"
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Dist = Join-Path $Frontend "dist"

Push-Location $Frontend
try {
  npm install
  npm run build
}
finally {
  Pop-Location
}

Push-Location $Backend
try {
  py -m pip install -r requirements.txt
  py -m pip install -r requirements-build.txt
  py -m PyInstaller `
    --noconfirm `
    --clean `
    --name $Name `
    --onefile `
    --add-data "$Dist;frontend/dist" `
    --paths "$Backend" `
    --collect-submodules edge_tts `
    --hidden-import gtts `
    --hidden-import gtts.tts `
    app/launcher.py

  $DistRoot = Join-Path $Backend "dist"
  $DistExamples = Join-Path $DistRoot "examples"
  New-Item -ItemType Directory -Force -Path $DistExamples | Out-Null
  foreach ($DirName in @("music", "overlay", "sample_videos", "outputs")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $DistExamples $DirName) | Out-Null
  }
  foreach ($DirName in @("music", "overlay", "sample_videos")) {
    $SourceDir = Join-Path $Root "examples\$DirName"
    $TargetDir = Join-Path $DistExamples $DirName
    if (Test-Path $SourceDir) {
      Copy-Item -Path (Join-Path $SourceDir "*") -Destination $TargetDir -Recurse -Force
    }
  }
  $ExampleConfig = Join-Path $Root "examples\product_config.example.json"
  if (Test-Path $ExampleConfig) {
    Copy-Item -Path $ExampleConfig -Destination $DistExamples -Force
  }
}
finally {
  Pop-Location
}

Write-Host "Built exe: $Backend\dist\$Name.exe"
