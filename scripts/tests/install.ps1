$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$testFile = Join-Path ([IO.Path]::GetTempPath()) ("lean-install-test-" + [Guid]::NewGuid().ToString() + '.env')
$workDir = Join-Path ([IO.Path]::GetTempPath()) ("lean-install-cwd-" + [Guid]::NewGuid().ToString())
$packageDir = Join-Path ([IO.Path]::GetTempPath()) ("lean-install-package-" + [Guid]::NewGuid().ToString())
$relativeName = "lean-relative-" + [Guid]::NewGuid().ToString() + '.env'
$originalPython = $env:PYTHON
$global:DockerCalls = [Collections.Generic.List[string]]::new()
$global:PythonCalls = [Collections.Generic.List[string]]::new()
$global:PythonCheckExit = 0
function global:docker {
  $global:DockerCalls.Add(($args -join ' '))
  $global:LASTEXITCODE = 0
}
# 发布包用例用函数代替宿主机 Python：版本预检返回 PythonCheckExit，release_install.py 模拟失败。
function global:lean-test-python {
  $global:PythonCalls.Add(($args -join ' '))
  if ($args[0] -eq '-c') { $global:LASTEXITCODE = $global:PythonCheckExit }
  elseif ("$($args[0])" -like '*release_install.py') { $global:LASTEXITCODE = 7 }
  else { $global:LASTEXITCODE = 0 }
}
try {
  & (Join-Path $root 'install.ps1') -EnvFile $testFile -SkipBuild -NoOta
  $before = [IO.File]::ReadAllText($testFile)
  if ($before -notmatch 'LEAN_IMAGE=atm-erp-lean:local') { throw '镜像配置未写入配置文件' }
  if ($before -notmatch 'LEAN_ENVIRONMENT=production') { throw '全新安装必须默认启用发布环境的登录限流' }
  if ($before -notmatch 'LEAN_ADMIN_PASSWORD=Lean-[a-f0-9]{48}') { throw '缺少初始管理员密码' }
  if ($env:OS -ne 'Windows_NT' -and "$(& ls -l $testFile)" -notmatch '^-rw-------') { throw '非 Windows 新配置文件未限制为 600' }
  if ($global:DockerCalls.Exists([Predicate[string]]{ param($value) $value -match ' build app$' })) { throw '指定 SkipBuild 后仍执行了镜像构建' }
  & (Join-Path $root 'install.ps1') -EnvFile $testFile -NoOta
  if ($before -ne [IO.File]::ReadAllText($testFile)) { throw '重复安装覆盖了已有配置或密钥' }
  if (-not $global:DockerCalls.Exists([Predicate[string]]{ param($value) $value -match ' build app$' })) { throw '未下发镜像构建命令' }
  if (-not $global:DockerCalls.Exists([Predicate[string]]{ param($value) $value -match ' up -d --no-build --wait --wait-timeout 180$' })) { throw '未下发带健康检查的启动命令' }

  # 相对 -EnvFile 按 PowerShell 当前位置解析；进程工作目录不随 Set-Location 改变，不能把配置写到别处。
  New-Item -ItemType Directory -Path $workDir | Out-Null
  Push-Location $workDir
  try { & (Join-Path $root 'install.ps1') -EnvFile $relativeName -SkipBuild -NoOta } finally { Pop-Location }
  if (-not (Test-Path -LiteralPath (Join-Path $workDir $relativeName))) { throw '相对配置路径未按当前位置创建' }
  foreach ($call in $global:DockerCalls) { if ($call.Contains("--env-file $relativeName ")) { throw 'Compose 未使用解析后的绝对配置路径' } }

  # 发布包：缺少 Python 3.11 时在生成配置和调用 Docker 前停止。
  New-Item -ItemType Directory -Path $packageDir | Out-Null
  Copy-Item (Join-Path $root 'install.ps1') $packageDir
  [IO.File]::WriteAllText((Join-Path $packageDir 'INSTALL-MANIFEST.json'), '{}')
  $packageEnv = Join-Path $packageDir '.env'
  $env:PYTHON = 'lean-test-python'
  $global:DockerCalls.Clear()
  $global:PythonCheckExit = 1
  $failure = ''
  try { & (Join-Path $packageDir 'install.ps1') -EnvFile $packageEnv -NoOta } catch { $failure = $_.Exception.Message }
  if ($failure -notmatch 'Python 3.11') { throw "发布包缺少 Python 时未给出明确错误：$failure" }
  if (Test-Path -LiteralPath $packageEnv) { throw '发布包缺少 Python 时仍生成了配置文件' }
  if ($global:DockerCalls.Count -ne 0) { throw '发布包缺少 Python 时仍调用了 Docker' }

  # 发布包：新配置留空 LEAN_IMAGE（沿用 Compose 内置摘要），release_install 失败单独报错且不启动容器。
  $global:PythonCheckExit = 0
  $failure = ''
  try { & (Join-Path $packageDir 'install.ps1') -EnvFile $packageEnv -NoOta } catch { $failure = $_.Exception.Message }
  if ($failure -notmatch '发布镜像校验或导入失败') { throw "release_install 失败未单独报错：$failure" }
  $released = [IO.File]::ReadAllText($packageEnv)
  if ($released -notmatch '(?m)^LEAN_IMAGE=$' -or $released -match 'atm-erp-lean:local') { throw '发布包新配置不得写入本地构建镜像' }
  if (-not $global:PythonCalls.Exists([Predicate[string]]{ param($value) $value -like '*release_install.py --root*' })) { throw '发布包未调用 release_install.py' }
  if ($global:DockerCalls.Exists([Predicate[string]]{ param($value) $value -match ' up -d | build app$' })) { throw 'release_install 失败后仍构建或启动了容器' }
  # 上面的用例故意模拟 Python/release_install 以非零退出码失败；全部断言通过后清零，
  # 否则 CI 的 pwsh 步骤会以残留的 $LASTEXITCODE 判为失败。断言失败仍由 throw 终止。
  $global:LASTEXITCODE = 0
  Write-Host 'PowerShell 安装器命令下发、配置路径、发布包镜像与配置保留校验通过。'
} finally {
  $env:PYTHON = $originalPython
  Remove-Item $testFile -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $workDir, $packageDir -Recurse -Force -ErrorAction SilentlyContinue
  # 修复前相对路径会落到进程工作目录；文件名带随机后缀，只清理本用例可能遗留的文件。
  Remove-Item -LiteralPath (Join-Path ([Environment]::CurrentDirectory) $relativeName) -ErrorAction SilentlyContinue
  Remove-Item Function:global:docker -ErrorAction SilentlyContinue
  Remove-Item Function:global:lean-test-python -ErrorAction SilentlyContinue
}
