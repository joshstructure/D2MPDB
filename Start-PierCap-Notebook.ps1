$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectDir '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Host 'Create a Python 3.12 environment and install requirements-pier-cap.txt first. See README.md.'
    exit 1
}
Set-Location -LiteralPath $projectDir
$env:JUPYTER_RUNTIME_DIR = Join-Path $projectDir '.jupyter-runtime\runtime'
$env:JUPYTER_CONFIG_DIR = Join-Path $projectDir '.jupyter-runtime\config'
$env:JUPYTER_DATA_DIR = Join-Path $projectDir '.jupyter-runtime\data'
$env:JUPYTERLAB_WORKSPACES_DIR = Join-Path $projectDir '.jupyter-runtime\workspaces'
$env:JUPYTERLAB_SETTINGS_DIR = Join-Path $projectDir '.jupyter-runtime\settings'
$env:IPYTHONDIR = Join-Path $projectDir '.jupyter-runtime\ipython'
& $pythonPath -m jupyterlab --ServerApp.ip=127.0.0.1 'Pier_Cap_Design_Optimizer.ipynb'
