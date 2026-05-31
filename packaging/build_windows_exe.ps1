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
}
finally {
  Pop-Location
}

Write-Host "Built exe: $Backend\dist\$Name.exe"
