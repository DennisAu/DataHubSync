Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

# Use relative paths from script location
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)

# Try multiple possible config paths relative to project
$configPaths = @(
    (Join-Path $ProjectRoot "config.yaml"),
    (Join-Path $ProjectRoot "hub\config\config.yaml")
)

$ConfigPath = $null
foreach ($path in $configPaths) {
    if (Test-Path $path) {
        $ConfigPath = $path
        break
    }
}

# Server path relative to project
$ServerPath = Join-Path (Split-Path -Parent $ScriptDir) "server.py"

Write-Host "=========================================="
Write-Host "DataHubSync Hub Check (PowerShell - Hub Local)"
Write-Host "=========================================="
Write-Host "Config: $ConfigPath"
Write-Host "Server: $ServerPath"
Write-Host ""

$errors = @()

# Check conda first - prioritize full paths since PATH is not set
$condaFound = $false
$condaPaths = @(
    "C:\Users\Dennis\anaconda3\Scripts\conda.exe",  # Most likely path
    "C:\Users\Dennis\anaconda3\condabin\conda.bat",
    "C:\Users\Dennis\Miniconda3\Scripts\conda.exe", 
    "C:\Users\Dennis\Miniconda3\condabin\conda.bat",
    "C:\Anaconda3\Scripts\conda.exe",
    "C:\Miniconda3\Scripts\conda.exe",
    "conda"  # Try from PATH last
)

foreach ($condaPath in $condaPaths) {
    try {
        if ($condaPath -eq "conda") {
            $condaCheck = Get-Command conda -ErrorAction SilentlyContinue
            if ($condaCheck) {
                Write-Ok "conda command found in PATH: $($condaCheck.Source)"
                $condaFound = $true
                $condaCmd = "conda"
                break
            }
        } else {
            if (Test-Path $condaPath) {
                Write-Ok "conda command found at: $condaPath"
                $condaFound = $true
                $condaCmd = $condaPath
                break
            }
        }
    } catch {
        # Continue to next path
    }
}

if (-not $condaFound) {
    $errors += "conda command not found in PATH or common locations"
    $errors += "Tried: $($condaPaths -join ', ')"
}

if ($errors.Count -eq 0) {
    # Check conda environments
    try {
        $envList = & $condaCmd env list 2>$null
        Write-Host "Available conda environments:"
        Write-Host $envList
        Write-Host ""
        
        if ($envList -match "quant_dev") {
            Write-Ok "conda environment quant_dev found"
            
            # Test conda run
            try {
                $result = & $condaCmd run -n quant_dev python --version 2>&1
                if ($LASTEXITCODE -eq 0) {
                    Write-Ok "conda run successful in quant_dev environment"
                    Write-Host "Python version: $result"
                    $Python = "$condaCmd run -n quant_dev python"
                } else {
                    $errors += "conda run failed in quant_dev environment: $result"
                }
            } catch {
                $errors += "Failed to run conda run in quant_dev environment: $_"
            }
        } else {
            $errors += "conda environment quant_dev not found. Available environments:"
            $errors += $envList
        }
    } catch {
        $errors += "Failed to list conda environments: $_"
    }
}

# Check config file
if (-not (Test-Path $ConfigPath)) {
    $errors += "Config file not found: $ConfigPath"
} else {
    Write-Ok "Config file exists"
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
        $errors += "PyYAML not available in quant_dev environment"
    } else {
        Write-Ok "PyYAML available"
    }
}

if ($errors.Count -eq 0) {
    # Parse config with simple inline script
    $tempScript = [System.IO.Path]::GetTempFileName() + ".py"
    $py = @"
import json
import yaml

with open(r'''$ConfigPath''', 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

server = cfg.get('server', {})
output = {
    'data_root': server.get('data_root'),
    'cache_dir': server.get('cache_dir'),
    'datasets': cfg.get('datasets', [])
}
print(json.dumps(output))
"@
    
    try {
        $py | Out-File -FilePath $tempScript -Encoding UTF8
        $configJson = Invoke-Expression "$Python $tempScript"
        
        Write-Host "Raw JSON output: '$configJson'"
        
        if (-not $configJson -or $configJson.Trim() -eq "") {
            $errors += "No output from config parsing script"
        } else {
            try {
                # Clean up the JSON string - remove trailing whitespace and quotes
                $cleanJson = $configJson.Trim().TrimEnd('"''')
                Write-Host "Cleaned JSON: '$cleanJson'"
                
                $cfg = $cleanJson | ConvertFrom-Json
                Write-Host "Parsed config successfully"
                Write-Host "Config object properties: $($cfg | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name)"
            } catch {
                $errors += "Failed to parse JSON output: $_. Raw output was: $configJson"
            }
        }
    } finally {
        if (Test-Path $tempScript) {
            Remove-Item $tempScript -Force
        }
    }
}

if ($errors.Count -eq 0) {
    # Safely access properties using Select-Object
    $dataRoot = $cfg | Select-Object -ExpandProperty data_root -ErrorAction SilentlyContinue
    $cacheDir = $cfg | Select-Object -ExpandProperty cache_dir -ErrorAction SilentlyContinue
    $datasets = $cfg | Select-Object -ExpandProperty datasets -ErrorAction SilentlyContinue
    
    if (-not $dataRoot) {
        $errors += "server.data_root is missing in config"
    } elseif (-not (Test-Path $dataRoot)) {
        $errors += "data_root directory not found: $dataRoot"
    } else {
        Write-Ok "data_root: $dataRoot"
    }

    if (-not $cacheDir) {
        $errors += "server.cache_dir is missing in config"
    } elseif (-not (Test-Path $cacheDir)) {
        Write-Warn "cache_dir directory not found: $cacheDir - attempting to create..."
        try {
            New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null
            Write-Ok "cache_dir created: $cacheDir"
        } catch {
            $errors += "Failed to create cache_dir: $_"
        }
    } else {
        Write-Ok "cache_dir: $cacheDir"
    }

    if (-not $datasets -or $datasets.Count -eq 0) {
        $errors += "datasets list is empty in config"
    } else {
        Write-Ok "datasets configured: $($datasets.Count)"
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
Write-Host "conda run -n quant_dev python `"$ServerPath`" --config `"$ConfigPath`""
Write-Host ""
Write-Host "输入任意键后退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")