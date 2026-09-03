# DELETE old unused folders from D:\
# KEEPING: D:\kk]  D:\sivaproject\4.0

$toDelete = @(
    "D:\face-detection-dashboard",
    "D:\sw",
    "D:\swagatika",
    "D:\openclaw",
    "D:\fs 2.o",
    "D:\Face-Detection-cctv",
    "D:\frs best",
    "D:\3c",
    "D:\3c.o",
    "D:\proble soloving",
    "D:\zdot-attend",
    "D:\old",
    "D:\z.attend-backend",
    "D:\backup",
    "D:\StillName",
    "D:\hh",
    "D:\New folder",
    "D:\Seventeen",
    "D:\mian",
    "D:\attdacs pc"
)

# Delete sivaproject subfolders EXCEPT 4.0
$sivaSubs = Get-ChildItem "D:\sivaproject" -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne "4.0" }
foreach ($sub in $sivaSubs) {
    $toDelete += $sub.FullName
}
# Also delete loose files in sivaproject root
$sivaFiles = Get-ChildItem "D:\sivaproject" -File -ErrorAction SilentlyContinue
foreach ($file in $sivaFiles) {
    Write-Host "Deleting file: $($file.FullName)"
    Remove-Item $file.FullName -Force -ErrorAction SilentlyContinue
}

$totalFreed = 0

foreach ($path in $toDelete) {
    if (Test-Path $path) {
        $size = (Get-ChildItem $path -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        $mb   = [math]::Round($size/1MB, 1)
        Write-Host "Deleting: $path  ($mb MB) ..."
        Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
        if (-not (Test-Path $path)) {
            Write-Host "  DONE"
            $totalFreed += $size
        } else {
            Write-Host "  PARTIAL (some files may be in use)"
        }
    } else {
        Write-Host "SKIP (not found): $path"
    }
}

# Also delete D:\ loose files (not in any folder)
Write-Host ""
Write-Host "Deleting loose files on D:\ root..."
Get-ChildItem "D:\" -File -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "  Deleting: $($_.Name)"
    Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "========================================"
Write-Host "FREED: $([math]::Round($totalFreed/1GB, 2)) GB"
Write-Host ""
Write-Host "Remaining D:\ folders:"
Get-ChildItem "D:\" -Directory | Select-Object Name, LastWriteTime
Write-Host "========================================"
