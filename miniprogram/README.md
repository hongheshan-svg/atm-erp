# ERP 微信小程序 - 移动审批

基于微信小程序的ERP移动端，支持随时随地进行审批和查看关键业务数据。

## 功能特性

### 📋 移动审批
- 待办审批列表
- 审批详情查看
- 一键通过/拒绝
- 审批意见填写
- 撤回申请

### 📁 项目管理
- 项目列表浏览
- 项目详情查看
- 预算使用情况
- 任务进度跟踪

### 📊 数据看板
- 财务概览（收入/支出/应收/应付）
- 项目统计
- 库存概览
- 现金流预测

### 👤 个人中心
- 工作统计
- 快捷入口
- 退出登录

## 快速开始

### 1. 配置后端API地址

修改 `app.js` 中的 `baseUrl`：

```javascript
globalData: {
  baseUrl: 'https://your-erp-domain.com/api', // 替换为实际API地址
}
```

### 2. 配置小程序AppID

修改 `project.config.json` 中的 `appid`：

```json
{
  "appid": "your-appid-here"
}
```

### 3. 后端CORS配置

确保后端Django配置允许小程序域名访问：

```python
# settings.py
CORS_ALLOWED_ORIGINS = [
    "https://servicewechat.com",  # 微信小程序
]
```

### 4. 导入微信开发者工具

1. 下载并安装 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
2. 选择"导入项目"
3. 选择 `miniprogram` 目录
4. 填入AppID
5. 点击"导入"

## 目录结构

```
miniprogram/
├── app.js                 # 小程序入口
├── app.json               # 全局配置
├── app.wxss               # 全局样式
├── pages/
│   ├── index/             # 首页（工作台）
│   ├── login/             # 登录页
│   ├── approval/          # 审批相关
│   │   ├── list           # 审批列表
│   │   └── detail         # 审批详情
│   ├── project/           # 项目相关
│   │   ├── list           # 项目列表
│   │   └── detail         # 项目详情
│   ├── dashboard/         # 数据看板
│   └── profile/           # 个人中心
├── images/                # 图片资源（需自行添加）
└── project.config.json    # 项目配置
```

## 图片资源

需要在 `images/` 目录下添加以下图片：

- `logo.png` - 登录页Logo
- `home.png` / `home-active.png` - 首页Tab图标
- `approval.png` / `approval-active.png` - 审批Tab图标
- `project.png` / `project-active.png` - 项目Tab图标
- `profile.png` / `profile-active.png` - 我的Tab图标

建议图片尺寸：81x81px

## API接口依赖

小程序依赖以下后端API：

| 接口 | 说明 |
|------|------|
| POST /accounts/login/ | 用户登录 |
| GET /core/workflow/tasks/my_pending/ | 待审批任务 |
| GET /core/workflow/tasks/pending_count/ | 待审批数量 |
| POST /core/workflow/tasks/{id}/approve/ | 通过审批 |
| POST /core/workflow/tasks/{id}/reject/ | 拒绝审批 |
| GET /core/workflow/instances/my_submitted/ | 我提交的 |
| POST /core/workflow/instances/{id}/withdraw/ | 撤回申请 |
| GET /projects/ | 项目列表 |
| GET /projects/{id}/ | 项目详情 |
| GET /projects/{id}/summary/ | 项目统计 |
| GET /analytics/dashboard/kpis/ | KPI数据 |
| GET /analytics/dashboard/cash-flow-forecast/ | 现金流预测 |

## 注意事项

1. **HTTPS要求**：微信小程序要求所有网络请求必须使用HTTPS
2. **域名备案**：API域名需要在微信公众平台配置为合法域名
3. **登录态**：使用JWT Token进行身份验证，Token存储在本地Storage

## 发布上线

1. 在微信开发者工具中点击"上传"
2. 登录 [微信公众平台](https://mp.weixin.qq.com/) 
3. 进入"版本管理"提交审核
4. 审核通过后发布

## 技术支持

如有问题，请联系系统管理员。
