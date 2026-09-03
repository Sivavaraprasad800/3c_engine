Write-Host "=== D:\ Contents ==="
Get-ChildItem "D:\" | Select-Object Name, LastWriteTime, @{N="Type";E={if($_.PSIsContainer){"DIR"}else{"FILE"}}}

Write-Host ""
Write-Host "=== Disk Free Space ==="
$d = Get-PSDrive D
Write-Host "D:\ Free : $([math]::Round($d.Free/1GB,2)) GB"
Write-Host "D:\ Used : $([math]::Round($d.Used/1GB,2)) GB"
