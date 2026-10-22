# FormSynth — quick start (PowerShell)
# Запускает backend и frontend в двух параллельных окнах консоли

$root = $PSScriptRoot

function Check-Command($name) {
    return $null -ne (Get-Command $name -ErrorAction SilentlyContinue)
}

# ── Python ────────────────────────────────────────────────────────────────────
$pythonCmd = if (Check-Command "python") { "python" } `
             elseif (Check-Command "python3") { "python3" } `
             else { $null }

if (-not $pythonCmd) {
    Write-Error "Python not found. Install Python 3.11+ and try again."
    exit 1
}

# ── Node / npm ────────────────────────────────────────────────────────────────
if (-not (Check-Command "npm")) {
    Write-Error "npm not found. Install Node.js 18+ and try again."
    exit 1
}

# ── Backend venv ──────────────────────────────────────────────────────────────
$venv      = Join-Path $root "backend\venv"
$pip       = Join-Path $venv "Scripts\pip.exe"
$uvi       = Join-Path $venv "Scripts\uvicorn.exe"
$reqFile   = Join-Path $root "backend\requirements.txt"
$stampFile = Join-Path $venv ".req_hash"

if (-not (Test-Path $venv)) {
    Write-Host "Creating Python venv..." -ForegroundColor Cyan
    & $pythonCmd -m venv $venv
}

# pip install только если requirements.txt изменился
$currentHash = (Get-FileHash $reqFile -Algorithm MD5).Hash
$savedHash   = if (Test-Path $stampFile) { Get-Content $stampFile -Raw } else { "" }

if ($currentHash.Trim() -ne $savedHash.Trim()) {
    Write-Host "Installing backend dependencies..." -ForegroundColor Cyan
    & $pip install -q -r $reqFile
    $currentHash | Set-Content $stampFile
} else {
    Write-Host "Backend dependencies up to date." -ForegroundColor DarkGray
}

# ── Frontend deps ─────────────────────────────────────────────────────────────
$nodeModules   = Join-Path $root "frontend\node_modules"
$pkgFile       = Join-Path $root "frontend\package.json"
$pkgStampFile  = Join-Path $root "frontend\.pkg_hash"

$pkgHash       = (Get-FileHash $pkgFile -Algorithm MD5).Hash
$pkgSavedHash  = if (Test-Path $pkgStampFile) { Get-Content $pkgStampFile -Raw } else { "" }

if (-not (Test-Path $nodeModules) -or ($pkgHash.Trim() -ne $pkgSavedHash.Trim())) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    Push-Location (Join-Path $root "frontend")
    npm install --silent
    Pop-Location
    $pkgHash | Set-Content $pkgStampFile
} else {
    Write-Host "Frontend dependencies up to date." -ForegroundColor DarkGray
}

# ── Launch ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Starting FormSynth..." -ForegroundColor Green
Write-Host "  Frontend →  http://localhost:5173" -ForegroundColor Cyan
Write-Host "  API docs →  http://localhost:8000/docs" -ForegroundColor DarkGray
Write-Host ""

$backendArgs  = "-NoExit -Command `"& '$uvi' app.main:app --reload --port 8000`""
$frontendArgs = "-NoExit -Command `"npm run dev`""

Start-Process powershell -ArgumentList $backendArgs  -WorkingDirectory (Join-Path $root "backend")
Start-Process powershell -ArgumentList $frontendArgs -WorkingDirectory (Join-Path $root "frontend")

Write-Host "Two console windows opened. Close them to stop the servers." -ForegroundColor Yellow

# Подождать пока Vite поднимется и открыть браузер
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5173"
