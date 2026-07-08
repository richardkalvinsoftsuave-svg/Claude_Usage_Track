# Start the Claude Usage Tracker backend
# This script checks for port conflicts before starting.
param(
    [int]$Port = 8000,
    [string]$HostAddr = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

# --- Check if port is already in use ---
$existing = netstat -ano 2>$null | Select-String ":$Port\s" | Select-String "LISTENING"
if ($existing) {
    $line = $existing.ToString().Trim()
    $parts = -split $line | Where-Object { $_ -ne "" }
    $pidFromNetstat = $parts[-1]
    
    try {
        $proc = Get-Process -Id $pidFromNetstat -ErrorAction Stop
        $procName = $proc.ProcessName
    } catch {
        $procName = "(unknown - PID $pidFromNetstat)"
    }

    Write-Host ""
    Write-Host "⚠️  Port $Port is already in use!" -ForegroundColor Yellow
    Write-Host "   Process: $procName (PID $pidFromNetstat)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Is this a stale instance of this app? Kill it and retry? [Y/n] " -NoNewline
    $response = Read-Host
    if ($response -eq "" -or $response -match "^[Yy]") {
        Stop-Process -Id $pidFromNetstat -Force
        Write-Host "Killed PID $pidFromNetstat. Waiting for port release..." -ForegroundColor Green
        Start-Sleep -Seconds 2
    } else {
        Write-Host "Aborted. Try a different port: .\start.ps1 -Port 8001" -ForegroundColor Red
        exit 1
    }
}

# --- Start the server ---
Write-Host "Starting backend on http://$HostAddr`:$Port ..." -ForegroundColor Green
.venv\Scripts\uvicorn.exe app.main:app --host $HostAddr --port $Port
