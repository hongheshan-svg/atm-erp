#!/bin/bash
#
# ERP系统 Ubuntu 一键部署脚本
# 支持: Ubuntu 20.04/22.04/24.04 LTS
# 用法: sudo bash deploy-ubuntu.sh
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 打印函数
print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║                                                       ║"
    echo "║     ERP系统 Ubuntu 一键部署工具 v1.0                  ║"
    echo "║                                                       ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo -e "\n${CYAN}========================================${NC}"
    echo -e "${CYAN} $1${NC}"
    echo -e "${CYAN}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}[✓] $1${NC}"
}

print_error() {
    echo -e "${RED}[✗] $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[!] $1${NC}"
}

print_info() {
    echo -e "${BLUE}[i] $1${NC}"
}

# 检查是否为root用户
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "请使用 sudo 运行此脚本"
        echo "用法: sudo bash $0"
        exit 1
    fi
}

# 检查系统版本
check_system() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    else
        print_error "无法检测操作系统版本"
        exit 1
    fi
    
    print_info "操作系统: $OS $VER"
    
    if [[ "$ID" != "ubuntu" ]]; then
        print_warning "此脚本针对Ubuntu优化，其他系统可能需要调整"
    fi
}

# 获取项目目录
get_project_dir() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    cd "$PROJECT_DIR"
    print_info "项目目录: $PROJECT_DIR"
}

# 安装Docker
install_docker() {
    print_step "步骤 1/6: 安装 Docker"
    
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version)
        print_success "Docker 已安装: $DOCKER_VERSION"
    else
        print_info "正在安装 Docker..."
        
        # 更新包索引
        apt-get update -qq
        
        # 安装依赖
        apt-get install -y -qq \
            apt-transport-https \
            ca-certificates \
            curl \
            gnupg \
            lsb-release
        
        # 添加Docker官方GPG密钥
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        
        # 设置稳定版仓库
        echo \
            "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
            $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        # 安装Docker Engine
        apt-get update -qq
        apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
        
        # 启动Docker服务
        systemctl start docker
        systemctl enable docker
        
        print_success "Docker 安装完成"
    fi
    
    # 检查Docker Compose
    if command -v docker-compose &> /dev/null; then
        COMPOSE_VERSION=$(docker-compose --version)
        print_success "Docker Compose 已安装: $COMPOSE_VERSION"
    elif docker compose version &> /dev/null; then
        print_success "Docker Compose (plugin) 已安装"
        # 创建别名
        echo 'alias docker-compose="docker compose"' >> /etc/bash.bashrc
    else
        print_info "正在安装 Docker Compose..."
        apt-get install -y -qq docker-compose-plugin
        print_success "Docker Compose 安装完成"
    fi
}

# 生成配置文件
generate_config() {
    print_step "步骤 2/6: 生成配置文件"
    
    ENV_FILE="$PROJECT_DIR/backend/.env"
    
    if [ -f "$ENV_FILE" ]; then
        print_warning ".env 文件已存在"
        read -p "是否覆盖现有配置? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "保留现有配置"
            return
        fi
    fi
    
    print_info "生成新的配置文件..."
    
    # 生成随机密码和密钥
    DB_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)
    SECRET_KEY=$(openssl rand -base64 50 | tr -dc 'a-zA-Z0-9!@#$%^&*' | head -c 50)
    SERVER_IP=$(hostname -I | awk '{print $1}')
    
    # 创建.env文件
    cat > "$ENV_FILE" << EOF
# Database
POSTGRES_DB=erp_db
POSTGRES_USER=erp_user
POSTGRES_PASSWORD=$DB_PASSWORD
DATABASE_URL=postgres://erp_user:$DB_PASSWORD@db:5432/erp_db

# Django
SECRET_KEY=$SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,$SERVER_IP

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
EOF
    
    print_success "配置文件已生成: $ENV_FILE"
    print_info "数据库密码: $DB_PASSWORD"
    print_warning "请妥善保管以上密码！"
}

