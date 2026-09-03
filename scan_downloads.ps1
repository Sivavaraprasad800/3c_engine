$items = Get-ChildItem "C:\Users\siva\Downloads" -ErrorAction SilentlyContinue
$results = @()
foreach ($item in $items) {
    if ($item.PSIsContainer) {
        $size = (Get-ChildItem $item.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        $type = "DIR"
    } else {
        $size = $item.Length
        $type = "FILE"
    }
    $mb = [math]::Round($size/1MB,1)
    $results += [PSCustomObject]@{ Type=$type; MB=$mb; Size=$size; Name=$item.Name }
}
$results | Sort-Object Size -Descending | ForEach-Object {
    Write-Host ($_.Type.PadRight(5) + $_.MB.ToString().PadLeft(9) + " MB   " + $_.Name)
}
