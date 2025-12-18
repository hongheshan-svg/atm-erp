#!/bin/bash
#
# ERP系统一键安装脚本
# 自动检测操作系统并执行对应的部署脚本
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
    
    echo -e "${CYAN}[i] 检测到操作系统: $OS${NC}"
}

# 检查root权限
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}[✗] 请使用 sudo 运行此脚本${NC}"
        echo "用法: sudo bash $0"
        exit 1
    fi
}

# 显示部署方式选择
show_deploy_options() {
    echo
    echo -e "${CYAN}请选择部署方式:${NC}"
    echo "  [1] Docker部署（推荐，需要安装Docker）"
    echo "  [2] 原生部署（直接安装到系统，无需Docker）"
    echo
    read -p "请选择 [1/2]: " DEPLOY_MODE
}

# 主函数
main() {
    detect_os
    check_root
    
    # 检查命令行参数
    if [ "$1" = "--native" ] || [ "$1" = "-n" ]; then
        DEPLOY_MODE=2
    elif [ "$1" = "--docker" ] || [ "$1" = "-d" ]; then
        DEPLOY_MODE=1
    else
        show_deploy_options
    fi
    
    case "$OS" in
        ubuntu|debian)
            if [ "$DEPLOY_MODE" = "2" ]; then
                echo -e "${GREEN}[✓] 使用原生部署方式${NC}"
                bash "$SCRIPT_DIR/scripts/deploy-native-ubuntu.sh"
            else
                echo -e "${GREEN}[✓] 使用Docker部署方式${NC}"
                bash "$SCRIPT_DIR/scripts/deploy-ubuntu.sh"
            fi
            ;;
        centos|rhel|fedora|rocky|almalinux)
            echo -e "${YELLOW}[!] CentOS/RHEL 系统${NC}"
            if [ "$DEPLOY_MODE" = "2" ]; then
                echo -e "${RED}[✗] 原生部署暂不支持此系统，请使用Docker部署${NC}"
                exit 1
            fi
            bash "$SCRIPT_DIR/scripts/deploy-ubuntu.sh"
            ;;
        *)
            echo -e "${RED}[✗] 不支持的操作系统: $OS${NC}"
            echo -e "${YELLOW}[i] 请参考文档手动安装${NC}"
            exit 1
            ;;
    esac
}

main "$@"
