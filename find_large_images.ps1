$folders = @("face-detection-dashboard","sw","swagatika","openclaw","fs 2.o","Face-Detection-cctv","frs best","3c","3c.o","proble soloving","zdot-attend","old","z.attend-backend","backup","StillName","hh","New folder","Seventeen","sivaproject","mian","attdacs pc")

$imageExts = @(".jpg",".jpeg",".png",".gif",".bmp",".mp4",".avi",".mov",".mkv",".webm",".zip",".tar",".gz",".rar",".7z",".pkl",".faiss",".pth",".pt",".onnx",".bin",".db",".sqlite")

Write-Host "=== LARGE FILES (>10MB) IN OLD FOLDERS ==="
Write-Host ""

$grandTotal = 0

foreach ($f in $folders) {
    $path = "D:\$f"
    if (-not (Test-Path $path)) { continue }

    $bigFiles = Get-ChildItem $path -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Length -gt 10MB -and ($imageExts -contains $_.Extension.ToLower()) } |
        Sort-Object Length -Descending

    if ($bigFiles.Count -gt 0) {
        $folderTotal = ($bigFiles | Measure-Object -Property Length -Sum).Sum
        $grandTotal += $folderTotal
        Write-Host "--- $f  [$(($bigFiles.Count)) files, $([math]::Round($folderTotal/1MB,1)) MB total] ---"
        foreach ($file in $bigFiles | Select-Object -First 10) {
            $mb = [math]::Round($file.Length/1MB, 1)
            $rel = $file.FullName.Replace("D:\$f\","")
            Write-Host "  $($mb.ToString().PadLeft(8)) MB   $rel"
        }
        if ($bigFiles.Count -gt 10) {
            Write-Host "  ... and $($bigFiles.Count - 10) more files"
        }
        Write-Host ""
    }
}

Write-Host "========================================"
Write-Host "TOTAL LARGE IMAGE/MEDIA FILES: $([math]::Round($grandTotal/1GB,2)) GB"
