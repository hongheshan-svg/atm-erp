# ATM-ERP Go 重构 · 架构设计文档

> 由动态架构工作流(43 个 agent:11 域分析 ∥ 4×技术栈方案+评审团 → 11 上下文 + 10 跨域设计 → 综合蓝图 → 完备性评审)产出。
> 范围:**后端 Go 模块化单体重写 + 全新 Vue SPA**,复用现有 PostgreSQL 15 / Redis 7 与既有 Docker 升级链路。

## 文档索引

| 文件 | 内容 |
|------|------|
| [00-overview.md](./00-overview.md) | 架构总览(目标/原则/整体架构图/模块边界)+ 目标目录布局 |
| [01-tech-stack.md](./01-tech-stack.md) | 技术栈决策(Gin + GORM/sqlc + pgx;Vue3.5+Vite6+TanStack Query;asynq/PG 全文检索) |
| [10-current-state.md](./10-current-state.md) | 现状 11 限界上下文域分析(基线) |
| [20-module-designs.md](./20-module-designs.md) | 21 份模块与跨域设计(含权限简化、自动升级、数据迁移、安全、前端、性能…) |
| [30-migration-plan.md](./30-migration-plan.md) | 分阶段迁移计划(Phase 0-4,先地基后切片、可回滚) |
| [40-adr.md](./40-adr.md) | 12 条架构决策记录(ADR) |
| [50-gaps-risks.md](./50-gaps-risks.md) | 完备性评审:缺口 / 风险 / **必修项** |

## 核心结论速览

- **后端**:Go 1.23 + Gin + GORM(主 CRUD)/sqlc(报表聚合)/Squirrel(动态筛选) + pgx/v5;golang-jwt + Casbin(menu RBAC)+ **数据范围/字段脱敏手写**;go-redis + asynq(替 Celery+Beat)+ coder/websocket(替 Channels)+ PG tsvector(替 ES)。
- **前端**:另起新 SPA,沿用 Vue 3.5 + Element Plus,换 Vite 6 + pnpm + TS strict,补 TanStack Query + vxe-table;`request.ts` 三件套契约 1:1 复刻;196 视图增量迁移、双栈并存。
- **数据**:**共库共表**,Django 迁移冻结、golang-migrate 只接管增量;`gorm.DeletedAt` ↔ `deleted_at` + 钩子同步 `is_deleted`,保证两栈软删除互认。
- **升级**:沿用 erp-updater + manifest digest(MODE_DOCKER),修复同路径挂载缺陷、补全原生升级;Go 产物为 distroless 静态二进制。
- **权限简化**:删 operation/field 三级死代码与 `MODULE_MENU_MAP` 兜底放行;RBAC 扁平为单层;`RequireSystemAdmin` 前置封死 system:* 越权(C1)。

## 落地阶段(本分支当前进度)

1. ✅ 架构重设计工作流 + 设计文档(本目录)
2. ⏳ Go 基础脚手架(`server/`:platform/middleware/iam/core 内核)
3. ⏳ 参考垂直切片(masterdata)
4. ⏳ 新 SPA 工程基座(`web/`)
