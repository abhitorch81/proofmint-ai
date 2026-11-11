param(
  [Parameter(Mandatory=$true)][string]$SourceDir,
  [string]$TargetDir = (Join-Path (Join-Path $PSScriptRoot '..') 'backend\momentweave_exports')
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $SourceDir -PathType Container)) { throw "Source directory not found: $SourceDir" }
New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
Get-ChildItem -LiteralPath $SourceDir -Filter '*.json' -File | ForEach-Object {
  $dest = Join-Path $TargetDir $_.Name
  if (Test-Path -LiteralPath $dest) { Write-Warning "Skipping existing $dest" }
  else { Copy-Item -LiteralPath $_.FullName -Destination $dest; Write-Host "Copied $($_.Name)" }
}
Write-Host "MomentWeave JSON export migration complete. Database and receipts unchanged."
