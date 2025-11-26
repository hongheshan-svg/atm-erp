# ERP系统页面测试计划

**测试日期：** 2025-11-24  
**测试环境：** Docker + 前端端口3000

---

## 🎯 测试目标

1. 验证所有页面可以正常访问
2. 检查API调用是否正常
3. 测试数据的增删改查功能
4. 验证权限控制
5. 检查错误处理

---

## 📋 测试清单

### 1. 登录与认证模块

#### 1.1 登录页面
- [ ] 访问 http://localhost:3000/login
- [ ] 输入用户名密码
- [ ] 点击登录按钮
- [ ] 验证Token是否存储
- [ ] 检查自动跳转

**测试账号：**
- 用户名：`admin`
- 密码：`admin123`

**预期结果：**
- ✅ 登录成功
- ✅ Token存储到localStorage
- ✅ 跳转到Dashboard

---

### 2. 仪表板（Dashboard）

#### 2.1 首页展示
- [ ] 访问 http://localhost:3000/
- [ ] 检查KPI卡片显示
- [ ] 验证图表渲染
- [ ] 测试数据刷新

**预期结果：**
- ✅ 显示销售、采购、库存、财务指标
- ✅ ECharts图表正常渲染
- ✅ 数据从API加载

**API端点：**
- `GET /api/analytics/dashboard/kpi/`
- `GET /api/analytics/dashboard/sales-trend/`

---

### 3. 系统管理模块

#### 3.1 用户管理
- [ ] 访问 http://localhost:3000/system/users
- [ ] 查看用户列表
- [ ] 点击"新增用户"
- [ ] 填写表单并保存
- [ ] 编辑用户信息
- [ ] 删除用户

**测试数据：**
```json
{
  "username": "test_user",
  "email": "test@example.com",
  "first_name": "测试",
  "last_name": "用户",
  "phone": "13800138000",
  "employee_id": "EMP999",
  "department": 1,
  "role": 2
}
```

**API端点：**
- `GET /api/accounts/users/`
- `POST /api/accounts/users/`
- `PUT /api/accounts/users/{id}/`
- `DELETE /api/accounts/users/{id}/`

---

#### 3.2 角色管理
- [ ] 访问 http://localhost:3000/system/roles
- [ ] 查看角色列表
- [ ] 创建新角色
- [ ] 配置权限
- [ ] 测试数据权限

**API端点：**
- `GET /api/accounts/roles/`
- `POST /api/accounts/roles/`

---

#### 3.3 部门管理
- [ ] 访问 http://localhost:3000/system/departments
- [ ] 查看部门树
- [ ] 添加部门
- [ ] 编辑部门
- [ ] 删除部门

**API端点：**
- `GET /api/accounts/departments/`
- `GET /api/accounts/departments/tree/`

---

### 4. 主数据管理模块

#### 4.1 物料管理
- [ ] 访问 http://localhost:3000/masterdata/items
- [ ] 查看物料列表
- [ ] 搜索物料（SKU/名称）
- [ ] 创建新物料
- [ ] 编辑物料信息
- [ ] 生成条码
- [ ] Excel导入/导出

**测试数据：**
```json
{
  "sku": "TEST-SKU-001",
  "name": "测试物料",
  "specification": "规格说明",
  "category": 1,
  "unit": "PCS",
  "standard_cost": 100.00,
  "min_stock": 10,
  "max_stock": 1000
}
```

**API端点：**
- `GET /api/masterdata/items/`
- `POST /api/masterdata/items/`
- `GET /api/masterdata/items/{id}/generate_barcode/`

---

#### 4.2 客户管理
- [ ] 访问 http://localhost:3000/masterdata/customers
- [ ] 查看客户列表
- [ ] 创建客户
- [ ] 设置信用额度
- [ ] 启用/停用客户

**测试数据：**
```json
{
  "code": "CUST-001",
  "name": "测试客户",
  "contact_person": "张三",
  "phone": "13800138000",
  "email": "customer@example.com",
  "address": "测试地址",
  "credit_limit": 100000.00,
  "status": "ACTIVE"
}
```

