# 精简前端

Vue 3 + TypeScript + Element Plus；九个入口，以项目串联交付和售后。所有网络调用经 src/api 和 src/utils/request.ts，JWT 刷新及退出会话统一处理。

`npm ci` 后运行 `npm run dev`，默认 18310 端口；通过 VITE_API_BASE_URL 设置 API 代理目标。

检查：`npm run lint`、`npm run typecheck`、`npm run test`、`npm run build`。

浏览器验证：`E2E_BASE_URL=http://127.0.0.1:18320 E2E_ADMIN_PASSWORD=测试管理员密码 npm run test:e2e`。必须使用隔离测试环境，测试从界面创建用户、项目、采购、库存及收付款。没有密码会失败，不会以跳过冒充通过。
