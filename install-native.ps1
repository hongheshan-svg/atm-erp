param(
  [Parameter(Mandatory=$true)][ValidateSet('configure','install','start','check')][string]$Action,
  [string]$Config = (Join-Path $PSScriptRoot 'native-config.json')
)
$ErrorActionPreference = 'Stop'
if ($env:PYTHON) { & $env:PYTHON (Join-Path $PSScriptRoot 'scripts/native_install.py') $Action --config $Config }
else { & py -3.11 (Join-Path $PSScriptRoot 'scripts/native_install.py') $Action --config $Config }
if ($LASTEXITCODE -ne 0) { throw "Native installer failed: $LASTEXITCODE" }
