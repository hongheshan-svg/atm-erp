# 🧪 ERP系统浏览器测试指南

## 📍 访问地址

| 服务 | 地址 | 说明 |
|-----|------|------|
| 🎨 前端 | http://localhost:3000 | Vue 3 开发服务器 |
| ⚙️ 后端API | http://localhost:8000/api/docs/ | Swagger API文档 |
| 👤 管理后台 | http://localhost:8000/admin/ | Django Admin |

## 🔐 默认登录信息

**管理员账号（需创建）：**
- 用户名: `admin`
- 密码: `admin123`

## 📝 测试步骤

### 1️⃣ 创建超级用户

```bash
docker exec -it erp_backend python manage.py createsuperuser
```

### 2️⃣ 登录测试页面

#### ✅ 测试1: API文档访问
- 访问: http://localhost:8000/api/docs/
- 预期: 看到Swagger UI界面，显示所有API端点

#### ✅ 测试2: 前端登录页
- 访问: http://localhost:3000
- 预期: 显示登录页面
- 输入创建的用户名和密码
- 预期: 成功登录进入仪表板

#### ✅ 测试3: 主要功能模块测试

**系统管理模块：**
- [ ] 用户管理 (/system/users)
- [ ] 角色管理 (/system/roles)
- [ ] 部门管理 (/system/departments)

**基础数据模块：**
- [ ] 物料管理 (/masterdata/items)
- [ ] 客户管理 (/masterdata/customers)
- [ ] 供应商管理 (/masterdata/suppliers)
- [ ] 仓库管理 (/masterdata/warehouses)

**项目管理模块：**
- [ ] 项目列表 (/projects)
- [ ] 创建项目
- [ ] 项目详情（含任务、成员、BOM）
- [ ] 项目甘特图

**采购管理模块：**
- [ ] 采购申请 (/purchase/requests)
- [ ] 采购订单 (/purchase/orders)
- [ ] 收货管理 (/purchase/receipts)

**销售管理模块：**
- [ ] 销售报价 (/sales/quotations)
- [ ] 销售订单 (/sales/orders)
- [ ] 发货单 (/sales/deliveries)

**库存管理模块：**
- [ ] 库存查询 (/inventory/stock)
- [ ] 库存移动记录 (/inventory/moves)
- [ ] 库存调整 (/inventory/adjustments)

**财务管理模块：**
- [ ] 费用报销 (/finance/expenses)
- [ ] 应收账款 (/finance/receivables)
- [ ] 应付账款 (/finance/payables)

**报表中心：**
- [ ] 仪表板 (/dashboard)
- [ ] KPI指标
- [ ] 项目利润报表 (/reports/project-profit)
- [ ] 现金流预测 (/reports/cashflow)
- [ ] 项目分析 (/analytics/projects)
- [ ] 库存分析 (/analytics/inventory)

## 🔍 浏览器测试重点

### 功能测试
1. **创建操作**: 测试表单验证、必填项
2. **查询操作**: 测试搜索、过滤、排序、分页
3. **编辑操作**: 测试数据回显、更新保存
4. **删除操作**: 测试删除确认、软删除
5. **导入导出**: 测试Excel导入导出功能

### 页面测试
1. **响应式设计**: 测试不同屏幕尺寸
2. **加载速度**: 观察页面加载时间
3. **错误处理**: 测试网络错误、权限错误
4. **用户体验**: 测试操作流畅性、提示信息

### 业务流程测试

#### 完整采购流程
1. 创建采购申请
2. 审批采购申请
3. 转为采购订单
4. 记录收货
5. 查看库存增加

#### 完整销售流程
1. 创建销售报价
2. 转为销售订单
3. 创建发货单
4. 确认发货
5. 查看库存减少
6. 查看应收账款生成

#### 项目成本核算流程
1. 创建项目并设置预算
2. 项目领用材料（生成出库单）
3. 记录项目工时
4. 提交项目费用
5. 查看项目成本报表

## 📊 预期结果

✅ 所有页面正常加载  
✅ API调用成功  
✅ 数据正常显示  
✅ CRUD操作正常  
✅ 业务流程完整  
✅ 报表计算准确  

## ❌ 常见问题排查

### 问题1: 前端无法连接后端
- 检查后端服务状态: `docker ps | grep erp_backend`
- 查看后端日志: `docker logs erp_backend`
- 检查CORS配置

### 问题2: 页面报错
- 打开浏览器控制台查看错误信息
- 检查Network请求状态
- 查看前端日志: `docker logs erp_frontend`

### 问题3: 数据不显示
- 检查是否有初始数据
- 查看API响应: 访问 http://localhost:8000/api/docs/ 手动测试API
- 检查数据库数据: `docker exec -it erp_db psql -U erp_user -d erp_db`

## 📝 测试记录模板

```
测试日期: YYYY-MM-DD
测试人员: 
浏览器: Chrome/Firefox/Safari

| 模块 | 功能 | 状态 | 备注 |
|------|------|------|------|
| 登录 | 用户登录 | ✅/❌ |  |
| 仪表板 | 数据显示 | ✅/❌ |  |
| 用户管理 | 新增用户 | ✅/❌ |  |
| ... | ... | ... | ... |

发现的问题:
1. 
2. 
3. 
```

## 🚀 快速测试命令

```bash
# 1. 查看所有服务状态
docker-compose ps

# 2. 查看日志
docker logs erp_backend --tail 50
docker logs erp_frontend --tail 50

# 3. 进入后端容器
docker exec -it erp_backend bash

# 4. 进入数据库
docker exec -it erp_db psql -U erp_user -d erp_db

# 5. 重启服务
docker-compose restart backend frontend

# 6. 查看网络
docker network inspect python-erp_default
```

---

**开始测试前请确保：**
1. ✅ 所有Docker容器正在运行
2. ✅ 已创建超级用户
3. ✅ 数据库迁移已完成
4. ✅ 前端开发服务器已启动
