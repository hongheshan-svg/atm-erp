# ERP系统 Docker 部署指南

## 📋 系统要求

- Docker 20.10+
- Docker Compose v2.0+
- 至少 4GB 可用内存
- 至少 20GB 可用磁盘空间

## 🚀 快速开始

### 1. 配置 Docker 权限

如果遇到权限问题，将用户加入 docker 组：

```bash
sudo usermod -aG docker $USER
# 重新登录或执行:
newgrp docker
```

### 2. 配置环境变量

```bash
cd /home/administrator/erp

# 复制并编辑环境配置
cp .env.docker .env
nano .env  # 修改数据库密码、SECRET_KEY等
```

**重要配置项：**
- `SECRET_KEY`: 更换为安全的随机字符串
- `DB_PASSWORD`: 更换数据库密码
- `ALLOWED_HOSTS`: 添加你的域名或IP

### 3. 构建并启动服务

```bash
# 使用管理脚本
./scripts/docker-manage.sh build
./scripts/docker-manage.sh start

# 或直接使用 docker compose
docker compose up -d --build
```

### 4. 查看服务状态

```bash
./scripts/docker-manage.sh status
# 或
docker compose ps
```

### 5. 查看日志

```bash
./scripts/docker-manage.sh logs          # 所有服务
./scripts/docker-manage.sh logs backend  # 只看后端
./scripts/docker-manage.sh logs nginx    # 只看Nginx
```

## 📦 服务架构

| 服务 | 端口 | 说明 |
|------|------|------|
| nginx | 80, 443 | 反向代理 + 前端静态文件 |
| backend | 8000 (内部) | Django API 服务器 |
| celery | - | 异步任务处理 |
| celery-beat | - | 定时任务调度 |
| postgres | 5432 | PostgreSQL 数据库 |
| redis | 6379 | 缓存 + 消息队列 |
| elasticsearch | 9200 | 全文搜索 (可选) |

## 🔧 常用命令

### 服务管理

```bash
# 启动服务
./scripts/docker-manage.sh start

# 停止服务
./scripts/docker-manage.sh stop

# 重启服务
./scripts/docker-manage.sh restart

# 查看状态
./scripts/docker-manage.sh status
```

### Django 管理命令

```bash
# 创建超级用户
./scripts/docker-manage.sh manage createsuperuser

# 数据库迁移
./scripts/docker-manage.sh manage migrate

# 收集静态文件
./scripts/docker-manage.sh manage collectstatic
```

### 数据备份

```bash
# 备份数据库
./scripts/docker-manage.sh backup

# 恢复数据库
./scripts/docker-manage.sh restore backup_20231220.sql
```

### 清理

```bash
# 删除所有容器和数据卷（慎用！）
./scripts/docker-manage.sh clean
```

## 🔐 访问系统

启动成功后访问：

- **前端**: http://localhost
- **API 文档**: http://localhost/api/docs/
- **Django Admin**: http://localhost/admin/

**默认管理员账号：**
- 用户名: `admin`
- 密码: `admin123`

⚠️ **请在首次登录后立即修改密码！**

## 🌐 生产环境配置

### 配置 HTTPS

1. 获取 SSL 证书（推荐 Let's Encrypt）

2. 修改 `docker/nginx/nginx.conf` 添加 SSL 配置：

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    
    # ... 其他配置
}
```

3. 挂载证书目录到 nginx 容器

### 修改 .env 生产配置

```env
DEBUG=False
SECRET_KEY=your-very-long-and-random-secret-key-here

ALLOWED_HOSTS=your-domain.com,www.your-domain.com
CORS_ALLOWED_ORIGINS=https://your-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.com

SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

## 📊 监控与日志

### 查看容器日志

```bash
# 实时日志
docker compose logs -f

# 特定服务日志
docker compose logs -f backend
```

### 进入容器

```bash
# 进入后端容器
docker compose exec backend bash

# 进入数据库容器
docker compose exec postgres psql -U erp_user erp_db
```

## 🔍 故障排除

### 服务无法启动

1. 检查端口占用：
```bash
netstat -tlnp | grep -E '80|5432|6379|9200'
```

2. 检查 Docker 日志：
```bash
docker compose logs --tail=50
```

3. 检查磁盘空间：
```bash
df -h
```

### 数据库连接失败

1. 确认 PostgreSQL 容器运行正常：
```bash
docker compose exec postgres pg_isready
```

2. 检查数据库日志：
```bash
docker compose logs postgres
```

### Elasticsearch 启动慢

ES 需要较多内存，首次启动可能需要 2-3 分钟。可以先不启用 ES：

```bash
docker compose up -d --scale elasticsearch=0
```

## 📁 数据卷

所有持久化数据存储在 Docker volumes 中：

| Volume | 说明 |
|--------|------|
| postgres_data | 数据库文件 |
| redis_data | Redis 持久化数据 |
| elasticsearch_data | ES 索引数据 |
| static_files | Django 静态文件 |
| media_files | 上传的媒体文件 |
| backend_logs | 后端日志 |
| nginx_logs | Nginx 日志 |

备份这些 volume 即可完整备份系统数据。

---

*更新日期: 2024年12月*

