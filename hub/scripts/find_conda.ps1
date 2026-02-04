Write-Host "Searching for conda installations..."
Write-Host ""

# Common conda installation paths
$condaPaths = @(
    "C:\Users\Dennis\anaconda3",
    "C:\Users\Dennis\Miniconda3",
    "C:\Anaconda3", 
    "C:\Miniconda3",
    "C:\Users\Dennis\anaconda3\Scripts",
    "C:\Users\Dennis\Miniconda3\Scripts",
    "C:\Anaconda3\Scripts",
    "C:\Miniconda3\Scripts",
    "C:\Users\Dennis\anaconda3\condabin",
    "C:\Users\Dennis\Miniconda3\condabin"
)

$foundPaths = @()

foreach ($path in $condaPaths) {
    if (Test-Path $path) {
        $foundPaths += $path
        Write-Host "[FOUND] $path"
        
        # Check for conda.exe
        $condaExe = Join-Path $path "conda.exe"
        $condaBat = Join-Path $path "conda.bat"
        
        if (Test-Path $condaExe) {
            Write-Host "  -> conda.exe found"
        }
        if (Test-Path $condaBat) {
            Write-Host "  -> conda.bat found"
        }
    }
}

Write-Host ""
if ($foundPaths.Count -eq 0) {
    Write-Host "[ERROR] No conda installation found in common locations"
} else {
    Write-Host "[SUCCESS] Found $($foundPaths.Count) conda installation(s)"
}

# Check PATH
Write-Host ""
Write-Host "Current PATH directories containing 'conda':"
$pathDirs = $env:PATH -split ';'
foreach ($dir in $pathDirs) {
    if ($dir -like "*conda*" -and (Test-Path $dir)) {
        Write-Host "[PATH] $dir"
        $condaInPath = Join-Path $dir "conda.exe"
        if (Test-Path $condaInPath) {
            Write-Host "  -> conda.exe found in PATH"
        }
    }
}

# Try conda command directly
Write-Host ""
Write-Host "Testing 'conda' command directly:"
try {
    $condaVersion = conda --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] conda command works: $condaVersion"
    } else {
        Write-Host "[ERROR] conda command failed"
    }
} catch {
    Write-Host "[ERROR] conda command not available: $_"
}

Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")