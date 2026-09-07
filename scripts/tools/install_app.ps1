# install_app.ps1 — Install FRS 3C Engine as a proper Windows application
# Creates Desktop + Start Menu + Startup shortcuts
# Double-clicking the shortcut opens the native app window (no browser)

$AppDir  = "d:\kk]\siva\frs_ai_model-main\frs_ai_model-main"
$Python  = "C:\Users\siva\AppData\Local\Programs\Python\Python310\pythonw.exe"
$Script  = "$AppDir\launcher.pyw"
$Icon    = "$AppDir\icon.ico"
$AppName = "3C Engine FRS"

Write-Host ""
Write-Host "=== Installing FRS 3C Engine ===" -ForegroundColor Cyan
Write-Host ""

$WS = New-Object -ComObject WScript.Shell

function Make-Shortcut($path) {
    $SC = $WS.CreateShortcut($path)
    $SC.TargetPath       = $Python
    $SC.Arguments        = "`"$Script`""
    $SC.WorkingDirectory = $AppDir
    $SC.WindowStyle      = 1
    if (Test-Path $Icon) { $SC.IconLocation = $Icon }
    $SC.Description      = "FRS 3C Engine - Face Recognition System"
    $SC.Save()
    Write-Host "  [OK] $path" -ForegroundColor Green
}

# Desktop
Make-Shortcut "$([Environment]::GetFolderPath('Desktop'))\$AppName.lnk"

# Start Menu
Make-Shortcut "$([Environment]::GetFolderPath('StartMenu'))\Programs\$AppName.lnk"

# Startup (auto-start on boot)
Make-Shortcut "$([Environment]::GetFolderPath('Startup'))\$AppName.lnk"

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Cyan
Write-Host "  Desktop shortcut  : $AppName" -ForegroundColor White
Write-Host "  Start Menu        : Windows key -> type '3C Engine'" -ForegroundColor White
Write-Host "  Auto-start        : Registered in Windows Startup" -ForegroundColor White
Write-Host ""
Write-Host "  Double-click the desktop shortcut to open the app." -ForegroundColor Yellow
Write-Host ""