**API端点：**
- `GET /api/masterdata/customers/`
- `POST /api/masterdata/customers/`

---

#### 4.3 供应商管理
- [ ] 访问 http://localhost:3000/masterdata/suppliers
- [ ] 查看供应商列表
- [ ] 创建供应商
- [ ] 设置付款条款

**API端点：**
- `GET /api/masterdata/suppliers/`
- `POST /api/masterdata/suppliers/`

---

#### 4.4 仓库管理
- [ ] 访问 http://localhost:3000/masterdata/warehouses
- [ ] 查看仓库列表
- [ ] 创建仓库
- [ ] 分配管理员

**API端点：**
- `GET /api/masterdata/warehouses/`
- `POST /api/masterdata/warehouses/`

---

### 5. 项目管理模块

#### 5.1 项目列表
- [ ] 访问 http://localhost:3000/projects
- [ ] 查看项目列表
- [ ] 筛选项目（按状态、日期）
- [ ] 创建新项目

**测试数据：**
```json
{
  "code": "PRJ-TEST-001",
  "name": "测试项目",
  "customer": 1,
  "manager": 1,
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "status": "ACTIVE",
  "budget_total": 1000000.00,
  "budget_material": 400000.00,
  "budget_labor": 300000.00,
  "budget_expense": 100000.00,
  "description": "测试项目描述"
}
```

**API端点：**
- `GET /api/projects/projects/`
- `POST /api/projects/projects/`

---

#### 5.2 项目详情
- [ ] 点击项目进入详情
- [ ] 查看项目基本信息
- [ ] 查看成本统计
- [ ] 查看预算使用情况

**API端点：**
- `GET /api/projects/projects/{id}/`
- `GET /api/projects/projects/{id}/cost_analysis/`

---

#### 5.3 项目任务
- [ ] 创建任务
- [ ] 设置父任务（多级任务树）
- [ ] 分配任务给成员
- [ ] 填报工时
- [ ] 更新进度

**测试数据：**
```json
{
  "project": 1,
  "name": "测试任务",
  "description": "任务描述",
  "assignee": 1,
  "planned_hours": 40,
  "start_date": "2025-01-01",
  "end_date": "2025-01-05",
  "status": "TODO"
}
```

**API端点：**
- `GET /api/projects/tasks/`
- `POST /api/projects/tasks/`
- `PUT /api/projects/tasks/{id}/`

---

#### 5.4 项目BOM
- [ ] 添加BOM行
- [ ] 设置物料数量
- [ ] 推送到采购

**API端点：**
- `GET /api/projects/bom/`
- `POST /api/projects/bom/`

---

#### 5.5 项目成员
- [ ] 添加成员
- [ ] 设置角色
- [ ] 设置时薪（成本计算用）

**API端点：**
- `GET /api/projects/members/`
- `POST /api/projects/members/`

---

#### 5.6 甘特图
- [ ] 访问 http://localhost:3000/projects/{id}/gantt
- [ ] 查看任务甘特图
- [ ] 拖拽调整时间
- [ ] 查看依赖关系

---

### 6. 采购管理模块

#### 6.1 采购申请（PR）
- [ ] 访问 http://localhost:3000/purchase/requests
- [ ] 创建采购申请
- [ ] 关联项目（测试预算校验）
- [ ] 添加申请行
- [ ] 提交审批

**测试数据：**
```json
{
  "request_no": "PR-TEST-001",
  "project": 1,
  "requestor": 1,
  "status": "DRAFT",
  "lines": [
    {
      "item": 1,
      "qty": 100,
      "estimated_price": 100.00
    }
  ]
}
```

**预期验证：**
- ✅ 如果关联项目，检查是否超出材料预算
- ✅ 预算不足时显示警告

**API端点：**
- `GET /api/purchase/purchase-requests/`
- `POST /api/purchase/purchase-requests/`

---

#### 6.2 RFQ（询价）
- [ ] 访问 http://localhost:3000/purchase/rfq
- [ ] 创建询价单
- [ ] 添加供应商
- [ ] 接收供应商报价
- [ ] 对比报价
- [ ] 选择中标供应商

