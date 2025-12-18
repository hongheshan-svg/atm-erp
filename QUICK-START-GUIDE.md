# 🚀 ERP系统 - 快速入门指南

## ⚡ **快速开始**

### 1. 部署系统
```bash
# 上传项目到Ubuntu服务器
scp erp-system.tar.gz user@server:/tmp/

# 登录服务器
ssh user@server

# 解压并安装
cd /tmp
tar -xzvf erp-system.tar.gz
cd erp-system
sudo bash install.sh
```

### 2. 访问系统
- **前端界面:** http://服务器IP
- **后台管理:** http://服务器IP/admin
- **API接口:** http://服务器IP/api/

### 3. 登录
- **用户名:** `admin`
- **密码:** `admin123`

---

## 🎯 **核心功能**

### 📊 **1. 管理仪表盘**
**路径:** 登录后首页

**功能:**
- 总收入、活跃项目、库存价值、现金头寸
- 现金流预测图表（30天）
- 项目完成率饼图
- 系统告警提醒

---

### 📈 **2. 项目分析**
**路径:** 分析 → 项目分析

**功能:**
- 项目状态分布图
- 利润率分析
- 成本结构分解（材料/人工/费用）
- Top 10项目绩效表

---

### 📦 **3. 库存分析**
**路径:** 分析 → 库存分析

**功能:**
- 各仓库库存价值
- 周转率计算
- 滞销品清单
- ABC分析

---

### 📋 **4. 项目甘特图**
**路径:** 项目 → 项目甘特图

**功能:**
- 可视化项目时间线
- 任务状态颜色标识
- 任务进度跟踪
- 交互式操作

---

### 💰 **5. 多币种财务**
**路径:** 财务 → 币种管理

**功能:**
- 添加/编辑币种
- 更新汇率
- 查看汇率历史
- 设置基础币种

---

### 📄 **6. PDF发票生成**
**路径:** 销售 → 销售订单 → 选择订单 → 操作

**功能:**
- 专业PDF发票
- 公司品牌标识
- 明细项目与合计
- 可下载PDF

---

### 🔍 **7. 条码/二维码生成**
**路径:** 主数据 → 物料 → 选择物料 → 操作

**功能:**
- 生成条形码（CODE128）
- 生成二维码（JSON数据）
- 可下载PNG图片
- 支持打印/扫描

---

### 📦 **8. 批次追踪**
**路径:** 库存 → 批次管理

**功能:**
- 创建带有效期的批次
- 查看即将过期物料
- 跟踪批次移动
- 质量状态管理
- FEFO（先过期先出）

---

### 📬 **9. 询价系统（RFQ）**
**路径:** 采购 → 询价单

**功能:**
- 创建询价请求
- 发送给多个供应商
- 接收并比较报价
- 接受最优报价
- 转换为采购订单

---

### 🔔 **10. 通知中心**
**路径:** 右上角铃铛图标

**功能:**
- 系统通知
- 未读数量徽章
- 标记已读/未读
- 按类型筛选

---

### 🔍 **11. 审计日志**
**路径:** 系统 → 审计日志

**功能:**
- 完整系统变更历史
- 按用户、操作、日期筛选
- 查看详细变更（JSON）
- IP地址追踪

---

## 🛠️ **常用操作**

### 创建新项目
1. 项目 → 创建项目
2. 填写：名称、客户、经理、日期、预算
3. 添加项目成员
4. 添加BOM（物料清单）
5. 创建任务（WBS结构）
6. 在甘特图中查看

### 采购流程
1. **采购申请** → 创建PR并添加物料
2. **转换为PO** → 选择供应商
3. **收货** → 接收物料
4. **库存移动** → 自动创建（物料入库）

### 销售流程
1. **报价单** → 创建并发送给客户
2. **转换为SO** → 客户接受
3. **发货单** → 发运物料
4. **发票** → 生成PDF
5. **应收账款** → 自动创建

### 库存管理
1. **库存查询** → 检查可用量
2. **库存调整** → 盘点
3. **库存调拨** → 仓库间转移
4. **批次追踪** → 有效期管理

---

## 🔧 **系统管理**

### 查看服务状态
```bash
# 使用管理脚本（推荐）
sudo /opt/erp/scripts/manage-native.sh

# 或使用systemctl
sudo systemctl status erp-backend
sudo systemctl status erp-celery
sudo systemctl status nginx
sudo systemctl status postgresql
sudo systemctl status redis-server
```

### 查看日志
```bash
# 应用日志
sudo tail -f /var/log/erp/gunicorn-error.log

# Nginx日志
sudo tail -f /var/log/nginx/error.log

# 系统服务日志
sudo journalctl -u erp-backend -f
```

### 重启服务
```bash
# 重启所有服务
sudo systemctl restart erp-backend erp-celery nginx

# 重启特定服务
sudo systemctl restart erp-backend
```

### 停止系统
```bash
# 停止应用服务
sudo systemctl stop erp-backend erp-celery erp-celery-beat
```

---

## 💾 **数据备份**

```bash
# 数据库备份
sudo -u postgres pg_dump erp_db > backup_$(date +%Y%m%d).sql

# 恢复数据库
sudo -u postgres psql erp_db < backup.sql

# 使用管理脚本备份
sudo /opt/erp/scripts/manage-native.sh backup
```

---

## 🆘 **故障排除**

### 前端无法加载
```bash
# 检查Nginx状态
sudo systemctl status nginx
sudo nginx -t

# 检查前端文件
ls -la /var/www/erp/
```

### 后端错误
```bash
# 检查后端服务
sudo systemctl status erp-backend
sudo tail -f /var/log/erp/gunicorn-error.log
```

### 数据库连接错误
```bash
# 检查PostgreSQL
sudo systemctl status postgresql
sudo -u postgres psql -c "\l"
```

### 502 Bad Gateway
```bash
# 重启后端服务
sudo systemctl restart erp-backend
```

---

## 📚 **文档**

- **部署指南:** `UBUNTU-NATIVE-DEPLOYMENT.md`
- **快速部署参考:** `QUICK-DEPLOY-CARD.md`
- **系统架构:** `SYSTEM-ARCHITECTURE.md`
- **安全指南:** `SECURITY-PERFORMANCE-GUIDE.md`

---

## 🌟 **快捷操作**

| 页面 | 操作 |
|------|------|
| 仪表盘 | 点击左上角Logo |
| 创建物料 | 主数据 → 物料 → + 新建 |
| 查看库存 | 库存 → 库存查询 |
| 新建项目 | 项目 → + 创建 |
| 通知 | 右上角铃铛图标 |
| 审计日志 | 系统菜单 |
| 退出 | 右上角用户头像 |

---

## ✨ **使用技巧**

1. **善用搜索** - 大多数页面都有搜索框
2. **导出Excel** - 很多表格有导出按钮
3. **每日检查通知** - 系统告警很重要
4. **查看审计日志** - 追踪所有变更
5. **定期备份** - 使用管理脚本备份数据

---

## 🎉 **开始使用！**

系统已完整部署，包含：
- ✅ 16个主要功能模块
- ✅ 35+ API接口
- ✅ 22个前端页面
- ✅ 实时数据分析
- ✅ 自动化工作流
- ✅ 完整审计追踪

**开始探索现代化ERP系统的强大功能吧！🚀**

---

*版本: 1.0.0 | 更新日期: 2024年12月*
