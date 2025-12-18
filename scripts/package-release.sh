#!/bin/bash
#
# ERP系统打包发布脚本
# 用法: bash scripts/package-release.sh [版本号]
#

set -e

VERSION=${1:-"1.0.0"}
DATE=$(date +%Y%m%d)
PACKAGE_NAME="erp-system-v${VERSION}-${DATE}"

# 颜色定义
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║     ERP系统打包工具（Ubuntu原生部署版）               ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 获取项目目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo -e "${CYAN}[i] 版本: $VERSION${NC}"
echo -e "${CYAN}[i] 项目目录: $PROJECT_DIR${NC}"

# 创建临时目录
TEMP_DIR="/tmp/$PACKAGE_NAME"
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

echo -e "${CYAN}[i] 复制项目文件...${NC}"

# 复制必要文件
cp -r backend "$TEMP_DIR/"
cp -r frontend "$TEMP_DIR/"
cp -r nginx "$TEMP_DIR/"
cp -r scripts "$TEMP_DIR/"
cp -r docs "$TEMP_DIR/" 2>/dev/null || mkdir -p "$TEMP_DIR/docs"

# 复制配置文件
cp .gitignore "$TEMP_DIR/"

# 复制文档
cp README.md "$TEMP_DIR/"
cp UBUNTU-NATIVE-DEPLOYMENT.md "$TEMP_DIR/" 2>/dev/null || true
cp QUICK-DEPLOY-CARD.md "$TEMP_DIR/" 2>/dev/null || true
cp QUICK-START-GUIDE.md "$TEMP_DIR/" 2>/dev/null || true
cp SYSTEM-ARCHITECTURE.md "$TEMP_DIR/" 2>/dev/null || true
cp SECURITY-PERFORMANCE-GUIDE.md "$TEMP_DIR/" 2>/dev/null || true

# 复制安装脚本
cp install.sh "$TEMP_DIR/"

# 复制小程序（可选）
cp -r miniprogram "$TEMP_DIR/" 2>/dev/null || true

# 创建必要的空目录
mkdir -p "$TEMP_DIR/logs"
mkdir -p "$TEMP_DIR/uploads"
mkdir -p "$TEMP_DIR/backups"

# 清理不需要的文件
echo -e "${CYAN}[i] 清理临时文件...${NC}"

# 删除Python缓存
find "$TEMP_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$TEMP_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$TEMP_DIR" -type f -name "*.pyo" -delete 2>/dev/null || true

# 删除Node模块
rm -rf "$TEMP_DIR/frontend/node_modules" 2>/dev/null || true
rm -rf "$TEMP_DIR/frontend/dist" 2>/dev/null || true

# 删除.git目录
rm -rf "$TEMP_DIR/.git" 2>/dev/null || true

# 删除.env文件（保留示例）
rm -f "$TEMP_DIR/backend/.env" 2>/dev/null || true

# 删除数据库文件
rm -f "$TEMP_DIR/backend/db.sqlite3" 2>/dev/null || true
rm -f "$TEMP_DIR/backend/celerybeat-schedule" 2>/dev/null || true

# 删除静态文件（会在部署时重新生成）
rm -rf "$TEMP_DIR/backend/staticfiles" 2>/dev/null || true

# 删除媒体文件
rm -rf "$TEMP_DIR/backend/media/*" 2>/dev/null || true

# 设置脚本执行权限
chmod +x "$TEMP_DIR/install.sh"
chmod +x "$TEMP_DIR/scripts/"*.sh 2>/dev/null || true

# 创建版本文件
cat > "$TEMP_DIR/VERSION" << EOF
版本: $VERSION
构建日期: $(date '+%Y-%m-%d %H:%M:%S')
部署方式: Ubuntu原生部署（无Docker）
支持系统: Ubuntu 20.04/22.04/24.04 LTS
EOF

# 打包
echo -e "${CYAN}[i] 创建压缩包...${NC}"

cd /tmp

# 创建tar.gz包
tar -czvf "${PACKAGE_NAME}.tar.gz" "$PACKAGE_NAME"

# 创建zip包（可选）
if command -v zip &> /dev/null; then
    zip -r "${PACKAGE_NAME}.zip" "$PACKAGE_NAME"
fi

# 移动到项目目录
mv "${PACKAGE_NAME}.tar.gz" "$PROJECT_DIR/" 2>/dev/null || true
mv "${PACKAGE_NAME}.zip" "$PROJECT_DIR/" 2>/dev/null || true

# 清理临时目录
rm -rf "$TEMP_DIR"

echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║     打包完成！                                        ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${CYAN}生成的文件:${NC}"
ls -lh "$PROJECT_DIR/${PACKAGE_NAME}"* 2>/dev/null

echo
echo -e "${CYAN}部署说明:${NC}"
echo "1. 将压缩包上传到Ubuntu服务器"
echo "   scp ${PACKAGE_NAME}.tar.gz user@server:/tmp/"
echo ""
echo "2. 登录服务器并解压"
echo "   ssh user@server"
echo "   cd /tmp && tar -xzvf ${PACKAGE_NAME}.tar.gz"
echo ""
echo "3. 运行一键安装"
echo "   cd ${PACKAGE_NAME}"
echo "   sudo bash install.sh"