**API端点：**
- `GET /api/purchase/rfqs/`
- `POST /api/purchase/rfqs/`
- `POST /api/purchase/supplier-quotations/`

---

#### 6.3 采购订单（PO）
- [ ] 访问 http://localhost:3000/purchase/orders
- [ ] 从PR转PO
- [ ] 选择供应商
- [ ] 确认订单

**API端点：**
- `GET /api/purchase/purchase-orders/`
- `POST /api/purchase/purchase-orders/`

---

#### 6.4 收货单
- [ ] 访问 http://localhost:3000/purchase/receipts
- [ ] 创建收货单
- [ ] 质检（通过/不通过）
- [ ] 确认入库

**预期结果：**
- ✅ 确认后自动创建库存移动
- ✅ 自动生成应付账款

**API端点：**
- `GET /api/purchase/goods-receipts/`
- `POST /api/purchase/goods-receipts/`
- `POST /api/purchase/goods-receipts/{id}/confirm/`

---

### 7. 销售管理模块

#### 7.1 销售报价
- [ ] 访问 http://localhost:3000/sales/quotations
- [ ] 创建报价单
- [ ] 版本管理
- [ ] 转销售订单

**API端点：**
- `GET /api/sales/quotations/`
- `POST /api/sales/quotations/`
- `POST /api/sales/quotations/{id}/convert_to_order/`

---

#### 7.2 销售订单（SO）
- [ ] 访问 http://localhost:3000/sales/orders
- [ ] 创建销售订单
- [ ] **必须关联项目**（收入归集）
- [ ] 添加订单行
- [ ] 确认订单

**测试验证：**
- ✅ 未选择项目时，应该无法保存

**API端点：**
- `GET /api/sales/sales-orders/`
- `POST /api/sales/sales-orders/`

---

#### 7.3 发货单
- [ ] 访问 http://localhost:3000/sales/deliveries
- [ ] 从SO创建发货单
- [ ] 选择仓库
- [ ] 确认发货

**预期结果：**
- ✅ 确认后自动扣减库存
- ✅ 自动创建库存移动
- ✅ 自动生成应收账款

**API端点：**
- `GET /api/sales/delivery-orders/`
- `POST /api/sales/delivery-orders/`
- `POST /api/sales/delivery-orders/{id}/confirm/`

---

#### 7.4 PDF发票生成
- [ ] 在销售订单详情页
- [ ] 点击"生成发票"
- [ ] 下载PDF文件
- [ ] 检查发票内容

**API端点：**
- `POST /api/sales/sales-orders/{id}/generate_invoice_pdf/`

---

### 8. 库存管理模块

#### 8.1 库存查询
- [ ] 访问 http://localhost:3000/inventory/stock
- [ ] 查看即时库存
- [ ] 按仓库筛选
- [ ] 按物料搜索
- [ ] 查看可用数量

**预期字段：**
- qty_on_hand（在手数量）
- qty_reserved（预留数量）
- qty_available（可用数量 = 在手 - 预留）

**API端点：**
- `GET /api/inventory/stock/`

---

#### 8.2 库存移动流水
- [ ] 访问 http://localhost:3000/inventory/stock-moves
- [ ] 查看所有移动记录
- [ ] 筛选移动类型
- [ ] 查看项目关联（OUT_PROJECT）

**移动类型：**
- IN_PURCHASE（采购入库）
- OUT_SALES（销售出库）
- OUT_PROJECT（项目领料）⭐
- TRANSFER（调拨）
- ADJUSTMENT（盘点）

**API端点：**
- `GET /api/inventory/stock-moves/`

---

#### 8.3 库存调拨
- [ ] 创建调拨单
- [ ] 选择源仓库
- [ ] 选择目标仓库
- [ ] 确认调拨

**API端点：**
- `POST /api/inventory/stock-moves/transfer/`

---

#### 8.4 库存盘点
- [ ] 访问 http://localhost:3000/inventory/adjustments
- [ ] 创建盘点单
- [ ] 输入账面数量
- [ ] 输入实际数量
- [ ] 系统自动计算差异
- [ ] 确认调整

