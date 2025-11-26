#!/bin/bash
# 创建Windows Docker部署包
# 需要在Windows上安装Docker Desktop

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RELEASE_DIR="$SCRIPT_DIR/windows-docker"
BUILD_DIR="$RELEASE_DIR/build"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PACKAGE_NAME="ERP-Windows-Docker-$TIMESTAMP"
OUTPUT_DIR="$RELEASE_DIR/output"

echo "======================================="
echo "  创建Windows Docker部署包"
echo "======================================="
echo ""

# 清理和创建目录
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/$PACKAGE_NAME"
mkdir -p "$OUTPUT_DIR"

# 1. 复制整个项目（排除不需要的）
echo "1. 复制项目文件..."
rsync -av \
    --exclude='frontend/node_modules' \
    --exclude='frontend/dist' \
    --exclude='backend/venv' \
    --exclude='backend/__pycache__' \
    --exclude='backend/media' \
    --exclude='backend/staticfiles' \
    --exclude='backend/logs' \
    --exclude='.git' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    "$PROJECT_ROOT/" \
    "$BUILD_DIR/$PACKAGE_NAME/"

echo "✓ 项目文件已复制"

# 2. 创建.env.example
echo ""
echo "2. 创建环境配置模板..."
cat > "$BUILD_DIR/$PACKAGE_NAME/.env.example" << 'EOF'
# 数据库配置
POSTGRES_DB=erp_db
POSTGRES_USER=erp_user
POSTGRES_PASSWORD=请修改为安全密码

# Redis配置  
REDIS_PASSWORD=请修改为安全密码

# Django配置
SECRET_KEY=请修改为随机密钥
DEBUG=False
ALLOWED_HOSTS=your-domain.com,localhost,127.0.0.1,your-server-ip

# 数据库连接（Docker内部）
DATABASE_URL=postgresql://erp_user:请修改密码@db:5432/erp_db
REDIS_URL=redis://:请修改密码@redis:6379/0

# 邮件配置（可选）
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email@example.com
EMAIL_HOST_PASSWORD=your_email_password
DEFAULT_FROM_EMAIL=your_email@example.com

# 跨域配置
CORS_ALLOWED_ORIGINS=http://localhost,http://your-domain.com
EOF

echo "✓ 环境配置模板已创建"

# 3. 创建部署脚本
echo ""
echo "3. 创建部署脚本..."

# Windows批处理脚本
cat > "$BUILD_DIR/$PACKAGE_NAME/部署.bat" << 'EOF'
@echo off
chcp 65001 >nul
echo ========================================
echo   ERP系统 Docker部署
echo ========================================
echo.

