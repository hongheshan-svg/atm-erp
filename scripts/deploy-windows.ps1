#Requires -RunAsAdministrator
<#
.SYNOPSIS
    ERP系统 Windows Server 一键部署脚本
.DESCRIPTION
    自动完成环境检查、配置生成、服务部署、数据库初始化
.NOTES
    需要以管理员身份运行
#>

param(
    [switch]$SkipBuild,
    [switch]$SkipInit,
    [string]$Environment = "prod"
)

# 颜色输出函数
function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host " $Message" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[√] $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "[×] $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[!] $Message" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host "[i] $Message" -ForegroundColor Gray
}

# 生成随机密码
function New-RandomPassword {
    param([int]$Length = 32)
    $chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    $password = -join ((1..$Length) | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
    return $password
}

# 生成Django密钥
function New-DjangoSecretKey {
    $chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
    $key = -join ((1..50) | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
    return $key
}

# 主脚本开始
Clear-Host
Write-Host ""
Write-Host "  ╔═══════════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "  ║                                                       ║" -ForegroundColor Magenta
Write-Host "  ║     ERP系统 Windows Server 一键部署工具 v1.0          ║" -ForegroundColor Magenta
Write-Host "  ║                                                       ║" -ForegroundColor Magenta
Write-Host "  ╚═══════════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Info "项目目录: $ProjectRoot"
Write-Info "部署环境: $Environment"
Write-Host ""

# ============================================
# 步骤1: 环境检查
# ============================================
Write-Step "步骤 1/6: 环境检查"

# 检查Docker
Write-Info "检查 Docker..."
try {
    $dockerVersion = docker --version 2>$null
    if ($dockerVersion) {
        Write-Success "Docker 已安装: $dockerVersion"
    } else {
        throw "Docker未安装"
    }
} catch {
    Write-Error "Docker 未安装或未启动"
    Write-Warning "请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
}

# 检查Docker Compose
Write-Info "检查 Docker Compose..."
try {
    $composeVersion = docker-compose --version 2>$null
    if ($composeVersion) {
        Write-Success "Docker Compose 已安装: $composeVersion"
    } else {
        throw "Docker Compose未安装"
    }
} catch {
    Write-Error "Docker Compose 未安装"
    exit 1
}

# 检查Docker是否运行
Write-Info "检查 Docker 服务状态..."
try {
    docker info 2>$null | Out-Null
    Write-Success "Docker 服务运行正常"
} catch {
    Write-Error "Docker 服务未运行，请启动 Docker Desktop"
    exit 1
}

# 检查端口占用
Write-Info "检查端口占用..."
$portsToCheck = @(80, 443, 8000, 5432, 6379)
$portsInUse = @()
foreach ($port in $portsToCheck) {
    $connection = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connection) {
        $portsInUse += $port
    }
}
if ($portsInUse.Count -gt 0) {
    Write-Warning "以下端口已被占用: $($portsInUse -join ', ')"
    $continue = Read-Host "是否继续部署? (y/n)"
    if ($continue -ne 'y') {
        exit 1
    }
} else {
    Write-Success "所需端口均可用"
}

# ============================================
# 步骤2: 生成配置文件
# ============================================
Write-Step "步骤 2/6: 生成配置文件"

$envFile = "$ProjectRoot\backend\.env"
$envExampleFile = "$ProjectRoot\backend\.env.prod.example"

if (Test-Path $envFile) {
    Write-Warning ".env 文件已存在"
    $overwrite = Read-Host "是否覆盖现有配置? (y/n)"
    if ($overwrite -ne 'y') {
        Write-Info "保留现有配置文件"
    } else {
        $generateNew = $true
    }
} else {
    $generateNew = $true
}

if ($generateNew) {
    Write-Info "生成新的配置文件..."
    
    # 生成密码和密钥
    $dbPassword = New-RandomPassword -Length 24
    $secretKey = New-DjangoSecretKey
    $serverIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" } | Select-Object -First 1).IPAddress
    
    # 创建.env文件内容
    $envContent = @"
# Database
POSTGRES_DB=erp_db
POSTGRES_USER=erp_user
POSTGRES_PASSWORD=$dbPassword
DATABASE_URL=postgres://erp_user:$dbPassword@db:5432/erp_db

# Django
SECRET_KEY=$secretKey
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,$serverIP

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0

# Elasticsearch
ELASTICSEARCH_URL=http://elasticsearch:9200

# Email (配置你的邮件服务器)
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@example.com

# 时区
TZ=Asia/Shanghai
"@
    
    $envContent | Out-File -FilePath $envFile -Encoding UTF8
    Write-Success "配置文件已生成: $envFile"
    Write-Info "数据库密码: $dbPassword"
    Write-Warning "请妥善保管以上密码！"
}

# ============================================
# 步骤3: 构建Docker镜像
# ============================================
Write-Step "步骤 3/6: 构建Docker镜像"

if ($SkipBuild) {
    Write-Warning "跳过镜像构建"
} else {
    Write-Info "开始构建镜像，这可能需要几分钟..."
    
    # 选择配置文件
    if ($Environment -eq "prod") {
        $composeFile = "docker-compose.prod.yml"
    } elseif (Test-Path "$ProjectRoot\docker-compose.windows.yml") {
        $composeFile = "docker-compose.windows.yml"
    } else {
        $composeFile = "docker-compose.yml"
    }
    
    Write-Info "使用配置文件: $composeFile"
    
    docker-compose -f $composeFile build
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "镜像构建完成"
    } else {
        Write-Error "镜像构建失败"
        exit 1
    }
}

