$folders = @("face-detection-dashboard","sw","swagatika","openclaw","fs 2.o","Face-Detection-cctv","frs best","3c","3c.o","proble soloving","zdot-attend","old","z.attend-backend","backup","StillName","hh","New folder","Seventeen","sivaproject","mian","attdacs pc")
$total = 0
foreach ($f in $folders) {
    $path = "D:\$f"
    if (Test-Path $path) {
        $size = (Get-ChildItem $path -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        $mb = [math]::Round($size/1MB, 1)
        $total += $size
        Write-Host "$($f.PadRight(28)) $mb MB"
    } else {
        Write-Host "$($f.PadRight(28)) NOT FOUND"
    }
}
Write-Host ""
Write-Host "TOTAL TO FREE: $([math]::Round($total/1GB, 2)) GB"
