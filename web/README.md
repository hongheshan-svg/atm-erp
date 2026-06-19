# ATM-ERP Web(Go 重写版前端)

面向 ATM-ERP Go 重写后端的全新前端 SPA 工程基座。与旧 `frontend/` 完全独立。

## 技术栈

- Vue 3.5(Composition API)+ TypeScript(strict)
- Vite 6 + pnpm
- Element Plus(UI)、vxe-table(表格)
- Pinia(状态)、vue-router(路由)
- @tanstack/vue-query(服务端状态/缓存)
- axios(HTTP,封装在 `src/utils/request.ts`)

## 目录结构

```
web/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts          # base '/erp/',端口 3001,/api 与 /ws 代理到 :8000
├── env.d.ts
└── src/
    ├── main.ts             # 挂载 Vue + Pinia + router + Element Plus + vxe-table + VueQuery + v-permission
    ├── App.vue
    ├── api/
    │   ├── auth.ts         # login / refresh / profile
    │   └── masterdata.ts   # items CRUD + TanStack Query 封装
    ├── components/         # PageHeader / SearchForm
    ├── directives/
    │   └── permission.ts   # v-permission(无权限隐藏,watchEffect 响应)
    ├── layout/
    │   └── MainLayout.vue  # 侧边菜单按权限裁剪 + 顶栏
    ├── router/
    │   └── index.ts        # 懒加载 + meta.permission + beforeEach 守卫
    ├── stores/
    │   ├── user.ts         # token / profile
    │   ├── permission.ts   # Set 存权限,hasPermission(* + 精确 + 父码通配)
    │   └── companyConfig.ts
    ├── types/
    │   └── index.ts        # 后端契约类型
    ├── utils/
    │   └── request.ts      # axios 封装(JWT 刷新 + 401 排队重试 + 解包 + blob 透传)
    └── views/
        ├── Login.vue
        ├── Dashboard.vue
        └── masterdata/ItemList.vue
```

## 后端契约对齐

- 分页信封:`{ count, next, previous, results }`(`server/internal/platform/httpx.Page`)
- 错误体:`{ detail }`(`httpx.Error`)
- 物料 REST:`/api/masterdata/items`,权限码 `masterdata:item:view|create|update|delete`
- 认证(前瞻):`POST /api/auth/login`、`POST /api/auth/refresh`、`GET /api/auth/profile`
- 新后端监听 `:8000`;dev 代理 `/api`、`/ws` 至 `http://localhost:8000`

## 权限三件套

- 路由 `meta.permission` 控制页面访问
- `usePermissionStore().hasPermission(code)` 逻辑判断(支持 `*`、精确、父码通配 `a:b:c → a:b → a`)
- `v-permission` 指令控制元素可见性

三者权限标识需保持一致。

## 启动方式

```bash
cd web
pnpm install
pnpm dev          # 启动开发服务器(端口 3001,访问 http://localhost:3001/erp/)
pnpm typecheck    # vue-tsc --noEmit(strict)
pnpm build        # 类型检查 + 生产构建,产物在 dist/
pnpm preview      # 预览构建产物
```

dev 启动前确保 Go 后端在 `:8000` 运行;否则 `/api` 代理会失败。可用
`VITE_API_BASE_URL` 覆盖代理目标。
