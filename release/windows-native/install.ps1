# ERP系统 Windows一键安装脚本
# 自动安装所有依赖和配置服务

#Requires -RunAsAdministrator

param(
    [string]$InstallPath = "C:\ERP-System",
    [string]$PostgresPassword = "ERP@2024!Secure",
    [string]$DjangoSecretKey = "",
    [switch]$SkipDependencies = $false,
    [switch]$Uninstall = $false
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# 颜色输出函数
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Write-Step {
    param([string]$Message)
    Write-ColorOutput "`n=== $Message ===" "Cyan"
}

function Write-Success {
    param([string]$Message)
    Write-ColorOutput "✓ $Message" "Green"
}

function Write-Error {
    param([string]$Message)
    Write-ColorOutput "✗ $Message" "Red"
}

function Write-Warning {
    param([string]$Message)
    Write-ColorOutput "! $Message" "Yellow"
}

# 检查管理员权限
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "请以管理员身份运行此脚本"
    exit 1
}

# 卸载功能
if ($Uninstall) {
    Write-Step "开始卸载ERP系统"
    
    # 停止并删除Windows服务
    $services = @("ERPBackend", "ERPRedis", "ERPPostgreSQL", "ERPNginx")
    foreach ($svc in $services) {
        if (Get-Service $svc -ErrorAction SilentlyContinue) {
            Stop-Service $svc -Force -ErrorAction SilentlyContinue
            sc.exe delete $svc
            Write-Success "已删除服务: $svc"
        }
    }
    
    # 询问是否删除安装目录
    $confirm = Read-Host "是否删除安装目录 $InstallPath？(y/N)"
    if ($confirm -eq "y" -or $confirm -eq "Y") {
        Remove-Item -Path $InstallPath -Recurse -Force -ErrorAction SilentlyContinue
        Write-Success "已删除安装目录"
    }
    
    Write-Success "卸载完成"
    exit 0
}

# 显示欢迎信息
Clear-Host
Write-ColorOutput @"

╔═══════════════════════════════════════════════════════╗
║                                                       ║
║          ERP系统 Windows 一键安装程序                 ║
║                                                       ║
║          版本: 1.0.0                                  ║
║          支持: Windows Server 2016+, Win10/11 Pro    ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝

"@ "Cyan"

Write-ColorOutput "安装路径: $InstallPath" "Yellow"
Write-ColorOutput "开始时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" "Yellow"
Write-ColorOutput ""

# 检测Chocolatey
function Install-Chocolatey {
    Write-Step "检查 Chocolatey 包管理器"
    
    if (!(Get-Command choco -ErrorAction SilentlyContinue)) {
        Write-Warning "Chocolatey 未安装，正在安装..."
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))
        
        # 刷新环境变量
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        Write-Success "Chocolatey 安装完成"
    } else {
        Write-Success "Chocolatey 已安装"
    }
}

