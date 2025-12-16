#!/bin/bash
#
# ERP系统服务管理脚本
# 用法: ./manage-service.sh [命令]
#

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# 获取项目目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# 检测docker compose命令
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

show_menu() {
    clear
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║           ERP系统 服务管理工具                        ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo "  [1] 启动所有服务"
    echo "  [2] 停止所有服务"
    echo "  [3] 重启所有服务"
    echo "  [4] 查看服务状态"
    echo "  [5] 查看实时日志"
    echo "  [6] 备份数据库"
    echo "  [7] 恢复数据库"
    echo "  [8] 进入后端Shell"
    echo "  [9] 执行数据库迁移"
    echo "  [10] 重建并启动服务"
    echo "  [11] 清理未使用的镜像"
    echo "  [0] 退出"
    echo
}

start_services() {
    echo -e "${CYAN}[i] 启动所有服务...${NC}"
    $COMPOSE_CMD up -d
    echo -e "${GREEN}[✓] 服务已启动${NC}"
}

stop_services() {
    echo -e "${CYAN}[i] 停止所有服务...${NC}"
    $COMPOSE_CMD down
    echo -e "${GREEN}[✓] 服务已停止${NC}"
}

restart_services() {
    echo -e "${CYAN}[i] 重启所有服务...${NC}"
    $COMPOSE_CMD restart
    echo -e "${GREEN}[✓] 服务已重启${NC}"
}

show_status() {
    echo -e "${CYAN}[i] 服务状态:${NC}"
    echo
    $COMPOSE_CMD ps
}

show_logs() {
    echo -e "${CYAN}[i] 显示实时日志 (按 Ctrl+C 退出)${NC}"
    echo
    $COMPOSE_CMD logs -f --tail=100
}

backup_database() {
    BACKUP_DIR="$PROJECT_DIR/backups"
    mkdir -p "$BACKUP_DIR"
    BACKUP_FILE="$BACKUP_DIR/db_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    echo -e "${CYAN}[i] 备份数据库到: $BACKUP_FILE${NC}"
    $COMPOSE_CMD exec -T db pg_dump -U erp_user erp_db > "$BACKUP_FILE"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[✓] 备份完成: $BACKUP_FILE${NC}"
        echo -e "${CYAN}[i] 文件大小: $(du -h "$BACKUP_FILE" | cut -f1)${NC}"
    else
        echo -e "${RED}[✗] 备份失败${NC}"
    fi
}

restore_database() {
    BACKUP_DIR="$PROJECT_DIR/backups"
    
    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A $BACKUP_DIR 2>/dev/null)" ]; then
        echo -e "${YELLOW}[!] 没有找到备份文件${NC}"
        return
    fi
    
    echo -e "${CYAN}可用的备份文件:${NC}"
    ls -la "$BACKUP_DIR"/*.sql 2>/dev/null
    echo
    read -p "请输入要恢复的备份文件名: " BACKUP_FILE
    
    if [ -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
        echo -e "${YELLOW}[!] 警告: 这将覆盖当前数据库！${NC}"
        read -p "确定要继续吗? (yes/no): " CONFIRM
        
        if [ "$CONFIRM" = "yes" ]; then
            echo -e "${CYAN}[i] 正在恢复数据库...${NC}"
            cat "$BACKUP_DIR/$BACKUP_FILE" | $COMPOSE_CMD exec -T db psql -U erp_user erp_db
            echo -e "${GREEN}[✓] 数据库恢复完成${NC}"
        else
            echo -e "${CYAN}[i] 已取消${NC}"
        fi
    else
        echo -e "${RED}[✗] 文件不存在${NC}"
    fi
}

enter_shell() {
    echo -e "${CYAN}[i] 进入Django Shell (输入 exit() 退出)${NC}"
    $COMPOSE_CMD exec backend python manage.py shell
}

run_migrate() {
    echo -e "${CYAN}[i] 执行数据库迁移...${NC}"
    $COMPOSE_CMD exec backend python manage.py migrate
    echo -e "${GREEN}[✓] 迁移完成${NC}"
}

rebuild_services() {
    echo -e "${CYAN}[i] 重建并启动服务...${NC}"
    $COMPOSE_CMD down
    $COMPOSE_CMD build --no-cache
    $COMPOSE_CMD up -d
    echo -e "${GREEN}[✓] 服务已重建并启动${NC}"
}

cleanup_images() {
    echo -e "${CYAN}[i] 清理未使用的Docker镜像...${NC}"
    docker image prune -f
    docker volume prune -f
    echo -e "${GREEN}[✓] 清理完成${NC}"
}

# 命令行模式
if [ $# -gt 0 ]; then
    case "$1" in
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        backup)
            backup_database
            ;;
        migrate)
            run_migrate
            ;;
        shell)
            enter_shell
            ;;
        rebuild)
            rebuild_services
            ;;
        *)
            echo "用法: $0 {start|stop|restart|status|logs|backup|migrate|shell|rebuild}"
            exit 1
            ;;
    esac
    exit 0
fi

# 交互模式
while true; do
    show_menu
    read -p "请选择操作 [0-11]: " choice
    
    case $choice in
        1) start_services ;;
        2) stop_services ;;
        3) restart_services ;;
        4) show_status ;;
        5) show_logs ;;
        6) backup_database ;;
        7) restore_database ;;
        8) enter_shell ;;
        9) run_migrate ;;
        10) rebuild_services ;;
        11) cleanup_images ;;
        0) echo "再见！"; exit 0 ;;
        *) echo -e "${RED}无效选择${NC}" ;;
    esac
    
    echo
    read -p "按回车键继续..."
done
