#!/bin/bash
#
# ERP系统 Ubuntu 原生部署脚本（不使用Docker）
# 支持: Ubuntu 20.04/22.04/24.04 LTS
# 用法: sudo bash deploy-native-ubuntu.sh
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# 配置变量
APP_USER="erp"
APP_DIR="/opt/erp"
VENV_DIR="/opt/erp/venv"
LOG_DIR="/var/log/erp"

# 数据库配置
DB_NAME="erp_db"
DB_USER="erp_user"
DB_PASSWORD=$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 16)

# Django配置
SECRET_KEY=$(openssl rand -base64 50 | tr -dc 'a-zA-Z0-9' | head -c 50)
SERVER_IP=$(hostname -I | awk '{print $1}')

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║                                                       ║"
    echo "║   ERP系统 Ubuntu 原生部署（无Docker）v1.0             ║"
    echo "║                                                       ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo -e "\n${CYAN}========================================${NC}"
    echo -e "${CYAN} $1${NC}"
    echo -e "${CYAN}========================================${NC}"
}

print_success() { echo -e "${GREEN}[✓] $1${NC}"; }
print_error() { echo -e "${RED}[✗] $1${NC}"; }
print_warning() { echo -e "${YELLOW}[!] $1${NC}"; }
print_info() { echo -e "${CYAN}[i] $1${NC}"; }

# 检查root权限
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "请使用 sudo 运行此脚本"
        exit 1
    fi
}

# 获取项目目录
get_project_dir() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    SOURCE_DIR="$(dirname "$SCRIPT_DIR")"
    print_info "源代码目录: $SOURCE_DIR"
}

# 安装系统依赖
install_dependencies() {
    print_step "步骤 1/10: 安装系统依赖"
    
    apt-get update
    apt-get install -y \
        python3 python3-pip python3-venv python3-dev \
        postgresql postgresql-contrib libpq-dev \
        redis-server \
        nginx \
        nodejs npm \
        git curl wget \
        supervisor \
        build-essential \
        libffi-dev libssl-dev
    
    # 安装Node.js 18.x（如果版本太低）
    NODE_VERSION=$(node -v 2>/dev/null | cut -d'v' -f2 | cut -d'.' -f1)
    if [ -z "$NODE_VERSION" ] || [ "$NODE_VERSION" -lt 18 ]; then
        print_info "安装 Node.js 18.x..."
        curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
        apt-get install -y nodejs
    fi
    
    print_success "系统依赖安装完成"
}

# 创建应用用户
create_app_user() {
    print_step "步骤 2/10: 创建应用用户"
    
    if id "$APP_USER" &>/dev/null; then
        print_info "用户 $APP_USER 已存在"
    else
        useradd -r -m -d /home/$APP_USER -s /bin/bash $APP_USER
        print_success "用户 $APP_USER 创建成功"
    fi
}

# 配置PostgreSQL
setup_postgresql() {
    print_step "步骤 3/10: 配置 PostgreSQL"
    
    # 启动PostgreSQL
    systemctl start postgresql
    systemctl enable postgresql
    
    # 创建数据库和用户
    sudo -u postgres psql -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true
    sudo -u postgres psql -c "DROP USER IF EXISTS $DB_USER;" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
    
    print_success "PostgreSQL 配置完成"
    print_info "数据库: $DB_NAME"
    print_info "用户: $DB_USER"
    print_info "密码: $DB_PASSWORD"
}

# 配置Redis
setup_redis() {
    print_step "步骤 4/10: 配置 Redis"
    
    systemctl start redis-server
    systemctl enable redis-server
    
    print_success "Redis 配置完成"
}

