# ERP企业资源管理系统

一个基于 Django + Vue3 + Element Plus 的现代化企业资源管理系统，支持项目管理、采购销售、库存管理、财务管理、审批流程等核心业务功能。

## 🌟 功能特性

### 核心模块
- **项目管理** - 项目立项、任务分配、进度跟踪、甘特图、工时管理
- **采购管理** - 采购申请、采购订单、到货质检、供应商管理
- **销售管理** - 销售报价、销售订单、发货管理、客户管理
- **库存管理** - 库存查询、批次管理、库存调拨、盘点、预警
- **财务管理** - 费用报销、应收应付、发票管理、项目成本核算
- **审批中心** - 可配置审批流程（SAP风格）、待办审批、我的提交

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
- 🔄 实时数据同步
- 🚀 Ubuntu原生部署，简单高效

## 🛠 技术栈

### 后端
- Python 3.11
- Django 4.2 + Django REST Framework
- PostgreSQL 15
- Redis 7
- Celery（异步任务）

### 前端
- Vue 3 + Composition API
- Element Plus
- Vite
- ECharts（图表）
- Axios

### 部署
- Ubuntu Server（原生部署）
- Nginx
- Gunicorn
- Systemd

## 📦 快速开始

### 系统要求
- Ubuntu 20.04/22.04/24.04 LTS
- 最低配置：2核CPU、4GB内存、40GB硬盘
- 推荐配置：4核CPU、8GB内存、100GB SSD

### 一键部署

```bash
# 1. 上传项目到服务器
scp -r erp-system.tar.gz user@server:/tmp/

# 2. 登录服务器并解压
ssh user@server
cd /tmp
tar -xzvf erp-system.tar.gz
cd erp-system

# 3. 运行一键安装脚本
sudo bash install.sh
```

安装脚本会自动完成：
- 安装 Python、PostgreSQL、Redis、Nginx、Node.js
- 创建数据库和用户
- 配置 Django 后端
- 构建 Vue 前端
- 配置 Systemd 服务
- 启动所有服务

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
└── install.sh             # 一键安装脚本
```

## 📖 文档

| 文档 | 说明 |
|------|------|
| [Ubuntu部署指南](UBUNTU-NATIVE-DEPLOYMENT.md) | Ubuntu原生部署完整教程 |
| [快速部署参考](QUICK-DEPLOY-CARD.md) | 部署命令速查表 |
| [快速开始指南](QUICK-START-GUIDE.md) | 系统使用入门 |
| [系统架构](SYSTEM-ARCHITECTURE.md) | 技术架构说明 |
| [安全指南](SECURITY-PERFORMANCE-GUIDE.md) | 安全配置和性能优化 |

## 🔧 服务管理

```bash
# 使用管理脚本（推荐）
sudo /opt/erp/scripts/manage-native.sh

# 或使用 systemctl
sudo systemctl start erp-backend erp-celery    # 启动
sudo systemctl stop erp-backend erp-celery     # 停止
sudo systemctl restart erp-backend erp-celery  # 重启
sudo systemctl status erp-backend              # 状态
```

## 💾 数据备份

```bash
# 备份数据库
sudo -u postgres pg_dump erp_db > backup_$(date +%Y%m%d).sql

# 恢复数据库
sudo -u postgres psql erp_db < backup.sql
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
