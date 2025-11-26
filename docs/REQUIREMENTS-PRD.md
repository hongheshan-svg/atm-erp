# Python 企业级 ERP 系统需求规格说明书 (PRD)

## 1. 项目概述 (Project Overview)

**项目目标：** 构建一套轻量级但功能闭环的企业管理系统，打通"业务（项目）- 供应链（进销存）- 财务（成本）"的数据孤岛。

**适用场景：** 以项目制为主的贸易公司、工程公司、IT外包公司或生产制造型企业。

**核心价值：** 实现项目维度的全成本核算（人、材、机、费），实时掌握企业现金流与库存状况。

---

## 2. 技术架构选型 (Technology Stack)

鉴于Python的生态优势，推荐采用以下成熟架构，确保开发效率与系统稳定性：

### 后端框架：Django (配合 Django REST Framework)
**理由：** 自带强大的ORM、Admin后台、用户认证系统，适合快速构建复杂的关系型数据系统。

### 前端框架：Vue 3 或 React (配合 Ant Design Pro 或 Element Plus)
**理由：** 组件丰富，适合后台管理系统的表格、表单、图表开发。

### 数据库：PostgreSQL
**理由：** 对复杂查询、JSON数据支持优于MySQL，适合ERP复杂的报表统计。

### 缓存/消息队列：Redis & Celery
**理由：** 处理库存锁单、异步生成报表、发送邮件通知。

### 数据分析/报表：Pandas & Matplotlib/Echarts
**理由：** Python最强项，用于成本计算和可视化展示。

---

## 3. 详细功能模块 (Functional Requirements)

系统共分为五大核心子系统：系统管理、项目管理(PM)、进销存(PSI)、财务与成本管控、报表中心。

### 3.1 系统基础模块 (System Core)

#### 用户与权限 (RBAC)
- **用户管理：** 增删改查，关联部门。
- **角色管理：** 定义角色（如：项目经理、采购员、财务），配置菜单权限和数据权限（例如：销售只能看自己的订单，总监看全部）。

#### 基础数据
- **物料主数据 (Item Master)：** SKU编码、名称、规格、单位、默认供应商、标准成本（用于估算）。
- **往来单位：** 客户管理 (CRM)、供应商管理 (SRM)。
- **仓库定义：** 多仓库支持、库位管理。

---

### 3.2 项目管理模块 (Project Management - PM)

这是业务的源头，所有采购和费用需关联项目。

#### 项目立项
- 项目基本信息（名称、编号、负责人、起止时间）。
- 项目预算设置（人工预算、材料预算、费用预算）。
- 项目状态流转（立项 -> 进行中 -> 暂停 -> 结项 -> 归档）。

#### 任务与进度 (WBS)
- 任务分解：支持多级任务树。
- 进度汇报：工时填报、进度百分比。
- 甘特图展示 (Gantt Chart)。

#### 项目资源
- 项目成员分配。
- BOM清单 (Bill of Materials)：如果是工程/制造项目，需定义该项目需要采购哪些物料（将推送到采购模块）。

---

### 3.3 进销存模块 (PSI - Purchase, Sales, Inventory)

此模块负责物资流转，数据必须实时准确。

#### 销售管理 (Sales)
- **销售报价：** 生成报价单，支持版本管理。
- **销售订单 (SO)：** 关键点——订单行需关联"项目ID"，以便收入归集。
- **发货通知：** 生成出库单，扣减库存。

#### 采购管理 (Purchase)
- **采购申请 (PR)：** 由项目经理发起，系统校验是否超出项目材料预算。
- **采购订单 (PO)：** 关联供应商，支持分批交货。
- **到货质检：** 入库前的验收环节。

#### 库存管理 (Inventory)
- **入库/出库：** 采购入库、销售出库、领料出库（项目领用）。
- **调拨与盘点：** 仓库间调拨、定期库存盘点修正。
- **库存预警：** 低于安全库存自动提醒。
- **即时库存查询：** 支持按仓库、按批次查询。

---

### 3.4 成本管控模块 (Cost Control & Finance)

这是系统的核心大脑，通过Python Pandas进行计算。

#### 费用报销
- 差旅费、招待费等申请与审批。
- **必须关联项目：** 每一笔报销必须选择归属的项目（或归属部门费用）。

#### 应收应付 (AR/AP)
- **应收账款：** 根据销售订单生成，记录回款计划、实际回款、逾期预警。
- **应付账款：** 根据采购入库单生成，记录付款计划、实际付款。
- **发票管理：** 进项票、销项票登记。