# ============================================
# 步骤4: 启动服务
# ============================================
Write-Step "步骤 4/6: 启动服务"

Write-Info "启动所有服务..."

# 选择配置文件
if ($Environment -eq "prod") {
    $composeFile = "docker-compose.prod.yml"
} elseif (Test-Path "$ProjectRoot\docker-compose.windows.yml") {
    $composeFile = "docker-compose.windows.yml"
} else {
    $composeFile = "docker-compose.yml"
}

docker-compose -f $composeFile up -d

if ($LASTEXITCODE -eq 0) {
    Write-Success "服务启动成功"
} else {
    Write-Error "服务启动失败"
    exit 1
}

# 等待服务就绪
Write-Info "等待服务就绪..."
$maxRetries = 30
$retryCount = 0
$servicesReady = $false

while (-not $servicesReady -and $retryCount -lt $maxRetries) {
    Start-Sleep -Seconds 2
    $retryCount++
    Write-Host "." -NoNewline
    
    # 检查后端服务健康状态
    try {
        $health = docker inspect --format='{{.State.Health.Status}}' erp_backend 2>$null
        if ($health -eq "healthy") {
            $servicesReady = $true
        }
    } catch {
        # 继续等待
    }
}

Write-Host ""
if ($servicesReady) {
    Write-Success "所有服务已就绪"
} else {
    Write-Warning "服务启动超时，继续执行..."
}

# ============================================
# 步骤5: 初始化数据库
# ============================================
Write-Step "步骤 5/6: 初始化数据库"

if ($SkipInit) {
    Write-Warning "跳过数据库初始化"
} else {
    Write-Info "执行数据库迁移..."
    docker-compose -f $composeFile exec -T backend python manage.py migrate --noinput
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "数据库迁移完成"
    } else {
        Write-Error "数据库迁移失败"
    }
    
    Write-Info "创建管理员账号..."
    $createAdmin = @"
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Admin user created: admin / admin123')
else:
    print('Admin user already exists')
"@
    
    $createAdmin | docker-compose -f $composeFile exec -T backend python manage.py shell
    Write-Success "管理员账号: admin / admin123"
    
    Write-Info "初始化基础数据..."
    docker-compose -f $composeFile exec -T backend python manage.py init_workflows 2>$null
    docker-compose -f $composeFile exec -T backend python manage.py init_dashboard_widgets 2>$null
    Write-Success "基础数据初始化完成"
    
    Write-Info "收集静态文件..."
    docker-compose -f $composeFile exec -T backend python manage.py collectstatic --noinput 2>$null
    Write-Success "静态文件收集完成"
}

# ============================================
# 步骤6: 部署完成
# ============================================
Write-Step "步骤 6/6: 部署完成"

# 获取服务状态
Write-Info "服务状态:"
docker-compose -f $composeFile ps

$serverIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.PrefixOrigin -ne "WellKnown" } | Select-Object -First 1).IPAddress

Write-Host ""
Write-Host "  ╔═══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║                                                       ║" -ForegroundColor Green
Write-Host "  ║              部署成功！                               ║" -ForegroundColor Green
Write-Host "  ║                                                       ║" -ForegroundColor Green
Write-Host "  ╚═══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  访问地址:" -ForegroundColor White
Write-Host "  ├─ 本地访问:   http://localhost" -ForegroundColor Gray
Write-Host "  ├─ 局域网访问: http://$serverIP" -ForegroundColor Gray
Write-Host "  └─ 后台管理:   http://localhost/admin" -ForegroundColor Gray
Write-Host ""
Write-Host "  默认账号:" -ForegroundColor White
Write-Host "  ├─ 用户名: admin" -ForegroundColor Gray
Write-Host "  └─ 密码:   admin123" -ForegroundColor Gray
Write-Host ""
Write-Host "  常用命令:" -ForegroundColor White
Write-Host "  ├─ 查看日志:   docker-compose -f $composeFile logs -f" -ForegroundColor Gray
Write-Host "  ├─ 重启服务:   docker-compose -f $composeFile restart" -ForegroundColor Gray
Write-Host "  └─ 停止服务:   docker-compose -f $composeFile down" -ForegroundColor Gray
Write-Host ""
Write-Warning "请立即修改默认密码！"
Write-Host ""