# 安装依赖软件
function Install-Dependencies {
    if ($SkipDependencies) {
        Write-Warning "跳过依赖安装"
        return
    }
    
    Write-Step "安装系统依赖"
    
    # Python 3.9
    if (!(Get-Command python -ErrorAction SilentlyContinue)) {
        Write-ColorOutput "安装 Python 3.9..." "Yellow"
        choco install python39 -y
        Write-Success "Python 已安装"
    } else {
        Write-Success "Python 已存在"
    }
    
    # PostgreSQL
    if (!(Get-Command psql -ErrorAction SilentlyContinue)) {
        Write-ColorOutput "安装 PostgreSQL..." "Yellow"
        choco install postgresql13 --params "/Password:$PostgresPassword" -y
        Write-Success "PostgreSQL 已安装"
    } else {
        Write-Success "PostgreSQL 已存在"
    }
    
    # Redis (使用Memurai - Redis的Windows版本)
    if (!(Test-Path "C:\Program Files\Memurai\memurai.exe")) {
        Write-ColorOutput "安装 Memurai (Redis for Windows)..." "Yellow"
        choco install memurai-developer -y
        Write-Success "Memurai 已安装"
    } else {
        Write-Success "Redis/Memurai 已存在"
    }
    
    # Node.js (用于构建前端，可选)
    if (!(Get-Command node -ErrorAction SilentlyContinue)) {
        Write-ColorOutput "安装 Node.js..." "Yellow"
        choco install nodejs-lts -y
        Write-Success "Node.js 已安装"
    } else {
        Write-Success "Node.js 已存在"
    }
    
    # Nginx
    if (!(Test-Path "C:\nginx\nginx.exe")) {
        Write-ColorOutput "安装 Nginx..." "Yellow"
        choco install nginx -y
        Write-Success "Nginx 已安装"
    } else {
        Write-Success "Nginx 已存在"
    }
    
    # NSSM (用于创建Windows服务)
    if (!(Get-Command nssm -ErrorAction SilentlyContinue)) {
        Write-ColorOutput "安装 NSSM..." "Yellow"
        choco install nssm -y
        Write-Success "NSSM 已安装"
    } else {
        Write-Success "NSSM 已存在"
    }
    
    # 刷新环境变量
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

# 创建安装目录
function Setup-Directories {
    Write-Step "创建安装目录"
    
    $dirs = @(
        $InstallPath,
        "$InstallPath\backend",
        "$InstallPath\frontend",
        "$InstallPath\logs",
        "$InstallPath\backups",
        "$InstallPath\media",
        "$InstallPath\staticfiles"
    )
    
    foreach ($dir in $dirs) {
        if (!(Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Write-Success "创建目录: $dir"
        }
    }
}

# 复制应用文件
function Copy-Application {
    Write-Step "复制应用文件"
    
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    
    # 复制后端
    if (Test-Path "$scriptDir\backend") {
        Write-ColorOutput "复制后端文件..." "Yellow"
        Copy-Item -Path "$scriptDir\backend\*" -Destination "$InstallPath\backend\" -Recurse -Force
        Write-Success "后端文件已复制"
    } else {
        Write-Error "未找到后端文件目录"
        exit 1
    }
    
    # 复制前端
    if (Test-Path "$scriptDir\frontend") {
        Write-ColorOutput "复制前端文件..." "Yellow"
        Copy-Item -Path "$scriptDir\frontend\*" -Destination "$InstallPath\frontend\" -Recurse -Force
        Write-Success "前端文件已复制"
    } else {
        Write-Warning "未找到前端文件目录"
    }
    
    # 复制Nginx配置
    if (Test-Path "$scriptDir\nginx.conf") {
        Copy-Item -Path "$scriptDir\nginx.conf" -Destination "C:\nginx\conf\nginx.conf" -Force
        Write-Success "Nginx配置已复制"
    }
}

# 配置数据库
function Setup-Database {
    Write-Step "配置数据库"
    
    # 等待PostgreSQL服务启动
    Start-Sleep -Seconds 5
    
    # 创建数据库和用户
    $env:PGPASSWORD = $PostgresPassword
    
    try {
        # 创建数据库
        & psql -U postgres -c "CREATE DATABASE erp_db;" 2>$null
        & psql -U postgres -c "CREATE USER erp_user WITH PASSWORD '$PostgresPassword';" 2>$null
        & psql -U postgres -c "ALTER ROLE erp_user SET client_encoding TO 'utf8';" 2>$null
        & psql -U postgres -c "ALTER ROLE erp_user SET default_transaction_isolation TO 'read committed';" 2>$null
        & psql -U postgres -c "ALTER ROLE erp_user SET timezone TO 'Asia/Shanghai';" 2>$null
        & psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE erp_db TO erp_user;" 2>$null
        
        Write-Success "数据库配置完成"
    } catch {
        Write-Warning "数据库可能已存在或配置失败: $_"
    }
}

# 安装Python依赖
function Install-PythonPackages {
    Write-Step "安装Python依赖包"
    
    Set-Location "$InstallPath\backend"
    
    # 创建虚拟环境
    if (!(Test-Path "venv")) {
        python -m venv venv
        Write-Success "Python虚拟环境已创建"
    }
    
    # 激活虚拟环境并安装依赖
    & .\venv\Scripts\Activate.ps1
    
    if (Test-Path "requirements.txt") {
        Write-ColorOutput "安装Python包..." "Yellow"
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        Write-Success "Python依赖包已安装"
    }
}

# 生成配置文件
function Generate-Config {
    Write-Step "生成配置文件"
    
    # 生成Django SECRET_KEY
    if ([string]::IsNullOrEmpty($DjangoSecretKey)) {
        $DjangoSecretKey = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 50 | ForEach-Object {[char]$_})
    }
    
    # 创建.env文件
    $envContent = @"
# Django配置
SECRET_KEY=$DjangoSecretKey
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,*

# 数据库配置
DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=erp_db
DATABASE_USER=erp_user
DATABASE_PASSWORD=$PostgresPassword
DATABASE_HOST=localhost
DATABASE_PORT=5432

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 静态文件和媒体文件
STATIC_ROOT=$InstallPath\staticfiles
MEDIA_ROOT=$InstallPath\media
STATIC_URL=/static/
MEDIA_URL=/media/

# 时区和语言
TIME_ZONE=Asia/Shanghai
LANGUAGE_CODE=zh-hans
"@
    
    $envContent | Out-File -FilePath "$InstallPath\backend\.env" -Encoding UTF8
    Write-Success "配置文件已生成"
}

# 初始化Django
function Initialize-Django {
    Write-Step "初始化Django应用"
    
    Set-Location "$InstallPath\backend"
    & .\venv\Scripts\Activate.ps1
    
    # 执行数据库迁移
    Write-ColorOutput "执行数据库迁移..." "Yellow"
    python manage.py migrate
    Write-Success "数据库迁移完成"
    
    # 收集静态文件
    Write-ColorOutput "收集静态文件..." "Yellow"
    python manage.py collectstatic --noinput
    Write-Success "静态文件收集完成"
    
    # 创建超级用户（跳过交互）
    Write-ColorOutput ""
    Write-ColorOutput "请设置管理员账号:" "Yellow"
    python manage.py createsuperuser
}

# 配置Windows服务
function Setup-WindowsServices {
    Write-Step "配置Windows服务"
    
    # 配置Django后端服务
    Write-ColorOutput "配置Django服务..." "Yellow"
    nssm install ERPBackend "$InstallPath\backend\venv\Scripts\python.exe"
    nssm set ERPBackend AppParameters "$InstallPath\backend\manage.py runserver 0.0.0.0:8000"
    nssm set ERPBackend AppDirectory "$InstallPath\backend"
    nssm set ERPBackend DisplayName "ERP系统后端服务"
    nssm set ERPBackend Description "ERP系统Django后端服务"
    nssm set ERPBackend Start SERVICE_AUTO_START
    nssm set ERPBackend AppStdout "$InstallPath\logs\backend.log"
    nssm set ERPBackend AppStderr "$InstallPath\logs\backend-error.log"
    Write-Success "Django服务已配置"
    
    # 配置Nginx服务
    Write-ColorOutput "配置Nginx服务..." "Yellow"
    nssm install ERPNginx "C:\nginx\nginx.exe"
    nssm set ERPNginx AppDirectory "C:\nginx"
    nssm set ERPNginx DisplayName "ERP系统Web服务器"
    nssm set ERPNginx Description "ERP系统Nginx Web服务器"
    nssm set ERPNginx Start SERVICE_AUTO_START
    Write-Success "Nginx服务已配置"
    
    # 启动服务
    Write-Step "启动服务"
    Start-Service ERPBackend
    Start-Service ERPNginx
    Write-Success "所有服务已启动"
}

# 配置防火墙
function Configure-Firewall {
    Write-Step "配置防火墙规则"
    
    # HTTP
    New-NetFirewallRule -DisplayName "ERP-HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow -ErrorAction SilentlyContinue
    Write-Success "已开放HTTP端口 (80)"
    
    # Backend API
    New-NetFirewallRule -DisplayName "ERP-Backend" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -ErrorAction SilentlyContinue
    Write-Success "已开放后端端口 (8000)"
}

# 创建快捷方式
function Create-Shortcuts {
    Write-Step "创建管理脚本"
    
    # 启动脚本
    $startScript = @"
@echo off
echo 启动ERP系统服务...
net start ERPBackend
net start ERPNginx
echo.
echo ERP系统已启动!
echo 访问地址: http://localhost
pause
"@
    $startScript | Out-File -FilePath "$InstallPath\启动服务.bat" -Encoding Default
    
    # 停止脚本
    $stopScript = @"
@echo off
echo 停止ERP系统服务...
net stop ERPBackend
net stop ERPNginx
echo.
echo ERP系统已停止!
pause
"@
    $stopScript | Out-File -FilePath "$InstallPath\停止服务.bat" -Encoding Default
    
    # 重启脚本
    $restartScript = @"
@echo off
echo 重启ERP系统服务...
net stop ERPBackend
net stop ERPNginx
timeout /t 2 >nul
net start ERPBackend
net start ERPNginx
echo.
echo ERP系统已重启!
pause
"@
    $restartScript | Out-File -FilePath "$InstallPath\重启服务.bat" -Encoding Default
    
    # 查看日志脚本
    $logsScript = @"
@echo off
echo 打开日志目录...
explorer "$InstallPath\logs"
"@
    $logsScript | Out-File -FilePath "$InstallPath\查看日志.bat" -Encoding Default
    
    Write-Success "管理脚本已创建"
}

# 主安装流程
try {
    Install-Chocolatey
    Install-Dependencies
    Setup-Directories
    Copy-Application
    Setup-Database
    Install-PythonPackages
    Generate-Config
    Initialize-Django
    Setup-WindowsServices
    Configure-Firewall
    Create-Shortcuts
    
    # 安装完成
    Write-ColorOutput ""
    Write-ColorOutput "╔═══════════════════════════════════════════════════════╗" "Green"
    Write-ColorOutput "║                                                       ║" "Green"
    Write-ColorOutput "║            ✓ 安装成功完成！                           ║" "Green"
    Write-ColorOutput "║                                                       ║" "Green"
    Write-ColorOutput "╚═══════════════════════════════════════════════════════╝" "Green"
    Write-ColorOutput ""
    Write-ColorOutput "安装路径: $InstallPath" "Cyan"
    Write-ColorOutput "访问地址: http://localhost" "Cyan"
    Write-ColorOutput "后台地址: http://localhost/admin" "Cyan"
    Write-ColorOutput ""
    Write-ColorOutput "管理命令:" "Yellow"
    Write-ColorOutput "  启动服务: $InstallPath\启动服务.bat" "White"
    Write-ColorOutput "  停止服务: $InstallPath\停止服务.bat" "White"
    Write-ColorOutput "  重启服务: $InstallPath\重启服务.bat" "White"
    Write-ColorOutput "  查看日志: $InstallPath\查看日志.bat" "White"
    Write-ColorOutput ""
    Write-ColorOutput "卸载命令:" "Yellow"
    Write-ColorOutput "  .\install.ps1 -Uninstall" "White"
    Write-ColorOutput ""
    
} catch {
    Write-Error "安装过程中出现错误: $_"
    Write-ColorOutput $_.ScriptStackTrace "Red"
    exit 1
}

