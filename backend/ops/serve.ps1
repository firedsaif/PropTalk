# serve.ps1 - start the PropTalk backend + cloudflared tunnel, point Retell at it, verify.
# One command to go from nothing -> ready-to-call. Safe to re-run: it stops anything old first.
#
#   cd D:\US\backend
#   powershell -ExecutionPolicy Bypass -File ops\serve.ps1
#
# Auto-picks a free port (8000, then 8001, ...) so a stuck socket never blocks you.
param([int]$Port = 8000)

$backend = Split-Path $PSScriptRoot -Parent
$py = Join-Path $backend '.venv\Scripts\python.exe'
$cf = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
$logDir = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Write-Host '[1/5] Stopping any existing backend + tunnel...'
& (Join-Path $PSScriptRoot 'stop.ps1') | Out-Null
Start-Sleep -Seconds 2

while (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "      port $Port busy, trying $($Port + 1)"
    $Port++
}

Write-Host "[2/5] Starting backend on port $Port..."
Start-Process -FilePath $py `
    -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--port', "$Port") `
    -WorkingDirectory $backend `
    -RedirectStandardOutput (Join-Path $logDir 'backend.out.log') `
    -RedirectStandardError (Join-Path $logDir 'backend.err.log') `
    -WindowStyle Hidden
$up = $false
for ($i = 0; $i -lt 30; $i++) {
    try { Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 2 | Out-Null; $up = $true; break }
    catch { Start-Sleep -Seconds 1 }
}
if (-not $up) { Write-Host '      BACKEND FAILED - see ops\logs\backend.err.log'; exit 1 }
Write-Host "      backend healthy on $Port"

Write-Host '[3/5] Starting tunnel (needs internet/DNS; retries once)...'
$cfLog = Join-Path $logDir 'tunnel.err.log'
$url = $null
foreach ($attempt in 1, 2) {
    if (Test-Path $cfLog) { Remove-Item $cfLog -Force -ErrorAction SilentlyContinue }
    Start-Process -FilePath $cf `
        -ArgumentList @('tunnel', '--url', "http://localhost:$Port") `
        -RedirectStandardOutput (Join-Path $logDir 'tunnel.out.log') `
        -RedirectStandardError $cfLog `
        -WindowStyle Hidden
    for ($i = 0; $i -lt 30; $i++) {
        if (Test-Path $cfLog) {
            $m = Select-String -Path $cfLog -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($m) { $url = $m.Matches[0].Value; break }
            if (Select-String -Path $cfLog -Pattern 'failed to request quick Tunnel' -Quiet -ErrorAction SilentlyContinue) { break }
        }
        Start-Sleep -Seconds 1
    }
    if ($url) { break }
    Write-Host "      tunnel attempt $attempt failed (DNS?), retrying..."
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}
if (-not $url) { Write-Host '      TUNNEL FAILED (DNS/network) - see ops\logs\tunnel.err.log. Backend is still up.'; exit 1 }
Write-Host "      tunnel: $url"

Write-Host '[4/5] Pointing Retell at the tunnel + syncing agent tuning...'
& $py (Join-Path $backend 'scripts\retell_provision.py') update-urls --base-url $url

Write-Host '[5/5] Smoke test through the tunnel...'
& $py (Join-Path $backend 'scripts\smoke_test.py') $url

Write-Host ''
Write-Host '============================================================'
Write-Host " READY. Make your web call in the Retell dashboard."
Write-Host " Tunnel: $url"
Write-Host " After the call, run:  .\ops\after-call.ps1"
Write-Host " To stop everything:   .\ops\stop.ps1"
Write-Host '============================================================'
