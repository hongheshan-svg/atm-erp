#Requires -Version 5
# ATM-ERP 一键安装脚本 (Docker, Windows PowerShell)
# 用法: .\install.ps1 [-Tag <版本>] [-LocalSrc <目录>] [-Help]
#
# 环境变量钩子:
#   ERP_DIR=<目录>  指定工作目录（默认 %USERPROFILE%\atm-erp）
#
# 参数:
#   -Tag      镜像版本 (默认 latest，如 0.2.0)
#   -LocalSrc 从本地目录复制 docker-compose.yml / .env.example（离线部署/测试）
#   -Help     显示此帮助
[CmdletBinding()]
param(
    [string]$Tag = "latest",
    [string]$LocalSrc = "",
    [switch]$Help
)

$ErrorActionPreference = "Stop"

$Repo    = "hongheshan-svg/atm-erp"
$RelBase = "https://github.com/$Repo/releases"
$RawBase = "https://raw.githubusercontent.com/$Repo/main"

function Info($m)  { Write-Host "[i] $m" -ForegroundColor Cyan }
function Ok($m)    { Write-Host "[OK] $m" -ForegroundColor Green }
function Warn($m)  { Write-Host "[!] $m" -ForegroundColor Yellow }
function Err($m)   { Write-Host "[x] $m" -ForegroundColor Red }

if ($Help) {
    Write-Host @"
ATM-ERP 一键安装 (Docker, Windows PowerShell)
用法: .\install.ps1 [选项]

选项:
  -Tag <版本>       指定镜像版本 (默认 latest，如 0.2.0)
  -LocalSrc <目录>  从本地目录复制 docker-compose.yml/.env.example（离线部署）
  -Help             显示此帮助

环境变量:
  ERP_DIR=<目录>    指定工作目录（默认 %USERPROFILE%\atm-erp）

示例:
  .\install.ps1
  .\install.ps1 -Tag 0.2.0
  .\install.ps1 -LocalSrc C:\deploy-files
"@
    exit 0
}

# ---------------------------------------------------------------------------
# 1. 确保 Docker 已安装并运行
# ---------------------------------------------------------------------------
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Err "未检测到 Docker Desktop。请安装后重试："
    Err "  https://www.docker.com/products/docker-desktop/"
    exit 1
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Err "Docker 未运行，请启动 Docker Desktop 后重试。"
    exit 1
}
Ok "Docker 就绪"

# ---------------------------------------------------------------------------
# 2. 工作目录
# ---------------------------------------------------------------------------
if ($env:ERP_DIR) {
    $WorkDir = $env:ERP_DIR
} else {
    $WorkDir = Join-Path $env:USERPROFILE "atm-erp"
}
$SslDir = Join-Path $WorkDir "docker\ssl"
New-Item -ItemType Directory -Force -Path $SslDir | Out-Null
Set-Location $WorkDir
Info "工作目录: $WorkDir"

# ---------------------------------------------------------------------------
# 3. 生成自签名 SSL 证书（nginx 启动必需；浏览器会显示安全警告，可忽略）
#    Windows 通常没有 openssl，使用 docker 容器生成
# ---------------------------------------------------------------------------
$CertFile = Join-Path $SslDir "server.crt"
$KeyFile  = Join-Path $SslDir "server.key"

if (-not (Test-Path $CertFile) -or -not (Test-Path $KeyFile)) {
    Info "生成自签名 SSL 证书（通过 Docker 容器）..."
    # alpine/openssl 是 Docker Hub 上的官方轻量镜像，专为此类工具场景设计。
    # Docker Desktop for Windows 可接受绝对 Windows 路径作为 bind-mount 源。
    docker run --rm -v "${SslDir}:/certs" alpine/openssl `
        req -x509 -nodes -newkey rsa:2048 -days 3650 `
        -keyout /certs/server.key `
        -out    /certs/server.crt `
        -subj   "/C=CN/ST=Shanghai/L=Shanghai/O=ATM-ERP/CN=localhost"
    if ($LASTEXITCODE -ne 0) {
        Warn "SSL 证书生成失败（HTTPS 可能不可用），继续安装..."
    } else {
        Ok "SSL 证书已生成（自签名，3650 天有效期）"
    }
} else {
    Info "SSL 证书已存在，跳过生成"
}

