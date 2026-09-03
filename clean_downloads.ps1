$base = "C:\Users\siva\Downloads"

# KEEP only these folder names
$keepFolders = @(
    "klosud frs",
    "AttendanceSystem",
    "ai_license_plate_system"
)

Write-Host "=== CLEANING C:\Users\siva\Downloads ==="
Write-Host "Keeping: $($keepFolders -join ', ')"
Write-Host ""

$freed = 0

# Delete folders NOT in keep list
$dirs = Get-ChildItem $base -Directory -ErrorAction SilentlyContinue
foreach ($dir in $dirs) {
    $keep = $false
    foreach ($k in $keepFolders) {
        if ($dir.Name -eq $k) { $keep = $true; break }
    }
    if ($keep) {
        Write-Host "KEEP   DIR : $($dir.Name)"
    } else {
        $size = (Get-ChildItem $dir.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        $mb = [math]::Round($size/1MB,1)
        Write-Host "DELETE DIR : $($dir.Name)  ($mb MB)"
        Remove-Item $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
        $freed += $size
    }
}

# Delete ALL loose files in Downloads root
Write-Host ""
Write-Host "Deleting all loose files in Downloads..."
$files = Get-ChildItem $base -File -ErrorAction SilentlyContinue
foreach ($file in $files) {
    $mb = [math]::Round($file.Length/1MB,1)
    Write-Host "DELETE FILE: $($file.Name)  ($mb MB)"
    Remove-Item $file.FullName -Force -ErrorAction SilentlyContinue
    $freed += $file.Length
}

Write-Host ""
Write-Host "========================================"
Write-Host "FREED from Downloads: $([math]::Round($freed/1GB,2)) GB"
Write-Host ""
Write-Host "Remaining in Downloads:"
Get-ChildItem $base | ForEach-Object {
    Write-Host "  $($_.Name)"
}
Write-Host "========================================"
