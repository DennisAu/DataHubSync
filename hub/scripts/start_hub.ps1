Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

function Get-PythonCommand {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) { return 'python' }
    $python3Cmd = Get-Command python3 -ErrorAction SilentlyContinue
    if ($python3Cmd) { return 'python3' }
    return $null
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$HubDir = Resolve-Path (Join-Path $ScriptDir '..')
$ConfigPath = Join-Path $HubDir 'config\config.yaml'
$ServerPath = Join-Path $HubDir 'server.py'

Write-Host "=========================================="
Write-Host "DataHubSync Hub Startup (PowerShell)"
Write-Host "=========================================="
Write-Host "Hub Dir:    $HubDir"
Write-Host "Config:     $ConfigPath"
Write-Host "Server:     $ServerPath"
Write-Host ""

$errors = @()

# Check Python
$Python = Get-PythonCommand
if (-not $Python) {
    $errors += "Python not found in PATH (python/python3)"
} else {
    Write-Ok "Python found: $Python"
}

# Check config file
if (-not (Test-Path $ConfigPath)) {
    $errors += "Config file not found: $ConfigPath"
} else {
    Write-Ok "Config file exists"
}

if ($errors.Count -eq 0) {
    # Check PyYAML
    & $Python -c "import yaml" 2>$null
    if ($LASTEXITCODE -ne 0) {
        $errors += "PyYAML not available (pip install PyYAML)"
    } else {
        Write-Ok "PyYAML available"
    }
}

if ($errors.Count -eq 0) {
    # Parse config with Python and extract required fields
    $py = @"
import json
import yaml
from pathlib import Path

config_path = r'''$ConfigPath'''
with open(config_path, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

server = cfg.get('server', {}) or {}
output = {
    'data_root': server.get('data_root'),
    'cache_dir': server.get('cache_dir'),
    'datasets': cfg.get('datasets', [])
}
print(json.dumps(output))
"@

    try {
        $configJson = & $Python -c $py
        $cfg = $configJson | ConvertFrom-Json
    } catch {
        $errors += "Failed to parse config.yaml"
    }
}

if ($errors.Count -eq 0) {
    if (-not $cfg.data_root) {
        $errors += "server.data_root is missing in config"
    } elseif (-not (Test-Path $cfg.data_root)) {
        $errors += "data_root directory not found: $($cfg.data_root)"
    } else {
        Write-Ok "data_root: $($cfg.data_root)"
    }

    if (-not $cfg.cache_dir) {
        $errors += "server.cache_dir is missing in config"
    } elseif (-not (Test-Path $cfg.cache_dir)) {
        $errors += "cache_dir directory not found: $($cfg.cache_dir)"
    } else {
        Write-Ok "cache_dir: $($cfg.cache_dir)"
    }

    if (-not $cfg.datasets -or $cfg.datasets.Count -eq 0) {
        $errors += "datasets list is empty in config"
    } else {
        Write-Ok "datasets configured: $($cfg.datasets.Count)"
    }
}

if ($errors.Count -gt 0) {
    Write-Host ""
    Write-Err "Configuration check failed:"
    foreach ($e in $errors) {
        Write-Err "- $e"
    }
    exit 1
}

Write-Host ""
Write-Ok "All checks passed. Starting hub server..."
Write-Host ""

& $Python $ServerPath -c $ConfigPath
exit $LASTEXITCODE