# ---------------------------------------------------------------------------
# 4. 获取部署文件（LocalSrc 优先，然后 Release，最后 raw main 兜底）
# ---------------------------------------------------------------------------
function Fetch([string]$Rel, [string]$Dest) {
    # LocalSrc 钩子：离线/本地源优先
    if ($LocalSrc) {
        $SrcFile = Join-Path $LocalSrc $Rel
        if (Test-Path $SrcFile) {
            Info "本地源: 复制 $Rel 从 $LocalSrc"
            Copy-Item -Path $SrcFile -Destination $Dest -Force
            return
        } else {
            Warn "LocalSrc 中未找到 $Rel，回退到网络下载"
        }
    }

    # 从 GitHub Release 下载，失败则回退 raw main
    if ($Tag -eq "latest") {
        $Url = "$RelBase/latest/download/$Rel"
    } else {
        $TagClean = $Tag.TrimStart('v')
        $Url = "$RelBase/download/v$TagClean/$Rel"
    }

    try {
        Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $Dest
    } catch {
        Warn "Release 资产不存在，回退到源码 main: $Rel"
        Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/$Rel" -OutFile $Dest
    }
}

Info "获取部署文件 (tag=$Tag)..."
Fetch "docker-compose.yml" "docker-compose.yml"
Fetch ".env.example" ".env.example"

# ---------------------------------------------------------------------------
# 5. 随机值工具（使用加密 RNG，不用 Get-Random）
# ---------------------------------------------------------------------------
function RandHex([int]$ByteCount) {
    $bytes = New-Object 'System.Byte[]' $ByteCount
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    ($bytes | ForEach-Object { $_.ToString('x2') }) -join ''
}

function RandAlnum([int]$Length = 16) {
    # 纯字母数字密码，避免 shell 特殊字符干扰 .env 解析
    # 使用 ASCII 整数范围构建字符集：0-9 (48-57), A-Z (65-90), a-z (97-122)
    $charInts = (48..57) + (65..90) + (97..122)
    $chars = $charInts | ForEach-Object { [char]$_ }
    $bytes = New-Object 'System.Byte[]' ($Length * 2)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    $result = New-Object 'System.Text.StringBuilder'
    foreach ($b in $bytes) {
        if ($result.Length -ge $Length) { break }
        $idx = $b % $chars.Count
        [void]$result.Append($chars[$idx])
    }
    $result.ToString()
}

# ---------------------------------------------------------------------------
# 6. 获取宿主机 IP（用于 ALLOWED_HOSTS / CORS）
# ---------------------------------------------------------------------------
try {
    $HostIP = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex `
        (Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | Select-Object -First 1).InterfaceIndex `
        | Select-Object -ExpandProperty IPAddress -First 1)
} catch {
    $HostIP = "127.0.0.1"
}
if (-not $HostIP) { $HostIP = "127.0.0.1" }

# IMAGE_TAG: 去掉前导 v（"v0.2.0" → "0.2.0"；"local"/"latest" 保持原样）
$ImageTagVal = $Tag.TrimStart('v')

# ---------------------------------------------------------------------------
# 7. 生成 .env（首次安装）
# ---------------------------------------------------------------------------
if (-not (Test-Path ".env")) {
    Info "生成 .env..."
    $AdminPassword = RandAlnum 16
    $EnvContent = @"
DEBUG=False
SECRET_KEY=$(RandHex 32)
ALLOWED_HOSTS=localhost,127.0.0.1,$HostIP
DB_NAME=erp_db
DB_USER=erp_user
DB_PASSWORD=$(RandHex 16)
CORS_ALLOWED_ORIGINS=http://localhost,http://127.0.0.1,http://$HostIP
CSRF_TRUSTED_ORIGINS=http://localhost,http://127.0.0.1,http://$HostIP
FRONTEND_URL=http://localhost
IMAGE_TAG=$ImageTagVal
HTTP_PORT=80
HTTPS_PORT=443
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$AdminPassword
SEED_DEMO_DATA=0
"@
    # 用 ASCII 编码写入，避免 BOM 影响 Linux 容器读取
    [System.IO.File]::WriteAllText((Join-Path $WorkDir ".env"), $EnvContent, [System.Text.Encoding]::ASCII)
    Ok ".env 已生成（ADMIN_PASSWORD 见下方横幅，请妥善保存）"
} else {
    Warn ".env 已存在，跳过生成（沿用现有配置）"
}

