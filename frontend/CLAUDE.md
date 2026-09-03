# Frontend 约定（`frontend/`）

Vue 3 + TypeScript 前端。以下约定不可从代码直接推断，改动前必读。

## 网络层

- 网络调用统一走 `frontend/src/utils/request.ts`（封装 JWT 刷新、401 排队重试、错误码提示）。
- 新接口在 `frontend/src/api/<module>.ts` 中按模块组织。
- **不要在视图组件里直接 `import axios`**。

## 权限三件套

路由 `meta.permission` 控制页面访问、`usePermissionStore().hasPermission()` 用于逻辑判断、`v-permission` 指令控制元素可见性——**三者权限标识必须一致**。后端 API 契约变化要同步前端 API 封装与权限测试。

## 路由前缀

Vite `base: '/erp/'` 与 nginx 路由一致，**所有路由路径需带 `/erp/` 前缀**。开发服务器跑在端口 3000，启动后访问 `http://localhost:3000/erp/`（不是根路径）。

Vite 已配置 `/api` 与 `/ws` 反向代理到 `http://backend:8000`（Docker 内）或 `VITE_API_BASE_URL`（本地需 export）。

## TypeScript

前端已迁移至 TypeScript，新文件用 `.ts`/`.vue`（`script lang="ts"`），遵循已有类型定义。
