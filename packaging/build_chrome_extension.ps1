param(
  [string]$Name = "auto-tool-shopee-extractor"
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Extension = Join-Path $Root "chrome-extension"
$Dist = Join-Path $Extension "dist"
$ZipPath = Join-Path $Extension "$Name.zip"

Push-Location $Extension
try {
  npm install
  npm test
  npm run build
}
finally {
  Pop-Location
}

$Manifest = Join-Path $Dist "manifest.json"
if (-not (Test-Path -LiteralPath $Manifest)) {
  throw "Extension build did not create manifest.json in $Dist"
}

Compress-Archive -Path (Join-Path $Dist "*") -DestinationPath $ZipPath -Force
Write-Host "Built Chrome extension: $ZipPath"
