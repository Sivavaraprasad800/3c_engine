Write-Host "=== TOP SPACE USERS ON C:\ ==="
Write-Host ""

# Check biggest folders in C:\Users\siva
$checkPaths = @(
    "C:\Users\siva\Downloads",
    "C:\Users\siva\Desktop",
    "C:\Users\siva\Documents",
    "C:\Users\siva\Pictures",
    "C:\Users\siva\Videos",
    "C:\Users\siva\Music",
    "C:\Users\siva\AppData\Local\Temp",
    "C:\Users\siva\AppData\Local\pip",
    "C:\Users\siva\AppData\Local\Programs",
    "C:\Users\siva\AppData\Roaming\Python",
    "C:\Users\siva\AppData\Local\Packages",
    "C:\Users\siva\.insightface",
    "C:\Users\siva\.cache",
    "C:\Windows\Temp",
    "C:\Windows\SoftwareDistribution\Download"
)

foreach ($p in $checkPaths) {
    if (Test-Path $p) {
        $size = (Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        $gb = [math]::Round($size/1GB, 2)
        $mb = [math]::Round($size/1MB, 0)
        if ($size -gt 50MB) {
            Write-Host "$($p.PadRight(55)) $gb GB  ($mb MB)"
        }
    }
}

Write-Host ""
Write-Host "=== Downloads folder contents (>50MB) ==="
Get-ChildItem "C:\Users\siva\Downloads" -ErrorAction SilentlyContinue |
    ForEach-Object {
        if ($_.PSIsContainer) {
            $size = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        } else {
            $size = $_.Length
        }
        if ($size -gt 50MB) {
            $mb = [math]::Round($size/1MB,1)
            $type = if($_.PSIsContainer){"DIR"}else{"FILE"}
            Write-Host "  $type  $($_.Name.PadRight(50))  $mb MB"
        }
    } | Sort-Object

Write-Host ""
Write-Host "=== Python packages size ==="
$pyPaths = @(
    "C:\Users\siva\AppData\Local\Programs\Python\Python310\Lib\site-packages",
    "C:\Users\siva\AppData\Local\Programs\Python\Python314\Lib\site-packages",
    "C:\Users\siva\AppData\Roaming\Python\Python314\site-packages"
)
foreach ($p in $pyPaths) {
    if (Test-Path $p) {
        $size = (Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        $gb = [math]::Round($size/1GB,2)
        Write-Host "  $p"
        Write-Host "    Size: $gb GB"
    }
}

Write-Host ""
Write-Host "=== Temp folders ==="
$t1 = (Get-ChildItem "C:\Windows\Temp" -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
$t2 = (Get-ChildItem "C:\Users\siva\AppData\Local\Temp" -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
Write-Host "  C:\Windows\Temp              : $([math]::Round($t1/1MB,0)) MB"
Write-Host "  C:\Users\siva\AppData\Local\Temp : $([math]::Round($t2/1MB,0)) MB"
