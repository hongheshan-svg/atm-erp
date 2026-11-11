param(
  [Parameter(Mandatory=$true)][ValidateSet('configure','install','start','stop','check','reset-password')][string]$Action,
  [string]$Config = (Join-Path $PSScriptRoot 'native-config.json'),
  [string]$User = '',
  [switch]$NoOta
)
$ErrorActionPreference = 'Stop'
# 与 install-native.sh 透传参数一致：-User 对应 reset-password 的 --user，-NoOta 对应 start 的 --no-ota。
$arguments = @((Join-Path $PSScriptRoot 'scripts/native_install.py'), $Action, '--config', $Config)
if ($User) { $arguments += @('--user', $User) }
if ($NoOta) { $arguments += '--no-ota' }
if ($env:PYTHON) { & $env:PYTHON @arguments }
else { & py -3.11 @arguments }
if ($LASTEXITCODE -ne 0) { throw "原生安装器执行失败，退出码 $LASTEXITCODE。" }
