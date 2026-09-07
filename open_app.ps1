# open_app.ps1 — Opens FRS 3C Engine native app window
# This starts the server (if not already running) and opens the native window

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "C:\Users\siva\AppData\Local\Programs\Python\Python310\python.exe"
$Tray   = Join-Path $AppDir "tray.pyw"

# Check if server is already running
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8001/api/v1/health" -TimeoutSec 2 -UseBasicParsing
    Write-Host "Server already running — opening window..."
    # Just open the native window
    & $Python -c "import webview; w=webview.create_window('3C Engine — Face Recognition System','http://localhost:8001',width=1280,height=800,min_size=(900,600)); webview.start(gui='edgechromium')"
} catch {
    Write-Host "Starting FRS server + opening window..."
    & $Python $Tray
}
