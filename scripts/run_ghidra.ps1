[CmdletBinding()]
param(
    [ValidateSet('import', 'resume', 'xrefs', 'dispatch', 'resource-load', 'decode-evidence', 'equipment-evidence', 'vtable-evidence')]
    [string]$Action = 'import',
    [ValidateRange(60, 7200)]
    [int]$AnalysisTimeoutSeconds = 1200
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$jdkHome = Join-Path $env:LOCALAPPDATA 'Programs\JDK21\jdk-21.0.13+9'
$javaExe = Join-Path $jdkHome 'bin\java.exe'
$ghidraRoot = Join-Path $env:LOCALAPPDATA 'Programs\Ghidra_12.1.2\ghidra_12.1.2_PUBLIC'
$headless = Join-Path $ghidraRoot 'support\analyzeHeadless.bat'
$program = Join-Path $repoRoot 'data\extracted\lr_20261116T212608096_7b99bdd0\apk_contents\split_config.arm64_v8a\lib\arm64-v8a\libgame.so'
$projectDirectory = Join-Path $repoRoot 'data\research\ghidra'
$scriptDirectory = Join-Path $PSScriptRoot 'ghidra'
$reportDirectory = Join-Path $repoRoot 'reports\ghidra'
$projectName = 'LRNative'

foreach ($requiredPath in @($javaExe, $headless, $program, $scriptDirectory)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required Ghidra analysis path does not exist: $requiredPath"
    }
}

$projectFile = Join-Path $projectDirectory ($projectName + '.gpr')
if ($Action -eq 'import' -and (Test-Path -LiteralPath $projectFile)) {
    throw "Project already exists; use -Action resume to continue it: $projectFile"
}
if ($Action -in @('resume', 'xrefs', 'dispatch', 'resource-load', 'decode-evidence', 'equipment-evidence', 'vtable-evidence') -and -not (Test-Path -LiteralPath $projectFile)) {
    throw "Cannot resume because the Ghidra project does not exist: $projectFile"
}

New-Item -ItemType Directory -Path $projectDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null

$env:JAVA_HOME = $jdkHome
$env:Path = (Join-Path $jdkHome 'bin') + ';' + $env:Path

$timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$runLog = Join-Path $reportDirectory ("ghidra_" + $timestamp + '.log')
$xrefReport = Join-Path $reportDirectory ("libgame_resource_xrefs_" + $timestamp + '.txt')
$dispatchReport = Join-Path $reportDirectory ("libgame_fileutils_dispatch_" + $timestamp + '.txt')
$resourceLoadReport = Join-Path $reportDirectory ("libgame_resource_load_" + $timestamp + '.txt')
$decodeEvidenceReport = Join-Path $reportDirectory 'decode-evidence.txt'
$resourceLoadSourceReport = Join-Path $reportDirectory 'libgame_resource_load_20261117T131208Z.txt'
$equipEvidenceReport = Join-Path $reportDirectory 'equip-table-evidence.txt'
$equipSourceReport = Join-Path $reportDirectory 'libgame_resource_xrefs_20261117T122825Z.txt'
$javaVersionLog = Join-Path $reportDirectory ("java_version_" + $timestamp + '.txt')

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$javaVersionOutput = & $env:ComSpec /d /c ('"{0}" -version 2>&1' -f $javaExe)
$javaExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference
$javaVersionOutput | Out-File -LiteralPath $javaVersionLog -Encoding utf8
if ($javaExitCode -ne 0) {
    throw "The project-specific JDK failed to start. See $javaVersionLog"
}
if (($javaVersionOutput -join ' ') -notmatch 'version "21\.') {
    throw "Ghidra 12.1.2 requires the verified JDK 21, but the selected Java is not version 21. See $javaVersionLog"
}

