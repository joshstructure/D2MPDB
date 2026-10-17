param([switch]$NoOpen)
$ErrorActionPreference = 'Stop'
$atlasRoot = $PSScriptRoot
$atlasPython = Join-Path $atlasRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $atlasPython)) { $atlasPython = 'python' }
Push-Location -LiteralPath $atlasRoot
try {
    & $atlasPython -m design_atlas.build
    if ($LASTEXITCODE -ne 0) { throw 'Atlas rebuild failed; the previous snapshot was not refreshed.' }
    $atlasIndex = Join-Path $atlasRoot 'design_atlas\dist\index.html'
    if (-not $NoOpen) { Invoke-Item -LiteralPath $atlasIndex }
    Write-Output $atlasIndex
} finally {
    Pop-Location
}
