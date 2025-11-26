#!/bin/bash
# 创建Windows原生部署包
# 无需Docker，可直接在Windows上安装

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RELEASE_DIR="$SCRIPT_DIR/windows-native"
BUILD_DIR="$RELEASE_DIR/build"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PACKAGE_NAME="ERP-Windows-Native-$TIMESTAMP"
OUTPUT_DIR="$RELEASE_DIR/output"

echo "======================================="
echo "  创建Windows原生部署包"
echo "======================================="
echo ""
echo "项目根目录: $PROJECT_ROOT"
echo "构建目录: $BUILD_DIR"
echo "输出目录: $OUTPUT_DIR"
echo ""

# 清理旧的构建
if [ -d "$BUILD_DIR" ]; then
    echo "清理旧的构建目录..."
    rm -rf "$BUILD_DIR"
fi

# 创建构建目录
mkdir -p "$BUILD_DIR/$PACKAGE_NAME"/{backend,frontend,docs}
mkdir -p "$OUTPUT_DIR"

# 1. 复制后端代码
echo ""
echo "1. 打包后端代码..."
rsync -av \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.pytest_cache' \
    --exclude='celerybeat-schedule' \
    --exclude='media/*' \
    --exclude='staticfiles/*' \
    --exclude='logs/*' \
    --exclude='.env' \
    "$PROJECT_ROOT/backend/" \
    "$BUILD_DIR/$PACKAGE_NAME/backend/"

# 创建后端必要的空目录
mkdir -p "$BUILD_DIR/$PACKAGE_NAME/backend"/{media,staticfiles,logs}

echo "✓ 后端代码已打包"

# 2. 打包前端（使用预构建或从Docker复制）
echo ""
echo "2. 打包前端..."

# 尝试从Docker容器复制构建好的文件
if docker ps | grep -q erp_frontend; then
    echo "从Docker容器复制前端构建文件..."
    docker cp erp_frontend:/app/dist "$BUILD_DIR/$PACKAGE_NAME/frontend_temp" 2>/dev/null || true
    
    if [ -f "$BUILD_DIR/$PACKAGE_NAME/frontend_temp/index.html" ]; then
        mv "$BUILD_DIR/$PACKAGE_NAME/frontend_temp"/* "$BUILD_DIR/$PACKAGE_NAME/frontend/"
        rm -rf "$BUILD_DIR/$PACKAGE_NAME/frontend_temp"
        echo "✓ 前端文件已从容器复制"
    fi
fi

# 如果上面失败，尝试使用本地dist
if [ ! -f "$BUILD_DIR/$PACKAGE_NAME/frontend/index.html" ]; then
    if [ -d "$PROJECT_ROOT/frontend/dist" ] && [ -f "$PROJECT_ROOT/frontend/dist/index.html" ]; then
        echo "使用本地构建的前端文件..."
        cp -r "$PROJECT_ROOT/frontend/dist"/* "$BUILD_DIR/$PACKAGE_NAME/frontend/"
        echo "✓ 前端文件已复制"
    else
        echo "⚠ 警告: 前端构建文件未找到"
        echo "请先构建前端: cd frontend && npm run build"
        echo "或确保frontend Docker容器正在运行"
        
        # 创建占位文件
        cat > "$BUILD_DIR/$PACKAGE_NAME/frontend/index.html" << 'EOF'
<!DOCTYPE html>
<html>
<head><title>ERP System</title></head>
<body>
<h1>请替换此文件为实际的前端构建文件</h1>
<p>将前端构建后的dist目录内容复制到此处</p>
</body>
</html>
EOF
        echo "已创建占位index.html"
    fi
fi

# 3. 复制Nginx配置
echo ""
echo "3. 复制Nginx配置..."
if [ -f "$PROJECT_ROOT/nginx/nginx.conf" ]; then
    cp "$PROJECT_ROOT/nginx/nginx.conf" "$BUILD_DIR/$PACKAGE_NAME/nginx.conf"
    echo "✓ Nginx配置已复制"
else
    # 创建默认配置
    cat > "$BUILD_DIR/$PACKAGE_NAME/nginx.conf" << 'EOF'
worker_processes 1;

events {
    worker_connections 1024;
}

http {
    include mime.types;
    default_type application/octet-stream;
    sendfile on;
    keepalive_timeout 65;

    server {
        listen 80;
        server_name localhost;
        client_max_body_size 100M;

        # 前端
        location / {
            root C:/ERP-System/frontend;
            index index.html;
            try_files $uri $uri/ /index.html;
        }

        # 静态文件
        location /static/ {
            alias C:/ERP-System/staticfiles/;
        }

        # 媒体文件
        location /media/ {
            alias C:/ERP-System/media/;
        }

        # API
        location /api/ {
            proxy_pass http://127.0.0.1:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Admin
        location /admin/ {
            proxy_pass http://127.0.0.1:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
EOF
    echo "✓ 创建了默认Nginx配置"
fi

# 4. 复制安装脚本和文档
echo ""
echo "4. 复制安装脚本和文档..."
cp "$RELEASE_DIR/install.ps1" "$BUILD_DIR/$PACKAGE_NAME/"
cp "$RELEASE_DIR/README.md" "$BUILD_DIR/$PACKAGE_NAME/"

# 复制项目文档
if [ -f "$PROJECT_ROOT/README.md" ]; then
    cp "$PROJECT_ROOT/README.md" "$BUILD_DIR/$PACKAGE_NAME/docs/项目说明.md"
fi
if [ -f "$PROJECT_ROOT/SYSTEM-ARCHITECTURE.md" ]; then
    cp "$PROJECT_ROOT/SYSTEM-ARCHITECTURE.md" "$BUILD_DIR/$PACKAGE_NAME/docs/系统架构.md"
fi

echo "✓ 文档已复制"

# 5. 创建快速开始指南
cat > "$BUILD_DIR/$PACKAGE_NAME/快速开始.txt" << 'EOF'
========================================
  ERP系统 Windows原生部署包
  快速开始指南
========================================

系统要求:
---------
- Windows Server 2016+ 或 Windows 10/11 Pro
- 8GB+ 内存
- 50GB+ 磁盘空间
- 管理员权限

安装步骤:
---------
1. 右键点击PowerShell，选择"以管理员身份运行"

2. 允许脚本执行:
   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

3. 进入解压目录:
   cd C:\path\to\ERP-Windows-Native-xxxxx

4. 运行安装脚本:
   .\install.ps1

5. 等待安装完成（约10-20分钟）

6. 按提示创建管理员账号

7. 访问系统:
   http://localhost

详细说明请查看: README.md

常见问题:
---------
Q: 安装失败怎么办？
A: 查看日志文件，确保有管理员权限和网络连接

Q: 如何卸载？
A: 运行: .\install.ps1 -Uninstall

Q: 如何修改安装路径？
A: 运行: .\install.ps1 -InstallPath "D:\MyERP"

技术支持:
---------
查看README.md了解更多详细信息

========================================
EOF

# 6. 创建版本信息
cat > "$BUILD_DIR/$PACKAGE_NAME/VERSION.txt" << EOF
ERP系统 Windows原生部署包
================================

版本: 1.0.0
构建时间: $(date "+%Y-%m-%d %H:%M:%S")
构建主机: $(hostname)
包名称: $PACKAGE_NAME

部署方式: Windows原生（无需Docker）

包含组件:
---------
- Django 4.x (Python后端)
- Vue 3.x (前端)
- PostgreSQL 13+ (数据库)
- Redis 6+ (缓存)
- Nginx (Web服务器)

安装内容:
---------
- 自动安装所有依赖软件
- 配置Windows服务
- 配置防火墙规则
- 生成管理脚本

系统要求:
---------
- Windows Server 2016/2019/2022
- Windows 10/11 Pro
- 8GB+ RAM
- 50GB+ 磁盘空间

================================
EOF

# 7. 压缩打包
echo ""
echo "5. 压缩打包..."
cd "$BUILD_DIR"
zip -r "$OUTPUT_DIR/$PACKAGE_NAME.zip" "$PACKAGE_NAME" > /dev/null 2>&1 || \
tar -czf "$OUTPUT_DIR/$PACKAGE_NAME.tar.gz" "$PACKAGE_NAME"

# 检查哪个打包成功了
if [ -f "$OUTPUT_DIR/$PACKAGE_NAME.zip" ]; then
    PACKAGE_FILE="$OUTPUT_DIR/$PACKAGE_NAME.zip"
    PACKAGE_SIZE=$(du -sh "$PACKAGE_FILE" | cut -f1)
elif [ -f "$OUTPUT_DIR/$PACKAGE_NAME.tar.gz" ]; then
    PACKAGE_FILE="$OUTPUT_DIR/$PACKAGE_NAME.tar.gz"
    PACKAGE_SIZE=$(du -sh "$PACKAGE_FILE" | cut -f1)
else
    echo "✗ 打包失败"
    exit 1
fi

# 清理构建目录
rm -rf "$BUILD_DIR"

echo ""
echo "======================================="
echo "  ✓ 打包完成！"
echo "======================================="
echo ""
echo "部署包位置: $PACKAGE_FILE"
echo "部署包大小: $PACKAGE_SIZE"
echo ""
echo "Windows服务器部署步骤:"
echo "----------------------"
echo "1. 将压缩包传输到Windows服务器"
echo "2. 解压到任意目录"
echo "3. 右键PowerShell→以管理员身份运行"
echo "4. cd到解压目录"
echo "5. 执行: .\\install.ps1"
echo "6. 等待安装完成"
echo "7. 访问: http://服务器IP"
echo ""
echo "详细说明:"
echo "---------"
echo "- 解压后阅读 README.md"
echo "- 解压后阅读 快速开始.txt"
echo "- 安装会自动安装所有依赖"
echo "- 支持自定义安装路径和数据库密码"
echo ""
echo "传输方式建议:"
echo "-------------"
echo "- FTP/SFTP"
echo "- 网络共享"
echo "- U盘/移动硬盘"
echo "- 云存储（阿里云OSS、百度网盘等）"
echo ""

