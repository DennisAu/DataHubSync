Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

function Get-PythonCommand {
    # 首先尝试使用conda环境quant_dev
    try {
        # 使用conda run命令来运行指定环境的python
        $result = conda run -n quant_dev python --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Found conda environment: quant_dev"
            return "conda run -n quant_dev python"
        }
    } catch {
        # conda命令失败，继续尝试其他方法
    }
    
    # 回退到普通的python命令
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) { 
        return 'python' 
    }
    $python3Cmd = Get-Command python3 -ErrorAction SilentlyContinue
    if ($python3Cmd) { 
        return 'python3' 
    }
    return $null
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$HubDir = Resolve-Path (Join-Path $ScriptDir '..')

# Try multiple possible config file locations
$configLocations = @(
    (Join-Path (Split-Path -Parent (Split-Path -Parent $ScriptDir)) 'config.yaml'),
    (Join-Path (Split-Path -Parent (Split-Path -Parent $ScriptDir)) 'config\config.yaml'),
    "C:\Users\Dennis\projects\DataAborder\config.yaml",
    "e:\projects\DataAborder\config.yaml"
)

$ConfigPath = $null
foreach ($location in $configLocations) {
    if (Test-Path $location) {
        $ConfigPath = $location
        break
    }
}
$ServerPath = Join-Path $HubDir 'server.py'

Write-Host "=========================================="
Write-Host "DataHubSync Hub Check (PowerShell)"
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
if (-not $ConfigPath -or -not (Test-Path $ConfigPath)) {
    $errors += "Config file not found in any expected location"
} else {
    Write-Ok "Config file found: $ConfigPath"
}

# Check server file
if (-not (Test-Path $ServerPath)) {
    $errors += "Server file not found: $ServerPath"
} else {
    Write-Ok "Server file exists"
}

if ($errors.Count -eq 0) {
    # Check PyYAML
    Invoke-Expression "$Python -c `"import yaml`"" 2>$null
    if ($LASTEXITCODE -ne 0) {
        $errors += "PyYAML not available (pip install PyYAML)"
    } else {
        Write-Ok "PyYAML available"
    }
}

if ($errors.Count -eq 0) {
    # Parse config with Python and extract required fields
    $tempScript = [System.IO.Path]::GetTempFileName() + ".py"
    $py = @"
import json
import yaml
from pathlib import Path

config_path = r'''$ConfigPath'''
with open(config_path, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

server = cfg.get('server', {}) or {}
hub = cfg.get('hub', {}) or {}
output = {
    'data_root': server.get('data_root') or hub.get('data_dir'),
    'cache_dir': server.get('cache_dir') or hub.get('cache_dir'),
    'datasets': cfg.get('datasets', [])
}
print(json.dumps(output))
"@
    
    try {
        # Write Python code to temp file
        $py | Out-File -FilePath $tempScript -Encoding UTF8
        $configJson = Invoke-Expression "$Python $tempScript"
        
        if (-not $configJson -or $configJson.Trim() -eq "") {
            $errors += "No output from config parsing script"
        } else {
            try {
                $cfg = $configJson | ConvertFrom-Json
            } catch {
                $errors += "Failed to parse JSON output: $_. Raw output was: $configJson"
            }
        }
    } catch {
        $errors += "Failed to parse config.yaml: $_"
    } finally {
        # Clean up temp file
        if (Test-Path $tempScript) {
            Remove-Item $tempScript -Force
        }
    }
}

if ($errors.Count -eq 0) {
    if (-not $cfg.data_root) {
        $errors += "data_root is missing in config"
    } elseif (-not (Test-Path $cfg.data_root)) {
        $errors += "data_root directory not found: $($cfg.data_root)"
    } else {
        Write-Ok "data_root: $($cfg.data_root)"
    }

    if (-not $cfg.cache_dir) {
        $errors += "cache_dir is missing in config"
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
    Write-Host ""
    Write-Host "输入任意键后退出..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

Write-Host ""
Write-Ok "All checks passed. Ready to start hub server!"
Write-Host ""
Write-Host "To start the server, run:"
Write-Host "python `"$ServerPath`" --config `"$ConfigPath`""
Write-Host ""
Write-Host "输入任意键后退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")