$arguments = @($projectDirectory, $projectName)
$scriptName = 'ExportResourceStringXrefs.java'
$scriptReport = $xrefReport
if ($Action -eq 'import') {
    $arguments += @('-import', $program)
}
else {
    $arguments += @('-process', 'libgame.so')
}
if ($Action -notin @('xrefs', 'dispatch', 'resource-load', 'decode-evidence', 'equipment-evidence', 'vtable-evidence')) {
    $arguments += @('-analysisTimeoutPerFile', $AnalysisTimeoutSeconds.ToString())
}
else {
    $arguments += '-noanalysis'
}
if ($Action -eq 'dispatch') {
    $scriptName = 'InspectFileUtilsDispatch.java'
    $scriptReport = $dispatchReport
}
if ($Action -eq 'resource-load') {
    $scriptName = 'TraceResourceLoad.java'
    $scriptReport = $resourceLoadReport
}
if ($Action -eq 'decode-evidence') {
    if (-not (Test-Path -LiteralPath $resourceLoadSourceReport)) {
        throw "Existing caller evidence report is missing: $resourceLoadSourceReport"
    }
    $scriptName = 'ExportDecodeEvidence.java'
    $scriptReport = $decodeEvidenceReport
}
if ($Action -eq 'equipment-evidence') {
    if (-not (Test-Path -LiteralPath $equipSourceReport)) {
        throw "Existing descriptor evidence report is missing: $equipSourceReport"
    }
    $scriptName = 'ExportEquipTableEvidence.java'
    $scriptReport = $equipEvidenceReport
}
if ($Action -eq 'vtable-evidence') {
    if (-not (Test-Path -LiteralPath $equipSourceReport)) {
        throw "Existing descriptor evidence report is missing: $equipSourceReport"
    }
    $scriptName = 'InspectEquipVtableEvidence.java'
    $scriptReport = Join-Path $reportDirectory 'equip-vtable-address-point.txt'
}
$postScriptArguments = @($scriptReport)
if ($Action -eq 'decode-evidence') {
    $postScriptArguments += $resourceLoadSourceReport
}
if ($Action -eq 'equipment-evidence') {
    $postScriptArguments += $equipSourceReport
}
if ($Action -eq 'vtable-evidence') {
    $postScriptArguments += $equipSourceReport
}
$arguments += @(
    '-scriptPath', $scriptDirectory,
    '-postScript', $scriptName
) + $postScriptArguments

$analysisTimeoutDescription = "$AnalysisTimeoutSeconds seconds"
if ($Action -in @('xrefs', 'dispatch', 'resource-load', 'decode-evidence', 'equipment-evidence', 'vtable-evidence')) {
    $analysisTimeoutDescription = 'disabled; reuse saved analysis'
}

@(
    "UTC start: $timestamp"
    "Action: $Action"
    "Ghidra: 12.1.2"
    "Java home: $jdkHome"
    "Java version output: $($javaVersionOutput -join ' ')"
    "Input: $program"
    "Project: $projectFile"
    "Analysis timeout: $analysisTimeoutDescription"
    "Command: $headless $($arguments -join ' ')"
) | Out-File -LiteralPath $runLog -Encoding utf8

$ErrorActionPreference = 'Continue'
& $headless @arguments *>> $runLog
$ghidraExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference

if (Select-String -LiteralPath $runLog -Pattern 'Analysis timed out' -Quiet) {
    Write-Warning "Ghidra reached the configured analysis timeout. The project is retained for -Action resume. Log: $runLog"
}

Write-Output "Ghidra exit code: $ghidraExitCode"
Write-Output "Ghidra log: $runLog"
if ($ghidraExitCode -ne 0) {
    throw "Ghidra returned exit code $ghidraExitCode. The project is retained at $projectFile"
}
if (-not (Test-Path -LiteralPath $scriptReport)) {
    throw "Ghidra exited successfully but did not create the expected report: $scriptReport"
}
if (-not (Select-String -LiteralPath $scriptReport -Pattern '^REPORT_COMPLETE$' -Quiet)) {
    throw "The report is incomplete. See $runLog and $scriptReport"
}
Write-Output "Ghidra report: $scriptReport"
