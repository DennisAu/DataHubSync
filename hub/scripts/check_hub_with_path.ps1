# Temporarily add conda to PATH for this session
$condaPath = "C:\Users\Dennis\anaconda3\Scripts"
$condaCondabin = "C:\Users\Dennis\anaconda3\condabin"

if (Test-Path $condaPath) {
    $env:PATH = "$env:PATH;$condaPath"
    Write-Host "Added to PATH: $condaPath"
}

if (Test-Path $condaCondabin) {
    $env:PATH = "$env:PATH;$condaCondabin"
    Write-Host "Added to PATH: $condaCondabin"
}

Write-Host ""
Write-Host "Now running check_hub_local.ps1 with updated PATH..."
Write-Host ""

# Use relative path to call the script
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$checkScriptPath = Join-Path $ScriptDir "check_hub_local.ps1"

& $checkScriptPath