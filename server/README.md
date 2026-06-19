# server/ — ATM-ERP Go 后端(模块化单体)

> 本目录是 Go 重构的**基础脚手架**(Phase 0 地基 + 一个参考垂直切片)。
> 设计依据见 [`../docs/go-rewrite/`](../docs/go-rewrite/);本目录与旧 `backend/`(Django)在迁移期共库并行。

## 已落地

| 层 | 包 | 内容 |
|----|----|----|
| 入口 | `cmd/erpd` | cobra 多子命令:`serve` / `migrate` / `healthcheck`(后续加 `worker`/`scheduler`/`upgrade-relay`) |
| 平台内核 | `internal/platform/{config,obs,model,db,httpx}` | viper 配置(吃现有 .env 键)、slog、**BaseModel**(软删除+审计+操作人,共库 `is_deleted` 同步)、GORM/pgx 装配、DRF 风格分页信封 |
| 中间件 | `internal/middleware` | 顺序链:Recovery→RequestID→SecurityHeaders→CORS→Auth→RequirePermission;`RequireSystemAdmin` 封 system:* 越权 |
| 鉴权 | `internal/iam` | JWT(access/refresh)、**权限码父码通配**、**数据范围**(最宽+fail-closed self)、PermissionService 接口 |
| 参考切片 | `internal/masterdata/item` | model→repo→service→handler→权限→API 全链路 CRUD(软删除 + 数据范围过滤 + 分页) |

## 运行

```bash
cd server
go mod tidy          # 拉取依赖
go build ./...       # 编译
go test ./...        # 单元测试(权限通配 / 数据范围 fail-closed)

# 起服务(需可达的 PostgreSQL;键名同现有 .env)
DB_HOST=127.0.0.1 DB_PORT=5433 APP_ENV=development go run ./cmd/erpd serve
curl localhost:8000/healthz     # {"status":"ok"}
curl localhost:8000/readyz      # 探 DB 连通
```

## API(参考切片)

| 方法 | 路径 | 权限码 |
|------|------|--------|
| GET | `/api/masterdata/items` | `masterdata:item:view` |
| GET | `/api/masterdata/items/:id` | `masterdata:item:view` |
| POST | `/api/masterdata/items` | `masterdata:item:create` |
| PUT | `/api/masterdata/items/:id` | `masterdata:item:update` |
| DELETE | `/api/masterdata/items/:id` | `masterdata:item:delete`(软删除) |

## 脚手架阶段的明确边界(TODO,见迁移计划 Phase 1)

- `StaticPermissionService{Superuser:true}` 仅供本地起步;**接入真实 RBAC(GORM 查权限表)前不可用于生产**。
- 数据范围 dept / dept_tree 维度暂 fail-closed 到 self,待部门树落地。
- Casbin、Redis(缓存/限流/jti 黑名单)、asynq、WebSocket Hub、sqlc 报表层、golang-migrate embed、OpenTelemetry/Prometheus、审计落库 均为后续阶段。
- `item.TableName()="item"` 的确切表名须在共库切流前与 Django `Meta.db_table` 核对。
