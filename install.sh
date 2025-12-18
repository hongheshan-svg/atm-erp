#!/bin/bash
#
# ERP系统一键安装脚本
# Ubuntu原生部署（无Docker）
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║                                                       ║"
echo "║     ERP系统 一键安装程序                              ║"
echo "║     Ubuntu 原生部署（无Docker）                       ║"
echo "║                                                       ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检测操作系统
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    elif [ -f /etc/redhat-release ]; then
        OS="centos"
    else
        OS=$(uname -s)
    fi
    
    echo -e "${CYAN}[i] 检测到操作系统: $OS $VER${NC}"
}

# 检查root权限
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}[✗] 请使用 sudo 运行此脚本${NC}"
        echo "用法: sudo bash $0"
        exit 1
    fi
}

# 主函数
main() {
    detect_os
    check_root
    
    case "$OS" in
        ubuntu|debian)
            echo -e "${GREEN}[✓] 开始Ubuntu原生部署...${NC}"
            bash "$SCRIPT_DIR/scripts/deploy-native-ubuntu.sh"
            ;;
        *)
            echo -e "${RED}[✗] 不支持的操作系统: $OS${NC}"
            echo -e "${YELLOW}[i] 本系统仅支持 Ubuntu/Debian 原生部署${NC}"
            echo -e "${YELLOW}[i] 支持的系统: Ubuntu 20.04/22.04/24.04, Debian 11/12${NC}"
            exit 1
            ;;
    esac
}

main "$@"
