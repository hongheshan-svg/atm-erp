# ERP系统 Ubuntu 原生部署指南（无Docker）

本指南介绍如何在Ubuntu服务器上直接部署ERP系统，不使用Docker。

## 系统要求

### 硬件配置
| 配置项 | 最低配置 | 推荐配置 |
|--------|----------|----------|
| CPU | 2核 | 4核+ |
| 内存 | 4GB | 8GB+ |
| 硬盘 | 40GB | 100GB+ SSD |

### 操作系统
- Ubuntu 20.04 LTS
- Ubuntu 22.04 LTS（推荐）
- Ubuntu 24.04 LTS

---

## 一键部署

```bash
# 1. 上传项目到服务器（假设在 /tmp/erp-source）

# 2. 进入项目目录
cd /tmp/erp-source

# 3. 运行原生部署脚本
sudo bash scripts/deploy-native-ubuntu.sh
```

部署脚本会自动完成：
- 安装 Python、PostgreSQL、Redis、Nginx、Node.js
- 创建数据库和用户
- 配置 Django 后端
- 构建 Vue 前端
- 配置 Gunicorn、Celery、Nginx
- 创建 systemd 服务

---

## 手动部署步骤

### 1. 安装系统依赖

```bash
sudo apt update && sudo apt upgrade -y

# Python
sudo apt install -y python3 python3-pip python3-venv python3-dev

# PostgreSQL
sudo apt install -y postgresql postgresql-contrib libpq-dev

# Redis
sudo apt install -y redis-server

# Nginx
sudo apt install -y nginx

# Node.js 18.x
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# 其他工具
sudo apt install -y git curl build-essential
```

### 2. 配置 PostgreSQL

```bash
# 启动服务
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 创建数据库和用户
sudo -u postgres psql << EOF
CREATE USER erp_user WITH PASSWORD 'your_password';
CREATE DATABASE erp_db OWNER erp_user;
GRANT ALL PRIVILEGES ON DATABASE erp_db TO erp_user;
EOF
```

### 3. 配置 Redis

```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### 4. 部署后端

```bash
# 创建目录
sudo mkdir -p /opt/erp
sudo cp -r backend /opt/erp/

# 创建虚拟环境
cd /opt/erp/backend
python3 -m venv /opt/erp/venv
source /opt/erp/venv/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install gunicorn psycopg2-binary

# 创建环境配置
cat > .env << EOF
DATABASE_URL=postgres://erp_user:your_password@localhost:5432/erp_db
SECRET_KEY=your_secret_key_here
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,your_server_ip
REDIS_URL=redis://localhost:6379/0
EOF

# 数据库迁移
python manage.py migrate

# 创建管理员
python manage.py createsuperuser

# 收集静态文件
python manage.py collectstatic --noinput

deactivate
```

### 5. 构建前端

```bash
cd /opt/erp/frontend

# 安装依赖
npm install

# 构建
npm run build

# 复制到Nginx目录
sudo mkdir -p /var/www/erp
sudo cp -r dist/* /var/www/erp/
```

### 6. 配置 Gunicorn 服务

创建 `/etc/systemd/system/erp-backend.service`:

```ini
[Unit]
Description=ERP Backend
After=network.target postgresql.service redis-server.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/erp/backend
Environment="PATH=/opt/erp/venv/bin"
ExecStart=/opt/erp/venv/bin/gunicorn config.wsgi:application -b 127.0.0.1:8000 -w 4
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable erp-backend
sudo systemctl start erp-backend
```

### 7. 配置 Celery 服务

创建 `/etc/systemd/system/erp-celery.service`:

```ini
[Unit]
Description=ERP Celery Worker
After=network.target redis-server.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/erp/backend
Environment="PATH=/opt/erp/venv/bin"
ExecStart=/opt/erp/venv/bin/celery -A config worker -l info
Restart=always

[Install]
WantedBy=multi-user.target
```

### 8. 配置 Nginx

创建 `/etc/nginx/sites-available/erp`:

```nginx
server {
    listen 80;
    server_name _;
    client_max_body_size 100M;

    location / {
        root /var/www/erp;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static/ {
        alias /opt/erp/backend/staticfiles/;
    }

    location /media/ {
        alias /opt/erp/backend/media/;
    }
}
```

启用站点：
```bash
sudo ln -s /etc/nginx/sites-available/erp /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

---

## 服务管理

### 使用管理脚本

```bash
# 交互模式
sudo /opt/erp/scripts/manage-native.sh

# 命令行模式
sudo /opt/erp/scripts/manage-native.sh start
sudo /opt/erp/scripts/manage-native.sh stop
sudo /opt/erp/scripts/manage-native.sh restart
sudo /opt/erp/scripts/manage-native.sh status
```

### 使用 systemctl

```bash
# 启动
sudo systemctl start erp-backend erp-celery

# 停止
sudo systemctl stop erp-backend erp-celery

# 重启
sudo systemctl restart erp-backend erp-celery

# 查看状态
sudo systemctl status erp-backend
```

### 查看日志

```bash
# 应用日志
sudo tail -f /var/log/erp/gunicorn-error.log

# Nginx日志
sudo tail -f /var/log/nginx/error.log

# 系统日志
sudo journalctl -u erp-backend -f
```

---

## 数据备份

```bash
# 备份数据库
sudo -u postgres pg_dump erp_db > backup_$(date +%Y%m%d).sql

# 恢复数据库
sudo -u postgres psql erp_db < backup_20241201.sql

# 备份媒体文件
tar -czvf media_backup.tar.gz /opt/erp/backend/media/
```

---

## 更新系统

```bash
cd /opt/erp

# 备份
sudo -u postgres pg_dump erp_db > backup_before_update.sql

# 更新代码
sudo git pull  # 或重新上传文件

# 更新后端
source /opt/erp/venv/bin/activate
pip install -r backend/requirements.txt
cd backend
python manage.py migrate
python manage.py collectstatic --noinput
deactivate

# 更新前端
cd /opt/erp/frontend
npm install
npm run build
sudo cp -r dist/* /var/www/erp/

# 重启服务
sudo systemctl restart erp-backend erp-celery nginx
```

---

## 安装的组件

| 组件 | 说明 | 端口 |
|------|------|------|
| Nginx | Web服务器/反向代理 | 80 |
| Gunicorn | Python WSGI服务器 | 8000 |
| PostgreSQL | 数据库 | 5432 |
| Redis | 缓存/消息队列 | 6379 |
| Celery | 异步任务 | - |

---

## 目录结构

```
/opt/erp/
├── backend/          # Django后端
├── frontend/         # Vue前端源码
├── venv/            # Python虚拟环境
├── gunicorn.conf.py # Gunicorn配置
├── INSTALL_INFO.txt # 安装信息
└── backups/         # 数据库备份

/var/www/erp/        # 前端构建文件
/var/log/erp/        # 应用日志
```

---

## 常见问题

### Q1: 502 Bad Gateway
```bash
# 检查后端服务
sudo systemctl status erp-backend
sudo tail -f /var/log/erp/gunicorn-error.log
```

### Q2: 静态文件404
```bash
# 重新收集静态文件
source /opt/erp/venv/bin/activate
cd /opt/erp/backend
python manage.py collectstatic --noinput
```

### Q3: 数据库连接失败
```bash
# 检查PostgreSQL
sudo systemctl status postgresql
sudo -u postgres psql -c "\l"
```

---

*文档版本: 1.0 | 更新日期: 2024年12月*
