# Folders to KEEP (user specified - DO NOT DELETE)
$keepFolders = @(
    "D:\kk]",
    "C:\Users\siva\Downloads\klosud frs",
    "C:\Users\siva\Desktop\klosud frs",
    "D:\sivaproject\4.0",
    "C:\Users\siva\Downloads\AttendanceSystem"
)

Write-Host "============================================================"
Write-Host "  FOLDERS TO DELETE (everything NOT in keep list)"
Write-Host "============================================================"
Write-Host ""
Write-Host "KEPT (safe, will NOT be touched):"
foreach ($k in $keepFolders) { Write-Host "  KEEP: $k" }
Write-Host ""

$totalDelete = 0

# ── D:\ root folders ──────────────────────────────────────────
Write-Host "--- D:\ root folders ---"
Get-ChildItem "D:\" -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $full = $_.FullName
    $isKeep = $false
    foreach ($k in $keepFolders) {
        if ($full -eq $k -or $full.StartsWith($k)) { $isKeep = $true; break }
    }
    if (-not $isKeep) {
        $size = (Get-ChildItem $full -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        $mb = [math]::Round($size/1MB,1)
        $totalDelete += $size
        Write-Host "  DELETE  $($full.PadRight(45))  $mb MB"
    } else {
        Write-Host "  KEEP    $full"
    }
}

# ── D:\ root FILES (loose files) ─────────────────────────────
Write-Host ""
Write-Host "--- D:\ loose files ---"
Get-ChildItem "D:\" -File -ErrorAction SilentlyContinue | ForEach-Object {
    $mb = [math]::Round($_.Length/1MB,1)
    $totalDelete += $_.Length
    Write-Host "  DELETE  $($_.FullName.PadRight(45))  $mb MB"
}

# ── C:\Users\siva\Downloads folders ──────────────────────────
Write-Host ""
Write-Host "--- C:\Users\siva\Downloads folders ---"
Get-ChildItem "C:\Users\siva\Downloads" -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $full = $_.FullName
    $isKeep = $false
    foreach ($k in $keepFolders) {
        if ($full -eq $k -or $full.StartsWith($k)) { $isKeep = $true; break }
    }
    if (-not $isKeep) {
        $size = (Get-ChildItem $full -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        $mb = [math]::Round($size/1MB,1)
        $totalDelete += $size
        Write-Host "  DELETE  $($full.PadRight(60))  $mb MB"
    } else {
        Write-Host "  KEEP    $full"
    }
}

# ── C:\Users\siva\Downloads loose files ──────────────────────
Write-Host ""
Write-Host "--- C:\Users\siva\Downloads loose files (>5MB) ---"
Get-ChildItem "C:\Users\siva\Downloads" -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Length -gt 5MB } |
    Sort-Object Length -Descending |
    ForEach-Object {
        $mb = [math]::Round($_.Length/1MB,1)
        $totalDelete += $_.Length
        Write-Host "  DELETE  $($_.Name.PadRight(60))  $mb MB"
    }

# ── C:\Users\siva\Desktop folders ────────────────────────────
Write-Host ""
Write-Host "--- C:\Users\siva\Desktop folders ---"
Get-ChildItem "C:\Users\siva\Desktop" -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $full = $_.FullName
    $isKeep = $false
    foreach ($k in $keepFolders) {
        if ($full -eq $k -or $full.StartsWith($k)) { $isKeep = $true; break }
    }
    if (-not $isKeep) {
        $size = (Get-ChildItem $full -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        $mb = [math]::Round($size/1MB,1)
        $totalDelete += $size
        Write-Host "  DELETE  $($full.PadRight(60))  $mb MB"
    } else {
        Write-Host "  KEEP    $full"
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host "  TOTAL SPACE TO FREE: $([math]::Round($totalDelete/1GB,2)) GB"
Write-Host "============================================================"