# 构建Docker镜像
build_images() {
    print_step "步骤 3/6: 构建 Docker 镜像"
    
    print_info "开始构建镜像，这可能需要几分钟..."
    
    # 使用docker compose或docker-compose
    if docker compose version &> /dev/null; then
        docker compose build
    else
        docker-compose build
    fi
    
    print_success "镜像构建完成"
}

# 启动服务
start_services() {
    print_step "步骤 4/6: 启动服务"
    
    print_info "启动所有服务..."
    
    if docker compose version &> /dev/null; then
        docker compose up -d
    else
        docker-compose up -d
    fi
    
    print_success "服务启动命令已执行"
    
    # 等待服务就绪
    print_info "等待服务就绪..."
    
    MAX_RETRIES=60
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if docker compose ps 2>/dev/null | grep -q "healthy" || docker-compose ps 2>/dev/null | grep -q "healthy"; then
            break
        fi
        sleep 2
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo -n "."
    done
    echo
    
    if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
        print_success "所有服务已就绪"
    else
        print_warning "部分服务可能仍在启动中"
    fi
}

# 初始化数据库
init_database() {
    print_step "步骤 5/6: 初始化数据库"
    
    print_info "执行数据库迁移..."
    
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi
    
    # 等待数据库就绪
    sleep 5
    
    $COMPOSE_CMD exec -T backend python manage.py migrate --noinput
    print_success "数据库迁移完成"
    
    print_info "创建管理员账号..."
    $COMPOSE_CMD exec -T backend python manage.py shell << 'EOF'
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Admin user created: admin / admin123')
else:
    print('Admin user already exists')
EOF
    print_success "管理员账号: admin / admin123"
    
    print_info "初始化基础数据..."
    $COMPOSE_CMD exec -T backend python manage.py init_workflows 2>/dev/null || true
    $COMPOSE_CMD exec -T backend python manage.py init_dashboard_widgets 2>/dev/null || true
    print_success "基础数据初始化完成"
    
    print_info "收集静态文件..."
    $COMPOSE_CMD exec -T backend python manage.py collectstatic --noinput 2>/dev/null || true
    print_success "静态文件收集完成"
}

# 配置防火墙
configure_firewall() {
    print_step "步骤 6/6: 配置防火墙"
    
    if command -v ufw &> /dev/null; then
        print_info "配置 UFW 防火墙..."
        ufw allow 80/tcp
        ufw allow 443/tcp
        ufw allow 22/tcp
        print_success "防火墙规则已添加"
    else
        print_info "UFW 未安装，跳过防火墙配置"
    fi
}

# 显示完成信息
show_completion() {
    SERVER_IP=$(hostname -I | awk '{print $1}')
    
    echo -e "\n${GREEN}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║                                                       ║"
    echo "║              部署成功！                               ║"
    echo "║                                                       ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "  ${CYAN}访问地址:${NC}"
    echo -e "  ├─ 本地访问:   http://localhost"
    echo -e "  ├─ 局域网访问: http://$SERVER_IP"
    echo -e "  └─ 后台管理:   http://$SERVER_IP/admin"
    echo
    echo -e "  ${CYAN}默认账号:${NC}"
    echo -e "  ├─ 用户名: admin"
    echo -e "  └─ 密码:   admin123"
    echo
    echo -e "  ${CYAN}常用命令:${NC}"
    echo -e "  ├─ 查看状态:   docker compose ps"
    echo -e "  ├─ 查看日志:   docker compose logs -f"
    echo -e "  ├─ 重启服务:   docker compose restart"
    echo -e "  └─ 停止服务:   docker compose down"
    echo
    echo -e "  ${YELLOW}请立即修改默认密码！${NC}"
    echo
}

# 创建系统服务（可选）
create_systemd_service() {
    print_info "创建系统服务..."
    
    cat > /etc/systemd/system/erp.service << EOF
[Unit]
Description=ERP System
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable erp.service
    
    print_success "系统服务已创建，开机将自动启动"
}

# 主函数
main() {
    print_banner
    
    check_root
    check_system
    get_project_dir
    
    install_docker
    generate_config
    build_images
    start_services
    init_database
    configure_firewall
    create_systemd_service
    
    show_completion
}

# 运行主函数
main "$@"
