#!/bin/bash
#
# ERP系统原生部署服务管理脚本
# 用法: ./manage-native.sh [命令]
#

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

APP_DIR="/opt/erp"
VENV_DIR="/opt/erp/venv"
LOG_DIR="/var/log/erp"

SERVICES="erp-backend erp-celery erp-celery-beat"

show_menu() {
    clear
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║       ERP系统 服务管理工具（原生部署）                ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo "  [1] 启动所有服务"
    echo "  [2] 停止所有服务"
    echo "  [3] 重启所有服务"
    echo "  [4] 查看服务状态"
    echo "  [5] 查看应用日志"
    echo "  [6] 查看Nginx日志"
    echo "  [7] 备份数据库"
    echo "  [8] 恢复数据库"
    echo "  [9] 进入Django Shell"
    echo "  [10] 执行数据库迁移"
    echo "  [11] 重新收集静态文件"
    echo "  [12] 查看安装信息"
    echo "  [0] 退出"
    echo
}

start_services() {
    echo -e "${CYAN}[i] 启动所有服务...${NC}"
    for service in $SERVICES; do
        systemctl start $service
        echo -e "${GREEN}[✓] $service 已启动${NC}"
    done
    systemctl start nginx
    echo -e "${GREEN}[✓] nginx 已启动${NC}"
}

stop_services() {
    echo -e "${CYAN}[i] 停止所有服务...${NC}"
    for service in $SERVICES; do
        systemctl stop $service
        echo -e "${YELLOW}[!] $service 已停止${NC}"
    done
}

restart_services() {
    echo -e "${CYAN}[i] 重启所有服务...${NC}"
    for service in $SERVICES; do
        systemctl restart $service
        echo -e "${GREEN}[✓] $service 已重启${NC}"
    done
    systemctl restart nginx
    echo -e "${GREEN}[✓] nginx 已重启${NC}"
}

show_status() {
    echo -e "${CYAN}[i] 服务状态:${NC}"
    echo
    for service in $SERVICES nginx postgresql redis-server; do
        status=$(systemctl is-active $service 2>/dev/null)
        if [ "$status" = "active" ]; then
            echo -e "  ${GREEN}●${NC} $service: ${GREEN}运行中${NC}"
        else
            echo -e "  ${RED}●${NC} $service: ${RED}已停止${NC}"
        fi
    done
}

show_app_logs() {
    echo -e "${CYAN}[i] 应用日志 (按 Ctrl+C 退出)${NC}"
    echo
    tail -f $LOG_DIR/gunicorn-error.log $LOG_DIR/gunicorn-access.log
}

show_nginx_logs() {
    echo -e "${CYAN}[i] Nginx日志 (按 Ctrl+C 退出)${NC}"
    echo
    tail -f /var/log/nginx/access.log /var/log/nginx/error.log
}

backup_database() {
    BACKUP_DIR="$APP_DIR/backups"
    mkdir -p "$BACKUP_DIR"
    BACKUP_FILE="$BACKUP_DIR/db_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    # 从.env读取数据库信息
    source $APP_DIR/backend/.env
    
    echo -e "${CYAN}[i] 备份数据库到: $BACKUP_FILE${NC}"
    sudo -u postgres pg_dump $POSTGRES_DB > "$BACKUP_FILE"
    
    if [ $? -eq 0 ]; then
        gzip "$BACKUP_FILE"
        echo -e "${GREEN}[✓] 备份完成: ${BACKUP_FILE}.gz${NC}"
        echo -e "${CYAN}[i] 文件大小: $(du -h "${BACKUP_FILE}.gz" | cut -f1)${NC}"
    else
        echo -e "${RED}[✗] 备份失败${NC}"
    fi
}

restore_database() {
    BACKUP_DIR="$APP_DIR/backups"
    
    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A $BACKUP_DIR 2>/dev/null)" ]; then
        echo -e "${YELLOW}[!] 没有找到备份文件${NC}"
        return
    fi
    
    echo -e "${CYAN}可用的备份文件:${NC}"
    ls -la "$BACKUP_DIR"/*.sql* 2>/dev/null
    echo
    read -p "请输入要恢复的备份文件名: " BACKUP_FILE
    
    FULL_PATH="$BACKUP_DIR/$BACKUP_FILE"
    
    if [ -f "$FULL_PATH" ]; then
        echo -e "${YELLOW}[!] 警告: 这将覆盖当前数据库！${NC}"
        read -p "确定要继续吗? (yes/no): " CONFIRM
        
        if [ "$CONFIRM" = "yes" ]; then
            source $APP_DIR/backend/.env
            
            echo -e "${CYAN}[i] 正在恢复数据库...${NC}"
            
            if [[ "$FULL_PATH" == *.gz ]]; then
                gunzip -c "$FULL_PATH" | sudo -u postgres psql $POSTGRES_DB
            else
                sudo -u postgres psql $POSTGRES_DB < "$FULL_PATH"
            fi
            
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
    cd $APP_DIR/backend
    source $VENV_DIR/bin/activate
    python manage.py shell
    deactivate
}

run_migrate() {
    echo -e "${CYAN}[i] 执行数据库迁移...${NC}"
    cd $APP_DIR/backend
    source $VENV_DIR/bin/activate
    python manage.py migrate
    deactivate
    echo -e "${GREEN}[✓] 迁移完成${NC}"
}

collect_static() {
    echo -e "${CYAN}[i] 收集静态文件...${NC}"
    cd $APP_DIR/backend
    source $VENV_DIR/bin/activate
    python manage.py collectstatic --noinput
    deactivate
    echo -e "${GREEN}[✓] 静态文件收集完成${NC}"
}

show_install_info() {
    if [ -f "$APP_DIR/INSTALL_INFO.txt" ]; then
        cat "$APP_DIR/INSTALL_INFO.txt"
    else
        echo -e "${YELLOW}[!] 安装信息文件不存在${NC}"
    fi
}

# 命令行模式
if [ $# -gt 0 ]; then
    case "$1" in
        start) start_services ;;
        stop) stop_services ;;
        restart) restart_services ;;
        status) show_status ;;
        logs) show_app_logs ;;
        backup) backup_database ;;
        migrate) run_migrate ;;
        shell) enter_shell ;;
        *)
            echo "用法: $0 {start|stop|restart|status|logs|backup|migrate|shell}"
            exit 1
            ;;
    esac
    exit 0
fi

# 交互模式
while true; do
    show_menu
    read -p "请选择操作 [0-12]: " choice
    
    case $choice in
        1) start_services ;;
        2) stop_services ;;
        3) restart_services ;;
        4) show_status ;;
        5) show_app_logs ;;
        6) show_nginx_logs ;;
        7) backup_database ;;
        8) restore_database ;;
        9) enter_shell ;;
        10) run_migrate ;;
        11) collect_static ;;
        12) show_install_info ;;
        0) echo "再见！"; exit 0 ;;
        *) echo -e "${RED}无效选择${NC}" ;;
    esac
    
    echo
    read -p "按回车键继续..."
done
