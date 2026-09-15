$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$testFile = Join-Path ([IO.Path]::GetTempPath()) ("lean-install-test-" + [Guid]::NewGuid().ToString() + '.env')
$global:DockerCalls = [Collections.Generic.List[string]]::new()
function global:docker {
  $global:DockerCalls.Add(($args -join ' '))
  $global:LASTEXITCODE = 0
}
try {
  & (Join-Path $root 'install.ps1') -EnvFile $testFile -SkipBuild -NoOta
  $before = [IO.File]::ReadAllText($testFile)
  if ($before -notmatch 'LEAN_IMAGE=atm-erp-lean:local') { throw '镜像配置未写入配置文件' }
  if ($before -notmatch 'LEAN_ENVIRONMENT=production') { throw '全新安装必须默认启用发布环境的登录限流' }
  if ($before -notmatch 'LEAN_ADMIN_PASSWORD=Lean-[a-f0-9]{48}') { throw '缺少初始管理员密码' }
  if ($global:DockerCalls.Exists([Predicate[string]]{ param($value) $value -match ' build app$' })) { throw '指定 SkipBuild 后仍执行了镜像构建' }
  & (Join-Path $root 'install.ps1') -EnvFile $testFile -NoOta
  if ($before -ne [IO.File]::ReadAllText($testFile)) { throw '重复安装覆盖了已有配置或密钥' }
  if (-not $global:DockerCalls.Exists([Predicate[string]]{ param($value) $value -match ' build app$' })) { throw '未下发镜像构建命令' }
  if (-not $global:DockerCalls.Exists([Predicate[string]]{ param($value) $value -match ' up -d --no-build --wait --wait-timeout 180$' })) { throw '未下发带健康检查的启动命令' }
  Write-Host 'PowerShell 安装器命令下发与配置保留校验通过。'
} finally {
  Remove-Item $testFile -ErrorAction SilentlyContinue
  Remove-Item Function:global:docker -ErrorAction SilentlyContinue
}
