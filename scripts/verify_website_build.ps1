# Reproducible local build in a dedicated directory; no deployment or source deletion.
param([string]$DistDir = '.next-local-validation')
$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($DistDir -notmatch '^\.next-local-[A-Za-z0-9-]+$') {
    throw 'Use a dedicated .next-local-* build directory.'
}
$target = [IO.Path]::GetFullPath((Join-Path $workspace $DistDir))
if (-not $target.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Build directory escaped the workspace.'
}
Push-Location $workspace
try {
    # OneDrive marks generated directories ReadOnly/ReparsePoint. Clear only
    # ReadOnly on this generated tree; retain every other attribute and file.
    if (Test-Path -LiteralPath $target) {
        $items = @((Get-Item -LiteralPath $target -Force)) + @(Get-ChildItem -LiteralPath $target -Recurse -Force)
        foreach ($item in $items) {
            if (-not $item.FullName.StartsWith($target, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected build path.' }
            if (($item.Attributes -band [IO.FileAttributes]::ReadOnly) -ne 0) {
                [IO.File]::SetAttributes($item.FullName, ($item.Attributes -band (-bnot [IO.FileAttributes]::ReadOnly)))
            }
        }
    }
    $env:LR_NEXT_DIST_DIR = $DistDir
    $ErrorActionPreference = 'Continue'
    & npm.cmd run build *> (Join-Path $workspace 'reports/build-local-validation.log')
    $code = $LASTEXITCODE
    @{exitCode=$code;finishedAt=(Get-Date -Format o);distDir=$DistDir} | ConvertTo-Json | Set-Content -Encoding UTF8 'reports/build-local-validation-status.json'
    Get-Content 'reports/build-local-validation.log' -Tail 35
    if ($code -ne 0) { exit $code }
} finally {
    Pop-Location
}
