Add-Type -AssemblyName System.IO.Compression.FileSystem

$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$projectRoot = Split-Path -Parent $PSScriptRoot
$distDir = Join-Path $projectRoot "dist"
$latestZip = Get-ChildItem -Path $distDir -Filter "pdca-skill-v1.0.3-*.zip" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
$zipPath = $latestZip.FullName
if (-not (Test-Path $zipPath)) {
    Write-Host "ZIP NOT FOUND: $zipPath"
    exit 1
}

$zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
$entries = $zip.Entries

Write-Host "=== zip overview ==="
Write-Host ("file: " + $latestZip.Name)
Write-Host ("file count: " + $entries.Count)
$size = (Get-Item $zipPath).Length
Write-Host ("size: " + $size + " bytes = " + [math]::Round($size/1MB, 3) + " MB")

Write-Host ""
Write-Host "=== 3 skeleton whitelist ==="
$needed = @("memory/memory_main.md", "docs_rj/SUMMARY_RJ.md", "docs_rj/spec_rj/spec_main_rj.md")
foreach ($f in $needed) {
    $hit = $entries | Where-Object { $_.FullName -eq $f }
    if ($hit) { Write-Host ("OK: " + $f) } else { Write-Host ("MISS: " + $f) }
}

Write-Host ""
Write-Host "=== root SKILL.md ==="
$rootSkill = $entries | Where-Object { $_.FullName -eq "SKILL.md" }
if ($rootSkill) { Write-Host "OK" } else { Write-Host "FAIL" }

Write-Host ""
Write-Host "=== binary file scan (no .png/.jpg/.exe/.zip allowed) ==="
$binary = $entries | Where-Object { $_.FullName -match "\.(png|jpg|jpeg|gif|exe|zip|pdf)$" }
if ($binary) {
    $binary | ForEach-Object { Write-Host ("FOUND: " + $_.FullName + "  size=" + $_.Length + " bytes") }
} else {
    Write-Host "OK: no forbidden extension"
}

Write-Host ""
Write-Host "=== SKILL.md version field ==="
$skillEntry = $entries | Where-Object { $_.FullName -eq "SKILL.md" }
if ($skillEntry) {
    $reader = New-Object System.IO.StreamReader($skillEntry.Open())
    $skillContent = $reader.ReadToEnd()
    $reader.Close()
    $versionMatch = [regex]::Match($skillContent, 'version:\s*"?v?(\d+\.\d+\.\d+)"?')
    if ($versionMatch.Success) {
        Write-Host ("version: " + $versionMatch.Groups[1].Value)
    } else {
        Write-Host "version field not found"
    }
} else {
    Write-Host "SKILL.md not found, skip version check"
}

$zip.Dispose()
Write-Host ""
Write-Host "=== END ==="
