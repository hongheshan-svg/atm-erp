# ERP企业资源管理系统

一个基于 Django + Vue3 + Element Plus 的现代化企业资源管理系统，支持项目管理、采购销售、库存管理、财务管理、审批流程等核心业务功能。

## 🌟 功能特性

### 核心模块
- **项目管理** - 项目立项、任务分配、进度跟踪、甘特图、工时管理
- **采购管理** - 采购申请、采购订单、到货质检、供应商管理
- **销售管理** - 销售报价、销售订单、发货管理、客户管理
- **库存管理** - 库存查询、批次管理、库存调拨、盘点、预警
- **财务管理** - 费用报销、应收应付、发票管理、项目成本核算
- **审批中心** - 可配置审批流程、待办审批、我的提交

### 系统功能
- **用户权限** - 用户管理、角色管理、部门管理（树形架构）
- **数据分析** - 项目利润分析、库存周转率、账龄分析、现金流预测
- **系统配置** - 仪表盘配置、Webhook管理、登录日志、审计日志
- **通知中心** - 站内通知、邮件通知、微信通知

### 技术亮点
- 🎨 现代化UI设计，参考SAP风格
- 📱 响应式布局，支持移动端
- 🔐 完善的权限控制和安全机制
- 📊 丰富的数据可视化图表
- 🔄 实时数据同步（WebSocket）
- 📦 Docker一键部署

## 🛠 技术栈

### 后端
- Python 3.11
- Django 4.2 + Django REST Framework
- PostgreSQL 15
- Redis 7
- Celery（异步任务）
- Elasticsearch（全文搜索）

### 前端
- Vue 3 + Composition API
- Element Plus
- Vite
- ECharts（图表）
- Axios

### 部署
- Docker + Docker Compose
- Nginx
- Gunicorn

## 📦 快速开始

### 环境要求
- Docker Desktop
- Git

### 一键部署（Ubuntu Server）

```bash
# 1. 克隆项目
sudo git clone <repository-url> /opt/erp
cd /opt/erp

# 2. 运行安装脚本
sudo bash install.sh
```

### 一键部署（Windows Server）

```powershell
# 1. 克隆项目
git clone <repository-url> C:\ERP
cd C:\ERP

# 2. 运行安装脚本
.\install.bat
```

### 手动部署

```bash
# 1. 克隆项目
git clone <repository-url>
cd erp

# 2. 启动服务
docker-compose up -d

# 3. 初始化数据库
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser

# 4. 访问系统
# 前端: http://localhost
# 后台: http://localhost/admin
```

### 默认账号
- 用户名：`admin`
- 密码：`admin123`

## 📁 项目结构

```
erp/
├── backend/                 # Django后端
│   ├── apps/               # 应用模块
│   │   ├── core/          # 核心模块（用户、权限、审批流程）
│   │   ├── projects/      # 项目管理
│   │   ├── purchase/      # 采购管理
│   │   ├── sales/         # 销售管理
│   │   ├── inventory/     # 库存管理
│   │   └── finance/       # 财务管理
│   ├── config/            # Django配置
│   └── requirements.txt   # Python依赖
├── frontend/               # Vue前端
│   ├── src/
│   │   ├── api/          # API接口
│   │   ├── components/   # 公共组件
│   │   ├── views/        # 页面视图
│   │   ├── stores/       # Pinia状态管理
│   │   └── router/       # 路由配置
│   └── package.json
├── nginx/                  # Nginx配置
├── scripts/               # 部署脚本
├── miniprogram/           # 微信小程序（可选）
├── docker-compose.yml     # 开发环境配置
├── docker-compose.prod.yml # 生产环境配置
└── install.bat            # Windows一键安装
```

## 📖 文档

| 文档 | 说明 |
|------|------|
| [Ubuntu部署指南](UBUNTU-DEPLOYMENT-GUIDE.md) | Ubuntu Server完整部署教程 |
| [Windows部署指南](WINDOWS-DEPLOYMENT-GUIDE.md) | Windows Server完整部署教程 |
| [快速部署参考](QUICK-DEPLOY-CARD.md) | 部署命令速查表 |
| [快速开始指南](QUICK-START-GUIDE.md) | 系统使用入门 |
| [系统架构](SYSTEM-ARCHITECTURE.md) | 技术架构说明 |
| [安全指南](SECURITY-PERFORMANCE-GUIDE.md) | 安全配置和性能优化 |

## 🔧 常用命令

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 查看日志
docker-compose logs -f

# 进入后端容器
docker-compose exec backend bash

# 执行Django命令
docker-compose exec backend python manage.py <command>

# 备份数据库
docker-compose exec db pg_dump -U erp_user erp_db > backup.sql
```

## 🔐 安全建议

1. **修改默认密码** - 首次登录后立即修改admin密码
2. **配置HTTPS** - 生产环境务必启用SSL证书
3. **定期备份** - 建议每日自动备份数据库
4. **更新依赖** - 定期更新系统依赖包

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request

---

*版本: 1.0.0 | 更新日期: 2024年12月*
