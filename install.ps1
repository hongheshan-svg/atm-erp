param([string]$EnvFile = (Join-Path $PSScriptRoot '.env.lean'), [switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
function Invoke-Docker { & docker @args; if ($LASTEXITCODE -ne 0) { throw "Docker failed: $LASTEXITCODE" } }
function Random-Hex([int]$Length) {
  $bytes = New-Object byte[] $Length
  $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
  return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}
function Setting([string]$Name, [string]$Default) {
  $value = [Environment]::GetEnvironmentVariable($Name)
  if ($value) { return $value }; return $Default
}
Invoke-Docker compose version
Invoke-Docker info | Out-Null
if (-not (Test-Path $EnvFile)) {
  $content = @(
    "LEAN_PROJECT_NAME=$(Setting 'LEAN_PROJECT_NAME' 'atm-erp-lean')"
    "LEAN_IMAGE=$(Setting 'LEAN_IMAGE' 'atm-erp-lean:local')"
    "LEAN_HTTP_PORT=$(Setting 'LEAN_HTTP_PORT' '8080')"
    "LEAN_BIND_ADDRESS=$(Setting 'LEAN_BIND_ADDRESS' '127.0.0.1')"
    "LEAN_ALLOWED_HOSTS=$(Setting 'LEAN_ALLOWED_HOSTS' 'localhost,127.0.0.1')"
    "LEAN_ENVIRONMENT=$(Setting 'LEAN_ENVIRONMENT' 'production')"
    "LEAN_DB_PASSWORD=$(Random-Hex 32)"
    "LEAN_SECRET_KEY=$(Random-Hex 32)"
    "LEAN_OTA_AGENT_TOKEN=$(Random-Hex 32)"
    "LEAN_ADMIN_PASSWORD=Lean-$(Random-Hex 24)"
  ) -join "`n"
  $stream = [IO.File]::Open($EnvFile, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
  try { $bytes = [Text.UTF8Encoding]::new($false).GetBytes($content + "`n"); $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
  if ($env:OS -eq 'Windows_NT') {
    $acl = Get-Acl $EnvFile
    $acl.SetAccessRuleProtection($true, $false)
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $acl.SetAccessRule([Security.AccessControl.FileSystemAccessRule]::new($identity, 'FullControl', 'Allow'))
    Set-Acl $EnvFile $acl
  }
}
$compose = @('compose', '--env-file', $EnvFile, '-f', (Join-Path $PSScriptRoot 'docker-compose.yml'))
Invoke-Docker @compose config --quiet
if (-not $SkipBuild) { Invoke-Docker @compose build app }
Invoke-Docker @compose up -d --wait --wait-timeout 180
Write-Host "安装完成。管理员 admin 的首次密码位于 $EnvFile 的 LEAN_ADMIN_PASSWORD。"