# 读取最终密码（无论是新生成还是已有）
$AdminPassword = (Get-Content ".env" | Where-Object { $_ -match '^ADMIN_PASSWORD=' } |
    ForEach-Object { $_ -replace '^ADMIN_PASSWORD=', '' } | Select-Object -First 1)

# ---------------------------------------------------------------------------
# 8. 拉取镜像（非致命：本地/离线标签拉取会报错，但 up -d 仍可用已有镜像）
# ---------------------------------------------------------------------------
Info "拉取镜像 (tag=$ImageTagVal)..."
docker compose pull
if ($LASTEXITCODE -ne 0) {
    Warn "镜像拉取失败（可能是本地/离线标签），继续使用本地已有镜像..."
}

# ---------------------------------------------------------------------------
# 9. 启动服务
# ---------------------------------------------------------------------------
Info "启动服务..."
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Err "容器启动失败，请查看日志: docker compose logs -f"
    exit 1
}
Ok "容器已启动"

# ---------------------------------------------------------------------------
# 10. 等待后端 API 就绪（首次启动含迁移+种子数据，最长约 12 分钟）
# ---------------------------------------------------------------------------
Info "等待后端就绪（首次启动需要迁移数据库，可能需要数分钟...）"
$HealthUrl  = "http://localhost/api/v1/health/"
$Ready      = $false
$MaxAttempts = 240   # 240 × 3s = 720s ≈ 12 分钟

for ($i = 1; $i -le $MaxAttempts; $i++) {
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $HealthUrl -TimeoutSec 3 | Out-Null
        $Ready = $true
        break
    } catch {
        # 每 10 次（约 30 秒）打印一次进度
        if ($i % 10 -eq 0) {
            Info "等待中... ($i/$MaxAttempts 次，已等待 $($i * 3)s)，可用 'docker compose logs -f backend' 查看进度"
        }
        Start-Sleep -Seconds 3
    }
}

if ($Ready) {
    Ok "后端 API 已就绪"
} else {
    Warn "健康检查超时，服务可能仍在初始化中"
    Warn "请稍后运行: Invoke-WebRequest $HealthUrl"
    Warn "或查看日志: cd $WorkDir; docker compose logs -f backend"
}

# ---------------------------------------------------------------------------
# 11. 确定访问地址
# ---------------------------------------------------------------------------
$HttpPortVal = (Get-Content ".env" | Where-Object { $_ -match '^HTTP_PORT=' } |
    ForEach-Object { $_ -replace '^HTTP_PORT=', '' } | Select-Object -First 1)
if (-not $HttpPortVal) { $HttpPortVal = "80" }

if ($HttpPortVal -eq "80") {
    $AccessUrl   = "http://localhost/erp/"
    $AccessUrlIp = "http://$HostIP/erp/"
} else {
    $AccessUrl   = "http://localhost:$HttpPortVal/erp/"
    $AccessUrlIp = "http://${HostIP}:$HttpPortVal/erp/"
}

# ---------------------------------------------------------------------------
# 12. 成功横幅
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================================"
Write-Host "  ATM-ERP 安装完成！"
Write-Host "------------------------------------------------------------"
Write-Host "  访问地址 (本机)  : $AccessUrl"
Write-Host "  访问地址 (局域网): $AccessUrlIp"
Write-Host "  管理员账号       : admin"
Write-Host "  管理员密码       : $AdminPassword"
Write-Host "  工作目录         : $WorkDir"
Write-Host "------------------------------------------------------------"
Write-Host "  常用命令:"
Write-Host "    cd $WorkDir"
Write-Host "    docker compose ps              # 查看容器状态"
Write-Host "    docker compose logs -f backend # 查看后端日志"
Write-Host "    docker compose down            # 停止并移除容器"
Write-Host "    docker compose down -v         # 停止并清除所有数据"
Write-Host "============================================================"
