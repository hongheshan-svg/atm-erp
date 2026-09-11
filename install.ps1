param([string]$EnvFile = (Join-Path $PSScriptRoot '.env.lean'), [switch]$SkipBuild, [switch]$NoOta)
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
function Invoke-OtaPython {
  if ($env:PYTHON) { & $env:PYTHON @args } else { & py -3.11 @args }
  if ($LASTEXITCODE -ne 0) { throw '升级执行器配置失败，请检查宿主机 Python 3.11 和服务日志。' }
}
if (-not $NoOta) { Invoke-OtaPython -c 'import sys; assert sys.version_info[:2] == (3, 11)' }
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
if ([IO.File]::ReadAllText($EnvFile) -notmatch '(?m)^LEAN_OTA_AGENT_TOKEN=.+') {
  [IO.File]::AppendAllText($EnvFile, "`nLEAN_OTA_AGENT_TOKEN=$(Random-Hex 32)`n", [Text.UTF8Encoding]::new($false))
}
$compose = @('compose', '--env-file', $EnvFile, '-f', (Join-Path $PSScriptRoot 'docker-compose.yml'))
Invoke-Docker @compose config --quiet
if (Test-Path (Join-Path $PSScriptRoot 'INSTALL-MANIFEST.json')) {
  Invoke-OtaPython (Join-Path $PSScriptRoot 'scripts/release_install.py') --root $PSScriptRoot --config $EnvFile
} elseif (-not $SkipBuild) { Invoke-Docker @compose build app }
Invoke-Docker @compose up -d --no-build --wait --wait-timeout 180
if (-not $NoOta) {
  Invoke-OtaPython (Join-Path $PSScriptRoot 'scripts/ota_service.py') install --mode docker --root $PSScriptRoot --config $EnvFile
}
Write-Host "安装完成。管理员 admin 的首次密码位于 $EnvFile 的 LEAN_ADMIN_PASSWORD。"
Write-Host '访问配置端口的 /erp/，首次登录自动进入快速安装向导，完成后使用新密码登录即可开单。'
