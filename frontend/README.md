# ERP 系统前端

基于 Vue 3 + Element Plus 的企业资源计划系统前端。

## 技术栈

- **Vue 3** - 渐进式 JavaScript 框架
- **Vite** - 下一代前端构建工具
- **Element Plus** - 基于 Vue 3 的组件库
- **Vue Router** - 官方路由管理器
- **Pinia** - Vue 状态管理
- **Axios** - HTTP 客户端
- **ECharts** - 数据可视化库

## 项目结构

```
frontend/
├── public/             # 静态资源
├── src/
│   ├── api/           # API 接口
│   ├── assets/        # 资源文件
│   ├── components/    # 公共组件
│   ├── layout/        # 布局组件
│   ├── router/        # 路由配置
│   ├── stores/        # Pinia 状态管理
│   ├── utils/         # 工具函数
│   ├── views/         # 页面组件
│   ├── App.vue        # 根组件
│   └── main.js        # 入口文件
├── index.html
├── vite.config.js     # Vite 配置
└── package.json
```

## 安装与运行

### 1. 安装依赖

```bash
npm install
# 或
yarn install
```

### 2. 开发环境运行

```bash
npm run dev
# 或
yarn dev
```

访问 http://localhost:5173

### 3. 生产构建

```bash
npm run build
# 或
yarn build
```

### 4. 预览生产构建

```bash
npm run preview
# 或
yarn preview
```

## 功能模块

### 1. 系统管理
- 用户管理
- 角色管理
- 部门管理

### 2. 基础数据
- 物料管理
- 客户管理
- 供应商管理
- 仓库管理

### 3. 项目管理
- 项目列表
- 项目详情
- 任务管理
- 成员管理
- BOM 管理

### 4. 采购管理
- 采购申请
- 采购订单
- 收货管理

### 5. 销售管理
- 销售报价
- 销售订单
- 发货管理

### 6. 库存管理
- 库存查询
- 库存移动
- 库存调整

### 7. 财务管理
- 费用报销
- 应收账款
- 应付账款

### 8. 报表中心
- 项目利润分析
- 成本明细报表
- 仪表盘

## 开发规范

### 1. 代码风格

- 使用 ES6+ 语法
- 使用 Composition API
- 组件名使用 PascalCase
- 方法名使用 camelCase

### 2. 文件命名

- 组件文件：PascalCase (例如：UserList.vue)
- 工具文件：camelCase (例如：request.js)
- Store 文件：camelCase (例如：user.js)

### 3. 提交规范

- feat: 新功能
- fix: 修复 bug
- docs: 文档更新
- style: 代码格式
- refactor: 重构
- test: 测试
- chore: 构建/工具

## 环境变量

创建 `.env.local` 文件配置本地环境变量：

```
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_TITLE=ERP管理系统
```

## 常见问题

### 1. 安装依赖失败

尝试清除缓存：
```bash
rm -rf node_modules
rm package-lock.json
npm install
```

### 2. 开发服务器端口被占用

修改 `vite.config.js` 中的端口配置

### 3. API 请求跨域

确保后端已配置 CORS，或使用 Vite 代理

## 许可证

MIT License

