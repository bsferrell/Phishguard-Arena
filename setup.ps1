$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path -LiteralPath ".venv")) {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw "The Python launcher was not found. Install Python 3.13 from https://www.python.org/downloads/ and try again."
    }
    & py -3.13 -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the virtual environment. Check that Python 3.13 is installed."
    }
}

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "The existing .venv does not contain a usable Windows Python interpreter."
}

function Invoke-Python {
    & $python @args
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE. See the output above."
    }
}

& $python -c 'import sys; sys.exit(sys.version_info[:2] != (3, 13))'
if ($LASTEXITCODE -ne 0) {
    throw "The existing .venv must use Python 3.13."
}
Invoke-Python -m pip install --upgrade pip
Invoke-Python -m pip install -r requirements.txt
Invoke-Python check_fts5.py

if (Test-Path -LiteralPath "data\phishguard.db") {
    Write-Host "Existing database kept unchanged; skipping seed."
} else {
    Invoke-Python seed_db.py
}

Write-Host "Setup complete. Start the game with:"
Write-Host "  .\.venv\Scripts\python.exe -m streamlit run app.py"