# 复制项目文件
copy_project() {
    print_step "步骤 5/10: 复制项目文件"
    
    # 创建目录
    mkdir -p $APP_DIR
    mkdir -p $LOG_DIR
    
    # 复制文件
    cp -r "$SOURCE_DIR/backend" "$APP_DIR/"
    cp -r "$SOURCE_DIR/frontend" "$APP_DIR/"
    cp -r "$SOURCE_DIR/scripts" "$APP_DIR/"
    
    # 设置脚本执行权限
    chmod +x $APP_DIR/scripts/*.sh 2>/dev/null || true
    
    # 设置权限
    chown -R $APP_USER:$APP_USER $APP_DIR
    chown -R $APP_USER:$APP_USER $LOG_DIR
    
    print_success "项目文件复制完成"
}

# 配置后端
setup_backend() {
    print_step "步骤 6/10: 配置 Django 后端"
    
    cd $APP_DIR/backend
    
    # 创建虚拟环境
    python3 -m venv $VENV_DIR
    
    # 激活虚拟环境并安装依赖
    source $VENV_DIR/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    pip install gunicorn psycopg2-binary
    
    # 创建环境配置文件
    cat > $APP_DIR/backend/.env << EOF
# Database
DATABASE_URL=postgres://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME
POSTGRES_DB=$DB_NAME
POSTGRES_USER=$DB_USER
POSTGRES_PASSWORD=$DB_PASSWORD

# Django
SECRET_KEY=$SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,$SERVER_IP

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0

# 时区
TZ=Asia/Shanghai
EOF
    
    # 执行数据库迁移
    python manage.py migrate --noinput
    
    # 创建管理员
    python manage.py shell << 'PYEOF'
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Admin created: admin / admin123')
PYEOF
    
    # 初始化数据
    python manage.py init_workflows 2>/dev/null || true
    python manage.py init_dashboard_widgets 2>/dev/null || true
    
    # 收集静态文件
    python manage.py collectstatic --noinput
    
    deactivate
    
    chown -R $APP_USER:$APP_USER $APP_DIR
    
    print_success "Django 后端配置完成"
}

# 构建前端
setup_frontend() {
    print_step "步骤 7/10: 构建 Vue 前端"
    
    cd $APP_DIR/frontend
    
    # 安装依赖
    npm install
    
    # 构建生产版本
    npm run build
    
    # 复制到nginx目录
    mkdir -p /var/www/erp
    cp -r dist/* /var/www/erp/
    
    chown -R www-data:www-data /var/www/erp
    
    print_success "前端构建完成"
}

# 配置Gunicorn
setup_gunicorn() {
    print_step "步骤 8/10: 配置 Gunicorn"
    
    # 创建Gunicorn配置
    cat > $APP_DIR/gunicorn.conf.py << EOF
bind = "127.0.0.1:8000"
workers = 4
threads = 2
worker_class = "gthread"
timeout = 120
keepalive = 5
errorlog = "$LOG_DIR/gunicorn-error.log"
accesslog = "$LOG_DIR/gunicorn-access.log"
loglevel = "info"
EOF
    
    # 创建systemd服务
    cat > /etc/systemd/system/erp-backend.service << EOF
[Unit]
Description=ERP Backend (Gunicorn)
After=network.target postgresql.service redis-server.service

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR/backend
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/gunicorn config.wsgi:application -c $APP_DIR/gunicorn.conf.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable erp-backend
    systemctl start erp-backend
    
    print_success "Gunicorn 配置完成"
}

# 配置Celery
setup_celery() {
    print_step "步骤 9/10: 配置 Celery"
    
    # Celery Worker服务
    cat > /etc/systemd/system/erp-celery.service << EOF
[Unit]
Description=ERP Celery Worker
After=network.target redis-server.service

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR/backend
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/celery -A config worker -l info
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
    
    # Celery Beat服务
    cat > /etc/systemd/system/erp-celery-beat.service << EOF
[Unit]
Description=ERP Celery Beat
After=network.target redis-server.service

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR/backend
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/celery -A config beat -l info
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable erp-celery erp-celery-beat
    systemctl start erp-celery erp-celery-beat
    
    print_success "Celery 配置完成"
}

# 配置Nginx
setup_nginx() {
    print_step "步骤 10/10: 配置 Nginx"
    
    # 创建Nginx配置
    cat > /etc/nginx/sites-available/erp << 'EOF'
server {
    listen 80;
    server_name _;
    client_max_body_size 100M;

    # 前端静态文件
    location / {
        root /var/www/erp;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 后端API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 300s;
        proxy_read_timeout 300s;
    }

    # Django Admin
    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 静态文件
    location /static/ {
        alias /opt/erp/backend/staticfiles/;
        expires 30d;
    }

    # 媒体文件
    location /media/ {
        alias /opt/erp/backend/media/;
        expires 7d;
    }
}
EOF
    
    # 启用站点
    ln -sf /etc/nginx/sites-available/erp /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # 测试配置
    nginx -t
    
    # 重启Nginx
    systemctl restart nginx
    systemctl enable nginx
    
    print_success "Nginx 配置完成"
}

# 配置防火墙
setup_firewall() {
    if command -v ufw &> /dev/null; then
        print_info "配置防火墙..."
        ufw allow 22/tcp
        ufw allow 80/tcp
        ufw allow 443/tcp
        ufw --force enable
        print_success "防火墙配置完成"
    fi
}

# 保存配置信息
save_config() {
    cat > $APP_DIR/INSTALL_INFO.txt << EOF
========================================
ERP系统安装信息
========================================
安装时间: $(date)
服务器IP: $SERVER_IP

数据库信息:
- 数据库名: $DB_NAME
- 用户名: $DB_USER
- 密码: $DB_PASSWORD

管理员账号:
- 用户名: admin
- 密码: admin123

访问地址:
- 前端: http://$SERVER_IP
- 后台: http://$SERVER_IP/admin

服务管理:
- 启动: sudo systemctl start erp-backend erp-celery erp-celery-beat
- 停止: sudo systemctl stop erp-backend erp-celery erp-celery-beat
- 重启: sudo systemctl restart erp-backend erp-celery erp-celery-beat
- 状态: sudo systemctl status erp-backend

日志位置:
- 应用日志: $LOG_DIR/
- Nginx日志: /var/log/nginx/

========================================
EOF
    
    chmod 600 $APP_DIR/INSTALL_INFO.txt
}

# 显示完成信息
show_completion() {
    echo -e "\n${GREEN}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║                                                       ║"
    echo "║              部署成功！                               ║"
    echo "║                                                       ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "  ${CYAN}访问地址:${NC}"
    echo -e "  ├─ 前端界面: http://$SERVER_IP"
    echo -e "  └─ 后台管理: http://$SERVER_IP/admin"
    echo
    echo -e "  ${CYAN}默认账号:${NC}"
    echo -e "  ├─ 用户名: admin"
    echo -e "  └─ 密码:   admin123"
    echo
    echo -e "  ${CYAN}数据库信息:${NC}"
    echo -e "  ├─ 数据库: $DB_NAME"
    echo -e "  ├─ 用户:   $DB_USER"
    echo -e "  └─ 密码:   $DB_PASSWORD"
    echo
    echo -e "  ${CYAN}服务管理:${NC}"
    echo -e "  ├─ 查看状态: sudo systemctl status erp-backend"
    echo -e "  ├─ 重启服务: sudo systemctl restart erp-backend"
    echo -e "  └─ 查看日志: sudo tail -f $LOG_DIR/gunicorn-error.log"
    echo
    echo -e "  ${YELLOW}请立即修改默认密码！${NC}"
    echo -e "  ${CYAN}安装信息已保存到: $APP_DIR/INSTALL_INFO.txt${NC}"
    echo
}

# 安装升级代理
install_updater() {
    print_step "安装远程升级代理"

    mkdir -p /opt/erp/updater/deploy/updater
    cp -r "$SOURCE_DIR/deploy/updater/." /opt/erp/updater/deploy/updater/
    pip install redis requests >/dev/null 2>&1 || true
    cp "$SOURCE_DIR/deploy/updater/erp-updater.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable --now erp-updater
    # 写入版本与模式(被 backend 读取)
    echo "DEPLOY_MODE=native" >> "$APP_DIR/.env"
    echo "APP_VERSION=$(git -C "$SOURCE_DIR" describe --tags --abbrev=0 2>/dev/null || echo 0.0.0)" >> "$APP_DIR/.env"

    print_success "远程升级代理安装完成"
}

# 主函数
main() {
    print_banner
    check_root
    get_project_dir

    install_dependencies
    create_app_user
    setup_postgresql
    setup_redis
    copy_project
    setup_backend
    setup_frontend
    setup_gunicorn
    setup_celery
    setup_nginx
    setup_firewall
    install_updater
    save_config

    show_completion
}

main "$@"
