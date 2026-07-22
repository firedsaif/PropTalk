# stop.ps1 - kill the PropTalk backend + tunnel. Safe to run even if nothing's up.
#   powershell -ExecutionPolicy Bypass -File ops\stop.ps1

$found = $false
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*uvicorn*app.main*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host "stopped backend PID $($_.ProcessId)"; $found = $true }

Get-Process cloudflared -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue; Write-Host "stopped tunnel PID $($_.Id)"; $found = $true }

if (-not $found) { Write-Host 'Nothing was running.' } else { Write-Host 'Stopped.' }