**API端点：**
- `GET /api/inventory/adjustments/`
- `POST /api/inventory/adjustments/`
- `POST /api/inventory/adjustments/{id}/confirm/`

---

#### 8.5 批次管理
- [ ] 访问 http://localhost:3000/inventory/batches
- [ ] 创建批次
- [ ] 设置过期日期
- [ ] 查看批次库存

**API端点：**
- `GET /api/inventory/batches/`
- `POST /api/inventory/batches/`

---

### 9. 财务管理模块

#### 9.1 费用报销
- [ ] 访问 http://localhost:3000/finance/expenses
- [ ] 创建费用申请
- [ ] **必须关联项目或部门**
- [ ] 选择费用类别
- [ ] 提交审批

**测试验证：**
- ✅ 项目和部门必须选一个
- ✅ 两者都不选时无法保存

**API端点：**
- `GET /api/finance/expenses/`
- `POST /api/finance/expenses/`

---

#### 9.2 应收账款（AR）
- [ ] 访问 http://localhost:3000/finance/ar
- [ ] 查看应收列表
- [ ] 记录回款
- [ ] 查看逾期提醒

**预期：**
- ✅ 从销售订单自动生成
- ✅ 关联项目信息

**API端点：**
- `GET /api/finance/account-receivables/`
- `POST /api/finance/account-receivables/{id}/record_payment/`

---

#### 9.3 应付账款（AP）
- [ ] 访问 http://localhost:3000/finance/ap
- [ ] 查看应付列表
- [ ] 记录付款
- [ ] 查看逾期提醒

**预期：**
- ✅ 从采购入库自动生成

**API端点：**
- `GET /api/finance/account-payables/`
- `POST /api/finance/account-payables/{id}/record_payment/`

---

#### 9.4 多币种管理
- [ ] 访问 http://localhost:3000/finance/currencies
- [ ] 添加币种
- [ ] 设置汇率
- [ ] 多币种交易测试

**API端点：**
- `GET /api/finance/currencies/`
- `POST /api/finance/exchange-rates/`

---

### 10. 报表模块

#### 10.1 项目利润表
- [ ] 访问 http://localhost:3000/reports/project-profit
- [ ] 选择项目
- [ ] 查看收入
- [ ] 查看成本分解：
  - 材料成本（StockMove.OUT_PROJECT）
  - 人工成本（工时 × 时薪）
  - 费用成本（Expense）
- [ ] 查看利润和毛利率

**预期计算公式：**
```
收入 = SalesOrder.total_amount
材料成本 = Σ(StockMove.qty × unit_cost) where move_type=OUT_PROJECT
人工成本 = Σ(Task.actual_hours × Member.hourly_rate)
费用成本 = Σ(Expense.amount)
利润 = 收入 - (材料 + 人工 + 费用)
毛利率 = 利润 / 收入 × 100%
```

**API端点：**
- `GET /api/reports/project-profit/?project_id={id}`

---

#### 10.2 现金流预测
- [ ] 访问 http://localhost:3000/reports/cashflow
- [ ] 选择时间范围
- [ ] 查看应收预测
- [ ] 查看应付预测
- [ ] 查看资金缺口

**API端点：**
- `GET /api/finance/cashflow-forecast/`

---

### 11. 分析模块

#### 11.1 项目分析
- [ ] 访问 http://localhost:3000/analytics/projects
- [ ] 查看项目利润率排名
- [ ] 查看成本趋势图
- [ ] 查看预算执行情况

**API端点：**
- `GET /api/analytics/project-analytics/`

---

#### 11.2 库存分析
- [ ] 访问 http://localhost:3000/analytics/inventory
- [ ] 查看ABC分析
- [ ] 查看库存周转率
- [ ] 查看呆滞物料

**API端点：**
- `GET /api/analytics/inventory-analytics/`

---

### 12. 系统功能模块

#### 12.1 审计日志
- [ ] 访问 http://localhost:3000/system/audit-logs
- [ ] 查看操作日志
- [ ] 筛选用户
- [ ] 筛选操作类型
- [ ] 查看变更详情

