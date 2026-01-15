# 系统截图目录

此目录用于存放ERP系统的截图，用于生成操作手册Word文档。

## 截图命名规范

请按以下文件名保存截图（PNG格式）：

| 文件名 | 说明 | 对应页面路径 |
|--------|------|-------------|
| login.png | 登录页面 | /login |
| dashboard.png | 工作台 | /dashboard |
| customer_list.png | 客户列表 | /customers |
| customer_form.png | 客户表单 | 新建/编辑客户弹窗 |
| leads.png | 销售线索列表 | /sales/leads |
| opportunities.png | 销售商机 | /sales/opportunities |
| quotation.png | 销售报价 | /sales/quotations |
| project_list.png | 项目列表 | /projects |
| project_form.png | 项目表单 | 新建/编辑项目弹窗 |
| task_list.png | 任务列表 | /projects/tasks |
| gantt.png | 甘特图 | /projects/gantt |
| bom_list.png | BOM列表 | /projects/bom |
| drawings.png | 图纸管理 | /projects/drawings |
| purchase_request.png | 采购申请 | /purchase/requests |
| purchase_order.png | 采购订单 | /purchase/orders |
| goods_receipt.png | 到货质检 | /purchase/goods-receipts |
| sales_order.png | 销售订单列表 | /sales/orders |
| delivery.png | 发货管理 | /sales/delivery-orders |
| supplier_list.png | 供应商列表 | /suppliers |
| inventory.png | 库存查询 | /inventory/stocks |
| expense.png | 费用报销 | /finance/expenses |
| production_plan.png | 生产计划 | /production/plans |
| equipment.png | 设备台账 | /equipment/list |
| workflow.png | 待办审批 | /workflow/tasks |
| user_list.png | 用户管理 | /users |
| role_list.png | 角色管理 | /roles |
| profile.png | 个人中心 | /profile |
| reports.png | 报表分析 | 任意报表页面 |
| system_architecture.png | 系统架构图 | （手动绘制） |

## 截图建议

1. **分辨率**：建议使用 1920×1080 或更高分辨率
2. **浏览器**：使用 Chrome 浏览器截图，保持一致性
3. **内容**：截图应包含有意义的示例数据
4. **隐私**：确保截图中不包含敏感信息

## 重新生成文档

添加截图后，运行以下命令重新生成Word文档：

```bash
cd /home/administrator/erp/docs
python3 generate_word.py
```

生成的文档将保存在 `output/` 目录。
