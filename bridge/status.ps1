# Check WebBridge status
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:10088/status" -Method Get -ErrorAction Stop
    Write-Host "Bridge server: RUNNING" -ForegroundColor Green
    Write-Host "Extension connected: $(if ($resp.extension_connected) { 'YES' } else { 'NO' })" -ForegroundColor $(if ($resp.extension_connected) { 'Green' } else { 'Yellow' })
} catch {
    Write-Host "Bridge server: NOT RUNNING" -ForegroundColor Red
    Write-Host "Start with: .\bridge\start.ps1" -ForegroundColor Gray
}
