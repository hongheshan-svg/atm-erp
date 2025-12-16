# ERP系统 Ubuntu 服务器部署指南

## 目录
1. [服务器要求](#服务器要求)
2. [一键部署](#一键部署)
3. [手动部署](#手动部署)
4. [配置说明](#配置说明)
5. [服务管理](#服务管理)
6. [SSL证书配置](#ssl证书配置)
7. [常见问题](#常见问题)

---

## 服务器要求

### 硬件配置
| 配置项 | 最低配置 | 推荐配置 |
|--------|----------|----------|
| CPU | 2核 | 4核+ |
| 内存 | 4GB | 8GB+ |
| 硬盘 | 50GB SSD | 100GB+ SSD |
| 网络 | 10Mbps | 100Mbps+ |

### 操作系统
- Ubuntu 20.04 LTS
- Ubuntu 22.04 LTS（推荐）
- Ubuntu 24.04 LTS

### 网络要求
- 开放端口：22 (SSH), 80 (HTTP), 443 (HTTPS)
- 建议配置固定IP或域名

---

## 一键部署

### 方法1：直接运行（推荐）

```bash
# 1. 上传项目文件到服务器（或使用git克隆）
# 假设项目在 /opt/erp 目录

# 2. 进入项目目录
cd /opt/erp

# 3. 添加执行权限
chmod +x scripts/deploy-ubuntu.sh

# 4. 运行一键部署脚本
sudo bash scripts/deploy-ubuntu.sh
```

### 方法2：从GitHub克隆

```bash
# 1. 安装git
sudo apt update && sudo apt install -y git

# 2. 克隆项目
sudo git clone <你的仓库地址> /opt/erp

# 3. 运行部署脚本
cd /opt/erp
sudo bash scripts/deploy-ubuntu.sh
```

### 部署完成后

- 前端访问：`http://服务器IP`
- 后台管理：`http://服务器IP/admin`
- 默认账号：`admin` / `admin123`

---

## 手动部署

如果一键部署失败，可按以下步骤手动安装：

### 1. 安装Docker

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装依赖
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release

# 添加Docker GPG密钥
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# 添加Docker仓库
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动Docker
sudo systemctl start docker
sudo systemctl enable docker

# 验证安装
docker --version
docker compose version
```

### 2. 配置环境变量

```bash
cd /opt/erp/backend

# 复制示例配置
cp .env.prod.example .env

# 编辑配置文件
nano .env
```

修改以下配置：
```ini
POSTGRES_PASSWORD=你的数据库密码
SECRET_KEY=你的Django密钥
ALLOWED_HOSTS=localhost,127.0.0.1,你的服务器IP,你的域名
```

### 3. 构建并启动服务

```bash
cd /opt/erp

# 构建镜像
docker compose build

# 启动服务
docker compose up -d

# 查看状态
docker compose ps
```

### 4. 初始化数据库

```bash
# 执行迁移
docker compose exec backend python manage.py migrate

# 创建管理员
docker compose exec backend python manage.py createsuperuser

# 初始化数据
docker compose exec backend python manage.py init_workflows
docker compose exec backend python manage.py init_dashboard_widgets

# 收集静态文件
docker compose exec backend python manage.py collectstatic --noinput
```

---

## 配置说明

### 环境变量文件 (backend/.env)

```ini
# 数据库配置
POSTGRES_DB=erp_db
POSTGRES_USER=erp_user
POSTGRES_PASSWORD=强密码

# Django配置
SECRET_KEY=随机密钥
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,你的IP

# Redis配置
REDIS_URL=redis://redis:6379/0

# 邮件配置（可选）
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email
EMAIL_HOST_PASSWORD=your_password
```

### 生成安全密钥

```bash
# 生成数据库密码
openssl rand -base64 24

# 生成Django密钥
openssl rand -base64 50
```

---

## 服务管理

### 使用管理脚本

```bash
# 添加执行权限
chmod +x scripts/manage-service.sh

# 交互模式
./scripts/manage-service.sh

# 命令行模式
./scripts/manage-service.sh start    # 启动
./scripts/manage-service.sh stop     # 停止
./scripts/manage-service.sh restart  # 重启
./scripts/manage-service.sh status   # 状态
./scripts/manage-service.sh logs     # 日志
./scripts/manage-service.sh backup   # 备份
./scripts/manage-service.sh migrate  # 迁移
```

### 常用Docker命令

```bash
# 启动服务
docker compose up -d

# 停止服务
docker compose down

# 重启服务
docker compose restart

# 查看日志
docker compose logs -f

# 查看特定服务日志
docker compose logs -f backend

# 进入容器
docker compose exec backend bash

# 执行Django命令
docker compose exec backend python manage.py <command>
```

### 设置开机自启

```bash
# 创建系统服务
sudo nano /etc/systemd/system/erp.service
```

内容：
```ini
[Unit]
Description=ERP System
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/erp
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable erp.service
```

---

## SSL证书配置

### 使用Let's Encrypt免费证书

```bash
# 安装certbot
sudo apt install -y certbot

# 获取证书（需要先停止nginx）
docker compose stop nginx
sudo certbot certonly --standalone -d your-domain.com

# 复制证书
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/key.pem

# 修改nginx配置使用SSL
# 编辑 nginx/nginx.conf 或使用 nginx/nginx-ssl.conf

# 重启nginx
docker compose up -d nginx
```

### 自动续期

```bash
# 添加定时任务
sudo crontab -e

# 添加以下行（每月1号凌晨3点续期）
0 3 1 * * certbot renew --quiet && docker compose -f /opt/erp/docker-compose.yml restart nginx
```

---

## 数据备份

### 手动备份

```bash
# 备份数据库
docker compose exec -T db pg_dump -U erp_user erp_db > backup_$(date +%Y%m%d).sql

# 备份上传文件
tar -czvf media_backup_$(date +%Y%m%d).tar.gz backend/media/
```

### 自动备份脚本

```bash
#!/bin/bash
# /opt/erp/scripts/backup.sh

BACKUP_DIR="/opt/erp/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# 备份数据库
docker compose -f /opt/erp/docker-compose.yml exec -T db pg_dump -U erp_user erp_db > $BACKUP_DIR/db_$DATE.sql

# 备份媒体文件
tar -czvf $BACKUP_DIR/media_$DATE.tar.gz -C /opt/erp/backend media/

# 删除7天前的备份
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup completed: $DATE"
```

设置定时任务：
```bash
# 每天凌晨2点备份
0 2 * * * /opt/erp/scripts/backup.sh >> /var/log/erp-backup.log 2>&1
```

---

## 常见问题

### Q1: Docker安装失败
```bash
# 使用国内镜像源
curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

### Q2: 端口被占用
```bash
# 查看端口占用
sudo netstat -tlnp | grep :80
sudo lsof -i :80

# 停止占用进程
sudo kill -9 <PID>
```

### Q3: 权限问题
```bash
# 将当前用户加入docker组
sudo usermod -aG docker $USER

# 重新登录生效
```

### Q4: 内存不足
```bash
# 创建swap文件
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 永久生效
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Q5: 镜像拉取慢
```bash
# 配置Docker镜像加速
sudo nano /etc/docker/daemon.json
```

内容：
```json
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://registry.docker-cn.com"
  ]
}
```

重启Docker：
```bash
sudo systemctl restart docker
```

---

## 更新系统

```bash
cd /opt/erp

# 拉取最新代码
git pull

# 重建镜像
docker compose build

# 重启服务
docker compose up -d

# 执行迁移
docker compose exec backend python manage.py migrate
```

---

## 技术支持

遇到问题请提供：
1. 操作系统版本：`cat /etc/os-release`
2. Docker版本：`docker --version`
3. 服务状态：`docker compose ps`
4. 错误日志：`docker compose logs`

---

*文档版本: 1.0 | 更新日期: 2024年12月*
