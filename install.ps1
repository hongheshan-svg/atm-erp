param([string]$EnvFile = '', [switch]$SkipBuild, [switch]$NoOta, [switch]$WithOta)
$ErrorActionPreference = 'Stop'
if (-not $EnvFile) {
  $EnvFile = Join-Path $PSScriptRoot '.env'
  if (-not (Test-Path $EnvFile) -and (Test-Path (Join-Path $PSScriptRoot '.env.lean'))) { $EnvFile = Join-Path $PSScriptRoot '.env.lean' }
}
# 相对路径按 PowerShell 当前位置转为绝对路径：Test-Path 与 [IO.File] 的相对基准不同，必须检查和读写同一文件。
$EnvFile = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($EnvFile)
$Release = Test-Path (Join-Path $PSScriptRoot 'INSTALL-MANIFEST.json')
$EnableOta = $WithOta -and -not $NoOta
function Invoke-Docker { & docker @args; if ($LASTEXITCODE -ne 0) { throw "Docker 命令执行失败，退出码 $LASTEXITCODE。" } }
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
function Invoke-NetworkCheck {
  # Advisory only: never block the install when Python is unavailable.
  try { if ($env:PYTHON) { & $env:PYTHON @args } else { & py -3.11 @args } } catch { }
}
function Invoke-OtaPython {
  if ($env:PYTHON) { & $env:PYTHON @args } else { & py -3.11 @args }
  if ($LASTEXITCODE -ne 0) { throw '升级执行器配置失败，请检查宿主机 Python 3.11 和服务日志。' }
}
function Invoke-ReleaseInstall {
  if ($env:PYTHON) { & $env:PYTHON @args } else { & py -3.11 @args }
  if ($LASTEXITCODE -ne 0) { throw "发布镜像校验或导入失败（release_install.py 退出码 $LASTEXITCODE），未启动容器，配置中的 LEAN_IMAGE 未改动；请根据上方输出检查 Docker 与随包镜像后重新运行安装器。" }
}
# 发布包的镜像校验导入和可选升级服务都需要宿主机 Python 3.11；在生成配置或改动容器前确认。
if ($EnableOta -or $Release) {
  if ($env:PYTHON) { & $env:PYTHON -c 'import sys; assert sys.version_info[:2] == (3, 11)' } else { & py -3.11 -c 'import sys; assert sys.version_info[:2] == (3, 11)' }
  if ($LASTEXITCODE -ne 0) { throw '发布包安装和网页升级执行器需要宿主机 Python 3.11（可用 PYTHON 环境变量指定）；本次未改动配置或容器。' }
}
Invoke-Docker compose version
Invoke-Docker info | Out-Null
if (-not (Test-Path -LiteralPath $EnvFile)) {
  # 发布包留空 LEAN_IMAGE，沿用 Compose 内置的固定摘要，校验导入后由 release_install.py 写入；
  # 写入本地构建镜像名会遮蔽该摘要，安装中断后直接 Compose 启动就会找不到镜像。
  $content = @(
    "LEAN_PROJECT_NAME=$(Setting 'LEAN_PROJECT_NAME' 'atm-erp-lean')"
    "LEAN_IMAGE=$(if (-not $Release) { Setting 'LEAN_IMAGE' 'atm-erp-lean:local' })"
    "LEAN_HTTP_PORT=$(Setting 'LEAN_HTTP_PORT' '8080')"
    "LEAN_BIND_ADDRESS=$(Setting 'LEAN_BIND_ADDRESS' '127.0.0.1')"
    "LEAN_ALLOWED_HOSTS=$(Setting 'LEAN_ALLOWED_HOSTS' 'localhost,127.0.0.1')"
    "LEAN_ENVIRONMENT=$(Setting 'LEAN_ENVIRONMENT' 'production')"
    "LEAN_DB_PASSWORD=$(Random-Hex 32)"
    "LEAN_SECRET_KEY=$(Random-Hex 32)"
    "LEAN_OTA_AGENT_TOKEN=$(if ($EnableOta) { Random-Hex 32 })"
    "LEAN_ADMIN_PASSWORD=Lean-$(Random-Hex 24)"
  ) -join "`n"
  $stream = [IO.File]::Open($EnvFile, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
  $written = $false
  try {
    # 非 Windows 先把空文件收紧为仅当前用户可读写，再写入密钥。
    if ($env:OS -ne 'Windows_NT') {
      & chmod 600 $EnvFile
      if ($LASTEXITCODE -ne 0) { throw '无法将新配置文件权限设为 600，已删除未写入密钥的文件。' }
    }
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($content + "`n"); $stream.Write($bytes, 0, $bytes.Length)
    $written = $true
  } finally {
    $stream.Dispose()
    # 只删除本次 CreateNew 新建且未写完的文件，避免下次运行误以为配置已存在。
    if (-not $written) { Remove-Item -LiteralPath $EnvFile -ErrorAction SilentlyContinue }
  }
  if ($env:OS -eq 'Windows_NT') {
    $acl = Get-Acl $EnvFile
    $acl.SetAccessRuleProtection($true, $false)
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $acl.SetAccessRule([Security.AccessControl.FileSystemAccessRule]::new($identity, 'FullControl', 'Allow'))
    Set-Acl $EnvFile $acl
  }
}
if ($EnableOta -and [IO.File]::ReadAllText($EnvFile) -notmatch '(?m)^LEAN_OTA_AGENT_TOKEN=.+') {
  [IO.File]::AppendAllText($EnvFile, "`nLEAN_OTA_AGENT_TOKEN=$(Random-Hex 32)`n", [Text.UTF8Encoding]::new($false))
}
$compose = @('compose', '--env-file', $EnvFile, '-f', (Join-Path $PSScriptRoot 'docker-compose.yml'))
if ($EnableOta) {
  $contents = [IO.File]::ReadAllText($EnvFile) -replace '(?m)^LEAN_OTA_MODE=.*\r?\n?', ''
  [IO.File]::WriteAllText($EnvFile, $contents.TrimEnd() + "`nLEAN_OTA_MODE=host`n", [Text.UTF8Encoding]::new($false))
}
Invoke-Docker @compose config --quiet
if ($Release) {
  Invoke-ReleaseInstall (Join-Path $PSScriptRoot 'scripts/release_install.py') --root $PSScriptRoot --config $EnvFile
} elseif (-not $SkipBuild) { Invoke-Docker @compose build app }
Invoke-Docker @compose up -d --no-build --wait --wait-timeout 180
if ($EnableOta) {
  Invoke-OtaPython (Join-Path $PSScriptRoot 'scripts/ota_service.py') install --mode docker --root $PSScriptRoot --config $EnvFile
}
Invoke-NetworkCheck (Join-Path $PSScriptRoot 'scripts/network_check.py') --config $EnvFile
Write-Host "安装完成。管理员 admin 的初始密码位于 $EnvFile 的 LEAN_ADMIN_PASSWORD，完成安装向导修改密码后该值即失效。"
Write-Host '访问配置端口的 /erp/，首次登录自动进入快速安装向导，完成后使用新密码登录即可开单。'
Write-Host "忘记管理员密码时重设：docker compose --env-file $EnvFile -f $(Join-Path $PSScriptRoot 'docker-compose.yml') exec app python /opt/erp/container_runtime.py manage changepassword admin"
