[CmdletBinding()]
param(
    [ValidateSet('Start', 'Validate', 'Stop')]
    [string]$Action = 'Start',
    [switch]$Observability,
    [switch]$EnableGroq,
    [ValidateRange(1024, 65535)]
    [int]$PostgresHostPort = 5432
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

function Require-Command([string]$Name, [string]$Recovery) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required tool '$Name' was not found. $Recovery"
    }
}

function Read-EnvValue([string]$Name) {
    $matches = @(Get-Content -LiteralPath '.env' | Where-Object {
        $_ -match ('^\s*' + [regex]::Escape($Name) + '\s*=')
    })
    if ($matches.Count -ne 1) {
        throw "Expected exactly one $Name definition in ignored .env."
    }
    return ($matches[0] -split '=', 2)[1].Trim()
}

function Wait-Http([string]$Url, [int]$Attempts = 30) {
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) { return }
        } catch {
            if ($attempt -eq $Attempts) {
                throw "Timed out waiting for $Url. Run 'docker compose ps' and 'docker compose logs api worker' for safe diagnostics."
            }
        }
        Start-Sleep -Seconds 2
    }
}

Require-Command 'docker' 'Install or start Docker Desktop.'
Require-Command 'uv' 'Install uv and Python 3.12 before running validation commands.'
if (-not (Test-Path -LiteralPath '.env')) {
    throw "Missing .env. Run 'Copy-Item .env.example .env', then review local-only placeholders."
}
git check-ignore --quiet .env
if ($LASTEXITCODE -ne 0) { throw '.env must remain ignored before the demo can start.' }

$composeArgs = @('--env-file', '.env', '--profile', 'demo')
if ($Observability) { $composeArgs += @('--profile', 'observability') }
$env:COLDCHAIN_POSTGRES_HOST_PORT = $PostgresHostPort.ToString()

if ($Action -eq 'Stop') {
    & docker compose @composeArgs stop
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose could not stop the local services.' }
    Write-Host 'ColdChain Sentinel services stopped. Containers, volumes, and data were preserved.'
    exit 0
}

$overridePath = $null
try {
    $env:LLM_PROVIDER = 'deterministic'
    $env:LLM_LIVE_CALLS_ENABLED = 'false'
    if ($EnableGroq) {
        $groqKey = Read-EnvValue 'GROQ_API_KEY'
        if (-not $groqKey -or $groqKey -notmatch '^gsk_[A-Za-z0-9_-]{20,}$') {
            throw 'GROQ_API_KEY is missing or malformed. Keep it only in ignored .env.'
        }
        $env:GROQ_API_KEY = $groqKey
        $env:LLM_PROVIDER = 'groq'
        $env:LLM_LIVE_CALLS_ENABLED = 'true'
        $env:LLM_BASE_URL = 'https://api.groq.com/openai/v1'
        $env:LLM_API_KEY_ENV = 'GROQ_API_KEY'
        $env:LLM_MODEL = 'openai/gpt-oss-20b'
        $overridePath = Join-Path $repoRoot 'tmp\groq-demo.override.yaml'
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $overridePath) | Out-Null
        [IO.File]::WriteAllText($overridePath, @"
services:
  api:
    environment:
      LLM_PROVIDER: `${LLM_PROVIDER}
      LLM_BASE_URL: `${LLM_BASE_URL}
      LLM_API_KEY_ENV: `${LLM_API_KEY_ENV}
      LLM_MODEL: `${LLM_MODEL}
      LLM_LIVE_CALLS_ENABLED: `${LLM_LIVE_CALLS_ENABLED}
      GROQ_API_KEY: `${GROQ_API_KEY}
  worker:
    environment:
      LLM_PROVIDER: `${LLM_PROVIDER}
      LLM_BASE_URL: `${LLM_BASE_URL}
      LLM_API_KEY_ENV: `${LLM_API_KEY_ENV}
      LLM_MODEL: `${LLM_MODEL}
      LLM_LIVE_CALLS_ENABLED: `${LLM_LIVE_CALLS_ENABLED}
      GROQ_API_KEY: `${GROQ_API_KEY}
"@)
        $composeArgs = @('-f', 'compose.yaml', '-f', $overridePath) + $composeArgs
        Write-Host 'Provider mode: Groq explicitly enabled. The key value will not be displayed.'
    } else {
        Write-Host 'Provider mode: deterministic. External AI calls are disabled.'
    }

    & docker compose @composeArgs config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Compose configuration is invalid. Review .env placeholders.' }

    if ($Action -eq 'Start') {
        & docker compose @composeArgs up -d --build --wait
        if ($LASTEXITCODE -ne 0) {
            throw "Compose startup failed. Run 'docker compose ps' and inspect service logs; do not delete volumes."
        }
    }

    Wait-Http 'http://127.0.0.1:8000/api/v1/health/live'
    Wait-Http 'http://127.0.0.1:8000/api/v1/health/ready'
    Wait-Http 'http://127.0.0.1:4173/'
    Wait-Http 'http://127.0.0.1:6333/readyz'

    Write-Host ''
    Write-Host 'Local URLs:'
    Write-Host '  Control tower: http://127.0.0.1:4173/'
    Write-Host '  API docs:     http://127.0.0.1:8000/docs'
    if ($Observability) {
        Write-Host '  Grafana:      http://127.0.0.1:13001/'
        Write-Host '  Prometheus:   http://127.0.0.1:19090/'
        Write-Host '  Jaeger:       http://127.0.0.1:16687/'
    }
    Write-Host ''
    Write-Host 'Recommended path: Dispatcher -> Demo Lab -> Sustained temperature breach -> Open investigation -> Review evidence -> Approve hold -> Audit timeline.'
    Write-Host 'Demo Lab creates a unique synthetic run; this launcher never resets or deletes existing data.'
} finally {
    Remove-Item Env:GROQ_API_KEY -ErrorAction SilentlyContinue
    if ($overridePath -and (Test-Path -LiteralPath $overridePath)) {
        Remove-Item -LiteralPath $overridePath -Force
    }
}