#### 全成本核算 (核心算法)
- **直接材料成本** = 项目领料出库数量 × 加权平均单价。
- **直接人工成本** = 项目成员工时 × 对应时薪。
- **项目费用** = 归属该项目的报销 + 采购的服务费用。
- **分摊费用** = 公司公共费用（房租、水电）按比例分摊到项目（可选）。

---

### 3.5 报表与决策中心 (Dashboard)

- **项目利润表：** 实时显示 项目收入 - (材料+人工+费用) = 项目毛利。
- **现金流预测：** 基于应收应付计划，预测未来1-3个月的资金缺口。
- **进销存报表：** 库存周转率、呆滞物料分析、采购价格波动趋势。

---

## 4. 数据模型设计 (核心 ERD 概念)

在 Django models.py 中，几个关键的连接点如下：

### Project (项目表)
- `id` (PK)
- `name`, `budget_total`, `manager_id`

### SalesOrder (销售订单)
- `project_id` (FK -> Project): 收入归集点
- `total_amount`

### PurchaseOrder (采购订单)
- `project_id` (FK -> Project): 材料成本归集点 (专款专用模式)
- 如果是通用库存采购，该字段可为空。

### StockMove (库存移动/流水)
- `product_id`
- `qty`, `price` (移动时的成本)
- `move_type` (采购入库/销售出库/项目领料)
- `project_id` (FK -> Project): 当 `move_type='项目领料'` 时必填，用于精确核算材料成本。

### Expense (费用/报销)
- `project_id` (FK -> Project): 费用成本归集点
- `amount`, `category`

---

## 5. Python 实现建议 (Implementation Tips)

### 5.1 后端逻辑 (Django Services)

不要把所有逻辑写在 View 里，建议采用 Service Layer 模式：

- `services/cost_service.py`: 专门处理成本计算逻辑。
- `services/inventory_service.py`: 处理库存增减、FIFO（先进先出）成本计算。

### 5.2 报表生成

使用 Pandas 处理复杂报表：

```python
# 示例：计算某项目的利润
import pandas as pd

def calculate_project_profit(project_id):
    # 1. 获取收入 (ORM查询转DataFrame)
    sales = pd.DataFrame(SalesOrder.objects.filter(project_id=project_id).values())
    total_revenue = sales['amount'].sum() if not sales.empty else 0
    
    # 2. 获取材料成本 (领料单)
    materials = pd.DataFrame(StockMove.objects.filter(project_id=project_id, type='OUT_PROJECT').values())
    material_cost = (materials['qty'] * materials['cost_price']).sum() if not materials.empty else 0
    
    # 3. 获取费用
    expenses = pd.DataFrame(Expense.objects.filter(project_id=project_id).values())
    expense_cost = expenses['amount'].sum() if not expenses.empty else 0
    
    return {
        "revenue": total_revenue,
        "cost": material_cost + expense_cost,
        "profit": total_revenue - (material_cost + expense_cost)
    }
```

### 5.3 异步任务

使用 Celery 处理耗时操作：

- 每日凌晨自动计算所有进行中项目的实时毛利率，存入缓存或统计表，避免用户查询时实时计算导致卡顿。
- 库存不足时发送邮件/钉钉/企业微信通知。

---

## 6. 开发阶段规划 (Roadmap)

### 第一阶段：MVP (最小可行性产品) - 2个月
- 完成用户与RBAC。
- 完成基础物料、客户、供应商管理。
- 实现简单的"采购入库"和"销售出库"。
- 实现基础的"项目立项"，将采购和销售关联到项目ID。

### 第二阶段：资金与成本 - 1.5个月
- 开发应收应付模块。
- 开发费用报销模块。
- 实现项目维度的成本核算逻辑（简单的收入-支出）。

### 第三阶段：高级功能与报表 - 1.5个月
- 完善库存管理（调拨、盘点、预警）。
- 开发Pandas驱动的高级BI仪表盘。
- 引入审批流（工作流引擎）。

---

## 7. 总结

这套系统最大的难点在于**数据一致性**（库存与财务对账）和**成本归集逻辑**（如何准确将每一分钱算到项目头上）。利用 Python 强大的数据处理能力，你可以比 Java 或 PHP 更轻松地处理复杂的财务报表逻辑。

---

**文档版本：** v1.0  
**创建日期：** 2025-11-24  
**状态：** ✅ 已完整实现

