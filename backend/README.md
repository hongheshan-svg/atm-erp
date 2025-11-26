# Python ERP System - Backend

企业资源计划系统后端 - 基于 Django REST Framework

## 技术栈

- **Python 3.10+**
- **Django 4.2.9** - Web 框架
- **Django REST Framework** - API 开发
- **PostgreSQL** - 数据库
- **Redis** - 缓存和 Celery Broker
- **Celery** - 异步任务队列
- **Pandas** - 数据分析和成本计算
- **JWT** - 身份认证

## 功能模块

### 1. 用户与权限管理 (accounts)
- 用户管理
- 角色与权限 (RBAC)
- 部门管理
- 数据权限控制 (全部/部门/个人)

### 2. 基础数据管理 (masterdata)
- 物料主数据 (Item)
- 客户管理 (Customer)
- 供应商管理 (Supplier)
- 仓库管理 (Warehouse)
- 物料分类 (ItemCategory)

### 3. 项目管理 (projects)
- 项目信息与预算
- 项目成员与工时
- 项目任务 (WBS)
- 项目 BOM

### 4. 采购管理 (purchase)
- 采购申请 (PR)
- 采购订单 (PO)
- 收货管理 (Goods Receipt)

### 5. 销售管理 (sales)
- 销售报价 (Quotation)
- 销售订单 (SO) - 强制关联项目
- 发货管理 (Delivery Order)

### 6. 库存管理 (inventory)
- 实时库存 (Stock)
- 库存移动 (StockMove) - 加权平均成本法
- 库存调整 (Adjustment)
- 低库存预警

### 7. 财务管理 (finance)
- 费用报销 (Expense) - 关联项目/部门
- 应收账款 (AR)
- 应付账款 (AP)
- 账龄分析

### 8. 报表中心 (reports)
- 项目利润分析 (使用 Pandas)
- 成本明细报表
- 仪表盘汇总
- Excel 导出

## 安装与运行

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 数据库配置

创建 PostgreSQL 数据库:

```sql
CREATE DATABASE erp_db;
CREATE USER erp_user WITH PASSWORD 'erp_password';
GRANT ALL PRIVILEGES ON DATABASE erp_db TO erp_user;
```

配置环境变量（创建 `.env` 文件）:

```
SECRET_KEY=your-secret-key-here
DEBUG=True
DB_NAME=erp_db
DB_USER=erp_user
DB_PASSWORD=erp_password
DB_HOST=localhost
DB_PORT=5432
REDIS_URL=redis://127.0.0.1:6379/1
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
```

### 3. 数据库迁移

```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. 创建超级用户

```bash
python manage.py createsuperuser
```

### 5. 运行开发服务器

```bash
python manage.py runserver
```

API 文档地址: `http://localhost:8000/api/docs/`

### 6. 启动 Celery (可选)

```bash
# Worker
celery -A config worker -l info

# Beat (定时任务)
celery -A config beat -l info
```

## API 文档

访问 `http://localhost:8000/api/docs/` 查看完整的 Swagger API 文档。

### 主要 API 端点

- **认证**: `/api/auth/login/` `/api/auth/refresh/`
- **用户管理**: `/api/auth/users/`
- **物料**: `/api/masterdata/items/`
- **项目**: `/api/projects/projects/`
- **采购**: `/api/purchase/orders/`
- **销售**: `/api/sales/orders/`
- **库存**: `/api/inventory/stocks/`
- **财务**: `/api/finance/expenses/`
- **报表**: `/api/reports/profitability/`

## 核心业务逻辑

### 1. 成本核算流程

```
项目材料成本 = Σ(项目领料 × 加权平均成本)
项目人工成本 = Σ(实际工时 × 时薪)
项目费用成本 = Σ(已批准的报销)
项目毛利 = 销售收入 - (材料成本 + 人工成本 + 费用成本)
```

### 2. 库存成本计算

采用**加权平均法**：

```
新加权成本 = (原库存金额 + 新入库金额) / (原库存数量 + 新入库数量)
```

### 3. 项目与财务关联

- 所有**销售订单**必须关联项目（收入归集）
- 所有**费用报销**必须关联项目或部门（成本归集）
- **项目领料**自动记录到该项目的成本

## 定时任务

Celery Beat 自动执行以下任务：

- **每日 2:00** - 计算所有项目成本并缓存
- **每日 8:00** - 检查低库存并发送邮件提醒
- **每日 9:00** - 检查逾期应收账款并发送提醒

## 数据权限

系统支持三级数据权限：

- **全部数据** (ALL): 可查看所有数据
- **部门数据** (DEPARTMENT): 只能查看本部门数据
- **个人数据** (SELF): 只能查看自己创建的数据

## 测试

```bash
# 运行所有测试
python manage.py test

# 运行特定模块测试
python manage.py test apps.projects.tests
```

## 生产部署建议

1. 使用 **Gunicorn** 或 **uWSGI** 运行 Django
2. 使用 **Nginx** 作为反向代理
3. 配置 **PostgreSQL** 主从复制
4. 使用 **Redis Sentinel** 提高可用性
5. 启用 **Django** 的 `DEBUG=False`
6. 配置日志收集 (ELK Stack)
7. 设置监控告警 (Prometheus + Grafana)

## 项目结构

```
backend/
├── config/              # Django 配置
│   ├── settings.py
│   ├── urls.py
│   └── celery.py
├── apps/
│   ├── core/           # 基础模型和工具
│   ├── accounts/       # 用户和权限
│   ├── masterdata/     # 基础数据
│   ├── projects/       # 项目管理
│   ├── purchase/       # 采购管理
│   ├── sales/          # 销售管理
│   ├── inventory/      # 库存管理
│   ├── finance/        # 财务管理
│   └── reports/        # 报表中心
├── requirements.txt
└── manage.py
```

## 常见问题

### 1. 如何重置数据库？

```bash
python manage.py flush
python manage.py loaddata initial_data.json  # 如果有初始数据
```

### 2. 如何清理 Celery 任务队列？

```bash
celery -A config purge
```

### 3. 如何备份数据库？

```bash
python manage.py dumpdata > backup.json
# 或使用 pg_dump
pg_dump erp_db > backup.sql
```

## 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 许可证

MIT License

## 联系方式

如有问题请联系项目维护者。

