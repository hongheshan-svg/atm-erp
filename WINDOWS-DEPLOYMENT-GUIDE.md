# ERP系统 Windows Server 2022 部署指南

## 目录
1. [服务器要求](#服务器要求)
2. [软件安装清单](#软件安装清单)
3. [一键部署步骤](#一键部署步骤)
4. [手动安装步骤](#手动安装步骤)
5. [配置说明](#配置说明)
6. [常见问题](#常见问题)

---

## 服务器要求

### 硬件配置（最低要求）
| 配置项 | 最低配置 | 推荐配置 |
|--------|----------|----------|
| CPU | 4核 | 8核+ |
| 内存 | 8GB | 16GB+ |
| 硬盘 | 100GB SSD | 256GB+ SSD |
| 网络 | 100Mbps | 1Gbps |

### 操作系统
- Windows Server 2022 Standard/Datacenter
- 需要启用 Hyper-V 和容器功能

### 网络要求
- 开放端口：80 (HTTP), 443 (HTTPS), 8000 (API)
- 建议配置固定IP地址
- 如需外网访问，需配置域名和SSL证书

---

## 软件安装清单

### 必需软件

| 软件 | 版本 | 用途 | 下载地址 |
|------|------|------|----------|
| Docker Desktop | 最新版 | 容器运行环境 | https://www.docker.com/products/docker-desktop |
| Git | 最新版 | 代码管理 | https://git-scm.com/download/win |

### 可选软件

| 软件 | 版本 | 用途 | 下载地址 |
|------|------|------|----------|
| VS Code | 最新版 | 代码编辑 | https://code.visualstudio.com/ |
| Notepad++ | 最新版 | 配置文件编辑 | https://notepad-plus-plus.org/ |

---

## 一键部署步骤

### 步骤1：安装Docker Desktop

1. 下载 Docker Desktop for Windows
2. 双击安装程序，按提示完成安装
3. 安装完成后重启服务器
4. 启动 Docker Desktop，等待 Docker 引擎启动完成
5. 打开 PowerShell，验证安装：
   ```powershell
   docker --version
   docker-compose --version
   ```

### 步骤2：安装Git

1. 下载 Git for Windows
2. 双击安装程序，使用默认选项完成安装
3. 打开 PowerShell，验证安装：
   ```powershell
   git --version
   ```

### 步骤3：获取项目代码

```powershell
# 创建项目目录
mkdir C:\ERP
cd C:\ERP

# 克隆项目（替换为你的仓库地址）
git clone <你的仓库地址> .

# 或者直接复制项目文件到 C:\ERP 目录
```

### 步骤4：一键部署

以管理员身份运行 PowerShell，执行：

```powershell
cd C:\ERP
.\scripts\deploy-windows.ps1
```

脚本会自动完成：
- 环境检查
- 配置文件生成
- Docker镜像构建
- 服务启动
- 数据库初始化
- 管理员账号创建

### 步骤5：访问系统

部署完成后，打开浏览器访问：
- 前端界面：http://localhost 或 http://服务器IP
- 后台管理：http://localhost/admin
- 默认账号：admin / admin123

---

## 手动安装步骤

如果一键部署失败，可以按以下步骤手动安装：

### 1. 配置环境变量

复制并编辑环境配置文件：

```powershell
cd C:\ERP\backend
copy .env.prod.example .env
notepad .env
```

修改以下配置：
```ini
# 数据库配置
POSTGRES_DB=erp_db
POSTGRES_USER=erp_user
POSTGRES_PASSWORD=your_secure_password_here

# Django配置
SECRET_KEY=your_very_long_random_secret_key_here
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,你的服务器IP,你的域名

# Redis配置
REDIS_URL=redis://redis:6379/0
```

### 2. 构建并启动服务

```powershell
cd C:\ERP

# 构建镜像
docker-compose -f docker-compose.prod.yml build

# 启动服务
docker-compose -f docker-compose.prod.yml up -d

# 查看服务状态
docker-compose -f docker-compose.prod.yml ps
```

### 3. 初始化数据库

```powershell
# 执行数据库迁移
docker-compose -f docker-compose.prod.yml exec backend python manage.py migrate

# 创建超级管理员
docker-compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser

# 初始化基础数据
docker-compose -f docker-compose.prod.yml exec backend python manage.py init_workflows
docker-compose -f docker-compose.prod.yml exec backend python manage.py init_dashboard_widgets
```

### 4. 收集静态文件

```powershell
docker-compose -f docker-compose.prod.yml exec backend python manage.py collectstatic --noinput
```

---

## 配置说明

### 生产环境配置文件

| 文件 | 说明 |
|------|------|
| `backend/.env` | 后端环境变量 |
| `docker-compose.prod.yml` | 生产环境Docker配置 |
| `nginx/nginx-ssl.conf` | Nginx SSL配置 |

### 重要配置项

#### 数据库密码
```ini
POSTGRES_PASSWORD=修改为强密码
```

#### Django密钥
```ini
SECRET_KEY=生成一个随机的长字符串
```
生成方法：
```powershell
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

#### 允许的主机
```ini
ALLOWED_HOSTS=localhost,127.0.0.1,你的IP,你的域名
```

### SSL证书配置（HTTPS）

1. 获取SSL证书（可使用Let's Encrypt免费证书）
2. 将证书文件放到 `nginx/ssl/` 目录：
   - `cert.pem` - 证书文件
   - `key.pem` - 私钥文件
3. 修改 `docker-compose.prod.yml`，启用SSL配置
4. 重启nginx服务

---

## 服务管理命令

### 启动服务
```powershell
docker-compose -f docker-compose.prod.yml up -d
```

### 停止服务
```powershell
docker-compose -f docker-compose.prod.yml down
```

### 重启服务
```powershell
docker-compose -f docker-compose.prod.yml restart
```

### 查看日志
```powershell
# 查看所有服务日志
docker-compose -f docker-compose.prod.yml logs

# 查看特定服务日志
docker-compose -f docker-compose.prod.yml logs backend
docker-compose -f docker-compose.prod.yml logs nginx

# 实时查看日志
docker-compose -f docker-compose.prod.yml logs -f
```

### 查看服务状态
```powershell
docker-compose -f docker-compose.prod.yml ps
```

---

## 数据备份与恢复

### 备份数据库
```powershell
# 创建备份目录
mkdir C:\ERP\backups

# 备份数据库
docker-compose -f docker-compose.prod.yml exec db pg_dump -U erp_user erp_db > C:\ERP\backups\db_backup_$(Get-Date -Format "yyyyMMdd").sql
```

### 恢复数据库
```powershell
# 恢复数据库
Get-Content C:\ERP\backups\db_backup_20231201.sql | docker-compose -f docker-compose.prod.yml exec -T db psql -U erp_user erp_db
```

### 备份上传文件
```powershell
# 备份media目录
Compress-Archive -Path C:\ERP\backend\media -DestinationPath C:\ERP\backups\media_backup_$(Get-Date -Format "yyyyMMdd").zip
```

---

## 常见问题

### Q1: Docker Desktop 启动失败
**解决方案：**
1. 确保已启用 Hyper-V 功能
2. 在 PowerShell (管理员) 中执行：
   ```powershell
   Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
   Enable-WindowsOptionalFeature -Online -FeatureName Containers -All
   ```
3. 重启服务器

### Q2: 端口被占用
**解决方案：**
```powershell
# 查看端口占用
netstat -ano | findstr :80
netstat -ano | findstr :443

# 停止占用端口的进程
Stop-Process -Id <PID> -Force
```

### Q3: 数据库连接失败
**解决方案：**
1. 检查数据库容器是否正常运行
2. 检查 `.env` 文件中的数据库配置
3. 查看数据库日志：
   ```powershell
   docker-compose -f docker-compose.prod.yml logs db
   ```

### Q4: 前端页面无法访问
**解决方案：**
1. 检查nginx容器状态
2. 检查防火墙设置
3. 查看nginx日志：
   ```powershell
   docker-compose -f docker-compose.prod.yml logs nginx
   ```

### Q5: 如何更新系统
```powershell
cd C:\ERP

# 拉取最新代码
git pull

# 重新构建并启动
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# 执行数据库迁移
docker-compose -f docker-compose.prod.yml exec backend python manage.py migrate
```

---

## 技术支持

如遇到问题，请提供以下信息：
1. 服务器配置信息
2. Docker版本
3. 错误日志截图
4. 执行的命令和输出

---

## 版本信息

- 文档版本：1.0
- 更新日期：2024年12月
- 适用系统：Windows Server 2022
