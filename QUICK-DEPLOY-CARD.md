# ERP系统快速部署参考卡

## 🚀 一键部署（推荐）

```powershell
# 1. 以管理员身份打开 PowerShell
# 2. 进入项目目录
cd C:\ERP

# 3. 执行一键部署
.\install.bat
```

或者双击 `install.bat` 文件

---

## 📋 前置要求

### 必须安装
| 软件 | 下载地址 |
|------|----------|
| Docker Desktop | https://docker.com/products/docker-desktop |
| Git | https://git-scm.com/download/win |

### 安装Docker后
1. 重启服务器
2. 启动 Docker Desktop
3. 等待 Docker 引擎启动（托盘图标变绿）

---

## 🔧 手动部署命令

```powershell
# 进入项目目录
cd C:\ERP

# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 初始化数据库
docker-compose exec backend python manage.py migrate

# 创建管理员
docker-compose exec backend python manage.py createsuperuser
```

---

## 🌐 访问地址

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost |
| 后台管理 | http://localhost/admin |
| API文档 | http://localhost/api/docs/ |

### 默认账号
- 用户名：`admin`
- 密码：`admin123`

---

## 📦 常用命令

```powershell
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend

# 进入后端容器
docker-compose exec backend bash

# 执行Django命令
docker-compose exec backend python manage.py <command>
```

---

## 💾 数据备份

```powershell
# 备份数据库
docker-compose exec db pg_dump -U erp_user erp_db > backup.sql

# 恢复数据库
Get-Content backup.sql | docker-compose exec -T db psql -U erp_user erp_db
```

---

## ❓ 常见问题

### Docker启动失败
```powershell
# 启用Hyper-V
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
```

### 端口被占用
```powershell
# 查看端口占用
netstat -ano | findstr :80
```

### 服务无法访问
```powershell
# 检查防火墙
New-NetFirewallRule -DisplayName "ERP HTTP" -Direction Inbound -Port 80 -Protocol TCP -Action Allow
```

---

## 📞 技术支持

遇到问题请提供：
1. `docker-compose ps` 输出
2. `docker-compose logs` 日志
3. 错误截图

---

*文档版本: 1.0 | 更新日期: 2024-12*
