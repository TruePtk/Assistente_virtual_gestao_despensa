param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$projectPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not $Python) {
    $Python = if (Test-Path $projectPython) { $projectPython } else { "python" }
}
$cloudflared = Get-Command cloudflared.exe -ErrorAction SilentlyContinue
$cloudflaredPath = $cloudflared.Source
if (-not $cloudflaredPath) {
    $localCloudflared = Join-Path $projectRoot ".tools\cloudflared.exe"
    if (Test-Path $localCloudflared) {
        $cloudflaredPath = $localCloudflared
    }
    else {
        throw "cloudflared não foi encontrado. Instale-o pelo guia oficial: https://developers.cloudflare.com/tunnel/downloads/"
    }
}

$logPrefix = Join-Path $env:TEMP ("despensa-cloudflared-" + [guid]::NewGuid().ToString("N"))
$stdoutPath = "$logPrefix.out.log"
$stderrPath = "$logPrefix.err.log"
$baseUrlAnterior = $env:SHORTCUT_API_BASE_URL
$tunnelProcess = $null

try {
    $tunnelProcess = Start-Process `
        -FilePath $cloudflaredPath `
        -ArgumentList @("tunnel", "--url", "http://127.0.0.1:8765") `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath

    $apiUrl = $null
    for ($tentativa = 0; $tentativa -lt 60 -and -not $apiUrl; $tentativa++) {
        Start-Sleep -Seconds 1
        if ($tunnelProcess.HasExited) {
            throw "cloudflared encerrou antes de criar o túnel. Consulte a saída em $stderrPath"
        }
        $logs = (Get-Content $stdoutPath, $stderrPath -Raw -ErrorAction SilentlyContinue) -join "`n"
        if ($logs -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
            $apiUrl = $Matches[0]
        }
    }
    if (-not $apiUrl) {
        throw "Não recebi a URL pública do Quick Tunnel dentro de 60 segundos. Consulte $stderrPath"
    }

    $env:SHORTCUT_API_BASE_URL = $apiUrl
    Write-Host "API pública temporária: $apiUrl"
    Write-Host "O túnel e o bot ficarão ativos até você pressionar Ctrl+C."
    Push-Location $projectRoot
    try {
        & $Python main.py
        if ($LASTEXITCODE -ne 0) {
            throw "O bot encerrou com código $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($null -ne $baseUrlAnterior) {
        $env:SHORTCUT_API_BASE_URL = $baseUrlAnterior
    }
    else {
        Remove-Item Env:SHORTCUT_API_BASE_URL -ErrorAction SilentlyContinue
    }
    if ($tunnelProcess -and -not $tunnelProcess.HasExited) {
        Stop-Process -Id $tunnelProcess.Id -Force
    }
    Remove-Item $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
}
