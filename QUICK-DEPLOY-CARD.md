# ERP系统快速部署参考卡

## 🚀 一键部署

```bash
# 1. 上传项目到服务器
scp erp-system.tar.gz user@server:/tmp/

# 2. 登录服务器
ssh user@server

# 3. 解压并安装
cd /tmp
tar -xzvf erp-system.tar.gz
cd erp-system
sudo bash install.sh
```

---

## 📋 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Ubuntu 20.04/22.04/24.04 LTS |
| CPU | 最低2核，推荐4核+ |
| 内存 | 最低4GB，推荐8GB+ |
| 硬盘 | 最低40GB，推荐100GB SSD |

---

## 🌐 访问地址

| 服务 | 地址 |
|------|------|
| 前端界面 | http://服务器IP |
| 后台管理 | http://服务器IP/admin |
| API接口 | http://服务器IP/api/ |

### 默认账号
- 用户名：`admin`
- 密码：`admin123`

---

## 📦 服务管理

```bash
# 交互式管理（推荐）
sudo /opt/erp/scripts/manage-native.sh

# 启动所有服务
sudo systemctl start erp-backend erp-celery nginx

# 停止所有服务
sudo systemctl stop erp-backend erp-celery

# 重启所有服务
sudo systemctl restart erp-backend erp-celery nginx

# 查看服务状态
sudo systemctl status erp-backend
sudo systemctl status erp-celery
sudo systemctl status nginx
sudo systemctl status postgresql
sudo systemctl status redis-server
```

---

## 📋 查看日志

```bash
# 应用日志
sudo tail -f /var/log/erp/gunicorn-error.log
sudo tail -f /var/log/erp/celery.log

# Nginx日志
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# 系统服务日志
sudo journalctl -u erp-backend -f
sudo journalctl -u erp-celery -f
```

---

## 💾 数据备份

```bash
# 备份数据库
sudo -u postgres pg_dump erp_db > backup_$(date +%Y%m%d).sql

# 恢复数据库
sudo -u postgres psql erp_db < backup.sql

# 备份媒体文件
tar -czvf media_backup.tar.gz /opt/erp/backend/media/
```

---

## 🔧 Django管理命令

```bash
# 激活虚拟环境
source /opt/erp/venv/bin/activate
cd /opt/erp/backend

# 数据库迁移
python manage.py migrate

# 创建管理员
python manage.py createsuperuser

# 收集静态文件
python manage.py collectstatic --noinput

# 退出虚拟环境
deactivate
```

---

## ❓ 常见问题

### 502 Bad Gateway
```bash
# 检查后端服务
sudo systemctl status erp-backend
sudo tail -f /var/log/erp/gunicorn-error.log
```

### 静态文件404
```bash
source /opt/erp/venv/bin/activate
cd /opt/erp/backend
python manage.py collectstatic --noinput
sudo systemctl restart nginx
```

### 数据库连接失败
```bash
sudo systemctl status postgresql
sudo -u postgres psql -c "\l"
```

### 权限问题
```bash
sudo chown -R www-data:www-data /opt/erp
sudo chown -R www-data:www-data /var/www/erp
```

---

## 📂 目录结构

```
/opt/erp/              # 应用目录
├── backend/           # Django后端
├── frontend/          # Vue前端源码
├── venv/             # Python虚拟环境
└── scripts/          # 管理脚本

/var/www/erp/         # 前端构建文件
/var/log/erp/         # 应用日志
```

---

## 🔐 安全配置

```bash
# 配置防火墙
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable

# 配置SSL（使用Let's Encrypt）
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

*文档版本: 1.0 | 更新日期: 2024年12月*
