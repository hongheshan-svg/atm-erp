$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$testFile = Join-Path ([IO.Path]::GetTempPath()) ("lean-install-test-" + [Guid]::NewGuid().ToString() + '.env')
$global:DockerCalls = [Collections.Generic.List[string]]::new()
function global:docker {
  $global:DockerCalls.Add(($args -join ' '))
  $global:LASTEXITCODE = 0
}
try {
  & (Join-Path $root 'install.ps1') -EnvFile $testFile -SkipBuild
  $before = [IO.File]::ReadAllText($testFile)
  if ($before -notmatch 'LEAN_IMAGE=atm-erp-lean:local') { throw 'Image setting was not persisted' }
  if ($before -notmatch 'LEAN_ADMIN_PASSWORD=Lean-[a-f0-9]{48}') { throw 'Initial password is missing' }
  if ($global:DockerCalls.Exists([Predicate[string]]{ param($value) $value -match ' build app$' })) { throw 'SkipBuild still built the image' }
  & (Join-Path $root 'install.ps1') -EnvFile $testFile
  if ($before -ne [IO.File]::ReadAllText($testFile)) { throw 'Repeated install replaced configuration or credentials' }
  if (-not $global:DockerCalls.Exists([Predicate[string]]{ param($value) $value -match ' build app$' })) { throw 'Build command was not dispatched' }
  if (-not $global:DockerCalls.Exists([Predicate[string]]{ param($value) $value -match ' up -d --wait --wait-timeout 180$' })) { throw 'Health-gated startup was not dispatched' }
  Write-Host 'PowerShell installer dispatch and configuration preservation passed.'
} finally {
  Remove-Item $testFile -ErrorAction SilentlyContinue
  Remove-Item Function:global:docker -ErrorAction SilentlyContinue
}