**API端点：**
- `GET /api/core/audit-logs/`

---

#### 12.2 通知中心
- [ ] 访问 http://localhost:3000/notifications
- [ ] 查看通知列表
- [ ] 标记为已读
- [ ] 查看通知详情

**API端点：**
- `GET /api/core/notifications/`
- `PUT /api/core/notifications/{id}/mark_read/`

---

#### 12.3 全局搜索
- [ ] 点击顶部搜索框
- [ ] 输入关键词（至少2个字符）
- [ ] 查看自动完成建议
- [ ] 按回车查看完整搜索结果
- [ ] 点击结果跳转详情

**测试关键词：**
- 物料名称
- 客户名称
- 项目编码
- SKU

**API端点：**
- `GET /api/core/search/suggest/?q={keyword}`
- `GET /api/core/search/search/?q={keyword}`

---

#### 12.4 WebSocket实时通知
- [ ] 登录后自动连接WebSocket
- [ ] 在另一个浏览器窗口创建通知
- [ ] 查看是否实时弹出提醒
- [ ] 检查通知中心是否更新

**WebSocket端点：**
- `ws://localhost:3000/ws/notifications/`

---

## 🔧 常见问题处理

### 问题1：CORS错误
**现象：** 控制台显示跨域错误

**解决：** 检查 `backend/config/settings.py` CORS配置

---

### 问题2：401 未授权
**现象：** API请求返回401

**解决：**
1. 检查Token是否存在：`localStorage.getItem('access_token')`
2. 检查Token是否过期
3. 尝试重新登录

---

### 问题3：404 Not Found
**现象：** API端点不存在

**解决：**
1. 检查URL是否正确
2. 查看 `http://localhost:8000/api/docs/` 确认端点
3. 检查后端是否启动

---

### 问题4：500 服务器错误
**现象：** 服务器内部错误

**解决：**
1. 查看后端日志：`docker logs erp_backend`
2. 检查数据库迁移：`docker exec erp_backend python manage.py migrate`
3. 检查数据库连接

---

### 问题5：数据不显示
**现象：** 列表为空

**解决：**
1. 打开浏览器控制台查看Network
2. 检查API响应
3. 检查是否有初始数据
4. 可能需要先创建数据

---

## 📊 测试记录表

| 模块 | 页面 | 状态 | 问题描述 | 解决方案 |
|------|------|------|----------|----------|
| 认证 | 登录 |  |  |  |
| 仪表板 | Dashboard |  |  |  |
| 系统 | 用户管理 |  |  |  |
| 系统 | 角色管理 |  |  |  |
| 主数据 | 物料管理 |  |  |  |
| 主数据 | 客户管理 |  |  |  |
| 项目 | 项目列表 |  |  |  |
| 项目 | 项目详情 |  |  |  |
| 项目 | 甘特图 |  |  |  |
| 采购 | 采购申请 |  |  |  |
| 采购 | RFQ |  |  |  |
| 采购 | 采购订单 |  |  |  |
| 销售 | 销售订单 |  |  |  |
| 库存 | 库存查询 |  |  |  |
| 库存 | 库存移动 |  |  |  |
| 财务 | 费用报销 |  |  |  |
| 财务 | 应收应付 |  |  |  |
| 报表 | 项目利润 |  |  |  |
| 分析 | 项目分析 |  |  |  |

**状态说明：**
- ✅ 通过
- ❌ 失败
- ⚠️ 部分通过
- 🔄 测试中

---

## 🎯 测试优先级

### P0（必须通过）
1. 登录认证
2. 项目管理（核心业务）
3. 销售订单（收入归集）
4. 采购订单
5. 库存管理
6. 项目成本计算

### P1（重要）
1. 用户权限
2. 主数据管理
3. 财务模块
4. 报表查询

### P2（可选）
1. 高级搜索
2. 实时通知
3. 图表美化
4. 导入导出

---

**测试开始时间：** ___________  
**测试完成时间：** ___________  
**测试人员：** ___________

