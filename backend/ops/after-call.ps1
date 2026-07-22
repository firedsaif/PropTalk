# after-call.ps1 - run this AFTER each Retell web call.
# Pulls the newest call from Retell's API and generates + sends its summary email.
# Needed because the dev tunnel drops the big end-of-call webhooks (see ops\README isn't
# it - see backend\README.md and docs\gauntlet.md). Safe to re-run (one email per call).
#   powershell -ExecutionPolicy Bypass -File ops\after-call.ps1  [call_id]

$backend = Split-Path $PSScriptRoot -Parent
$py = Join-Path $backend '.venv\Scripts\python.exe'
& $py (Join-Path $backend 'scripts\reconcile_call.py') @args