echo 1. 检查Docker是否安装...
docker --version >nul 2>&1
if errorlevel 1 (
    echo Docker未安装！
    echo 请先安装Docker Desktop for Windows
    echo 下载地址: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
echo ✓ Docker已安装
echo.

echo 2. 检查.env配置文件...
if not exist .env (
    echo 未找到.env文件，正在从.env.example创建...
    copy .env.example .env
    echo.
    echo ⚠ 重要: 请编辑.env文件修改默认密码！
    echo.
    pause
)
echo ✓ 配置文件存在
echo.

echo 3. 启动Docker服务...
docker-compose up -d
echo.

echo 4. 等待服务启动（30秒）...
timeout /t 30 /nobreak >nul
echo.

echo 5. 执行数据库迁移...
docker-compose exec -T backend python manage.py migrate
echo.

echo 6. 收集静态文件...
docker-compose exec -T backend python manage.py collectstatic --noinput
echo.

echo 7. 创建超级管理员...
docker-compose exec backend python manage.py createsuperuser
echo.

echo ========================================
echo   ✓ 部署完成！
echo ========================================
echo.
echo 访问地址:
echo   前端: http://localhost
echo   API:  http://localhost/api
echo   后台: http://localhost/admin
echo.
echo 管理命令:
echo   启动: docker-compose start
echo   停止: docker-compose stop
echo   重启: docker-compose restart
echo   日志: docker-compose logs -f
echo.
pause
EOF

# 启动脚本
cat > "$BUILD_DIR/$PACKAGE_NAME/启动.bat" << 'EOF'
@echo off
echo 启动ERP系统...
docker-compose start
docker-compose ps
echo.
echo 系统已启动！
echo 访问: http://localhost
pause
EOF

# 停止脚本
cat > "$BUILD_DIR/$PACKAGE_NAME/停止.bat" << 'EOF'
@echo off
echo 停止ERP系统...
docker-compose stop
echo.
echo 系统已停止！
pause
EOF

# 重启脚本
cat > "$BUILD_DIR/$PACKAGE_NAME/重启.bat" << 'EOF'
@echo off
echo 重启ERP系统...
docker-compose restart
docker-compose ps
echo.
echo 系统已重启！
pause
EOF

# 查看日志
cat > "$BUILD_DIR/$PACKAGE_NAME/查看日志.bat" << 'EOF'
@echo off
echo 查看系统日志（按Ctrl+C退出）...
docker-compose logs -f
EOF

# 备份脚本
cat > "$BUILD_DIR/$PACKAGE_NAME/备份数据.bat" << 'EOF'
@echo off
echo 备份ERP系统数据...
set TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%

if not exist backups mkdir backups

echo 备份数据库...
docker-compose exec -T db pg_dump -U erp_user erp_db > backups\db_%TIMESTAMP%.sql
echo ✓ 数据库已备份

echo 备份上传文件...
docker cp erp_backend:/app/media backups\media_%TIMESTAMP%
echo ✓ 上传文件已备份

echo.
echo 备份完成！
echo 数据库: backups\db_%TIMESTAMP%.sql
echo 文件: backups\media_%TIMESTAMP%
pause
EOF

echo "✓ 部署脚本已创建"

# 4. 创建README
echo ""
echo "4. 创建README..."
cat > "$BUILD_DIR/$PACKAGE_NAME/README.txt" << 'EOF'
========================================
  ERP系统 Windows Docker部署包
========================================

系统要求:
---------
- Windows Server 2016+ 或 Windows 10/11 Pro
- 8GB+ 内存
- 100GB+ 磁盘空间
- Docker Desktop for Windows

快速开始:
---------
1. 安装Docker Desktop
   下载: https://www.docker.com/products/docker-desktop

2. 双击运行"部署.bat"

3. 按提示创建管理员账号

4. 访问 http://localhost

管理命令:
---------
- 启动.bat      : 启动系统
- 停止.bat      : 停止系统
- 重启.bat      : 重启系统
- 查看日志.bat  : 查看日志
- 备份数据.bat  : 备份数据

或使用命令行:
-------------
docker-compose up -d      # 启动
docker-compose stop       # 停止
docker-compose restart    # 重启
docker-compose logs -f    # 查看日志
docker-compose ps         # 查看状态

配置说明:
---------
安装前请编辑.env文件，修改:
- 数据库密码
- Redis密码  
- Django SECRET_KEY
- ALLOWED_HOSTS

技术支持:
---------
详细文档请查看docs目录

========================================
EOF

echo "✓ README已创建"

# 5. 压缩打包
echo ""
echo "5. 压缩打包..."
cd "$BUILD_DIR"

if command -v zip &> /dev/null; then
    zip -r "$OUTPUT_DIR/$PACKAGE_NAME.zip" "$PACKAGE_NAME" > /dev/null
    PACKAGE_FILE="$OUTPUT_DIR/$PACKAGE_NAME.zip"
else
    tar -czf "$OUTPUT_DIR/$PACKAGE_NAME.tar.gz" "$PACKAGE_NAME"
    PACKAGE_FILE="$OUTPUT_DIR/$PACKAGE_NAME.tar.gz"
fi

PACKAGE_SIZE=$(du -sh "$PACKAGE_FILE" | cut -f1)

# 清理
rm -rf "$BUILD_DIR"

echo ""
echo "======================================="
echo "  ✓ 打包完成！"
echo "======================================="
echo ""
echo "部署包: $PACKAGE_FILE"
echo "大小: $PACKAGE_SIZE"
echo ""
echo "Windows部署步骤:"
echo "----------------"
echo "1. 安装Docker Desktop for Windows"
echo "2. 解压部署包"
echo "3. 编辑.env文件（修改密码）"
echo "4. 双击运行"部署.bat""
echo "5. 访问 http://localhost"
echo ""

