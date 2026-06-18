# 设计文档：ERP 软件版本远程升级

- **日期**：2026-06-18
- **状态**：已确认，待编写实现计划
- **参考**：`/Users/zhengshan/projects/sub2api`（`backend/internal/service/update_service.go`、`handler/admin/system_handler.go` 的 check/perform/rollback/restart 模式）

## 1. 目标与背景

让管理员在 ERP 后台**一键远程升级**整套系统，**同时支持 Docker 与原生 systemd 两种部署**。
借鉴 sub2api「检查更新 → 执行 → 回滚 → 进度」模式，但 sub2api 是单 Go 二进制（自替换+重启），
而 ERP 是 Django + Vue 多容器/多进程应用，无法「替换二进制」。因此 apply 机制改为：
**厂商发布清单（公开 JSON）+ 宿主升级代理（特权边界）**。

核心难点与对策：
- **容器内后端无法干净地重建自己**（在 backend 容器里 `docker compose up -d` 会杀掉执行升级的进程）
  → 由**独立于应用容器/进程的宿主代理**执行真正的拉取+重建+迁移+重启。
- **进度会熬过后端重启** → 代理把进度/状态持久写入 Redis + DB，UI 断线后改读持久任务状态。

### 非目标（YAGNI）
- 不做灰度/分批发布、不做 A/B、不做增量补丁（按整版升级）。
- 不做多实例集群编排升级（面向单实例 on-prem 部署）。
- 不在本期内实现 Windows 原生升级（Windows 仅 Docker 形态，复用 Docker 分支）。

## 2. 关键决策（已确认）

| 决策 | 选择 |
|------|------|
| 目标部署形态 | Docker 与原生 systemd **都支持**（代理按 `DEPLOY_MODE` 分支） |
| 升级源 | **厂商发布清单**（公开 JSON），实例轮询 |
| 执行模型 | **宿主升级代理**（特权）；后端只校验+投递+推进度 |
| 清单托管 | **公开仓库** `hongheshan-svg/atm-erp` 的 raw |
| 清单默认 URL | `https://raw.githubusercontent.com/hongheshan-svg/atm-erp/main/manifest.json`（env `ERP_UPDATE_MANIFEST_URL` 可覆盖） |
| 升级前 DB 快照 | 默认**每次 `pg_dump` 全量快照**（可配置阈值/保留份数） |
| 健康门不过 | 默认**自动回滚** |

## 3. 架构总览

```
  厂商发布清单 (公开 JSON, raw.githubusercontent.com)
        ▲ ① 检查更新 (Redis 缓存 ~20min)
  ERP Backend (Django) ──② 投递升级任务──► Redis ──③ 取任务/执行──► 宿主升级代理 (特权)
   upgrade service+API    ◄──④ 进度(持久)── 队列+进度 ◄──────────────  Docker: erp-updater 容器(挂 docker.sock)
   Channels 推进度                                                     原生:  erp-updater root systemd
        ▲ ⑤ UI 读持久任务状态(熬过后端重启)                            备份DB→拉新→迁移→健康门→失败回滚
  前端「系统升级」页
```

后端**只**做：校验、单飞锁、建 `UpgradeJob`、投递任务、读/推进度。
代理**做**：真正的拉取 + 重建/重启 + 迁移 + 健康门 + 回滚，并持久写进度。

## 4. 组件与文件结构

| 单元 | 位置 | 责任 |
|------|------|------|
| 升级服务 | `backend/apps/core/services/upgrade_service.py` | 检查更新、比较版本、清单解析、建/查 job、投递任务、单飞锁 |
| 数据模型 | `backend/apps/core/models.py`（追加 `UpgradeJob`） | 升级任务持久记录 |
| API 视图 | `backend/apps/core/views/upgrade.py` | admin 端点（见 §6），`PermissionMixin` 权限 `system:upgrade` |
| 路由 | `backend/apps/core/urls.py`（追加） | `/api/v1/system/...` |
| WS 推进度 | `backend/apps/core/consumers.py`（或复用现有 Channels） | 升级进度实时推送 |
| 宿主代理(核心) | `deploy/updater/agent.py` | Redis 取任务 + 备份/健康门/回滚通用逻辑 + 两分支 |
| 代理 Docker 形态 | `docker-compose.yml` 追加 `erp-updater` 服务 + `docker/updater/Dockerfile` | 挂 docker.sock + 项目目录 |
| 代理原生形态 | `deploy/updater/erp-updater.service` + 安装钩子写入 `deploy-native-ubuntu.sh` | root systemd 助手 |
| 版本/模式注入 | compose env / 原生部署写 `VERSION`；改 `backend/config/urls.py` 的 health | `APP_VERSION` / `DEPLOY_MODE` |
| 前端页面 | `frontend/src/views/system/Upgrade.vue` | 检查/升级/进度/回滚/历史 |
| 前端 API | `frontend/src/api/system.ts`（追加） | 调用升级端点 |
| 权限种子 | `init_permissions` 追加 `system:upgrade` | RBAC |

## 5. 宿主升级代理（两形态，同一任务循环）

代理 `BRPOP` Redis 队列 `erp:upgrade:queue` 取任务 `{id, action, target_version, mode, manifest}`，
执行并把每一步进度/状态写回 Redis `erp:upgrade:progress:<id>` **且**更新 DB `UpgradeJob`（持久）。

**通用步骤（备份/健康门/回滚共用）**：
1. 预检：模式探测、磁盘空间、`target>current` 且满足 `min_upgradable_from`、单飞锁仍持有。
2. `pg_dump` 全量快照到带时间戳文件（`db_backup_path` 记入 job；保留 N 份）。
3. 拉取并校验产物完整性（见 §7）。
4. 应用（见下分支）。
5. **健康门**：轮询 `http://<backend>/api/v1/health/` 最长 N 分钟（可配），且校验返回的 `version` == 目标版本。
6. 健康 → `status=success`；任一步失败/健康门不过 → **回滚** → `status=rolled_back` 或 `failed`。

**Docker 分支**：
- 改 `.env` 的 `IMAGE_TAG`（记录旧值）→ `docker compose pull`（按 digest 校验）→ `docker compose up -d`（entrypoint 自动迁移）→ 健康门。
- 回滚：恢复旧 `IMAGE_TAG` → `docker compose up -d`；若迁移已执行且不兼容，按需 `pg_restore` 快照。

**原生分支**：
- 下载发布 tar（校验 sha256）→ 解到新发布目录 → `pip install` / 用预构建前端产物 → `migrate` + `collectstatic` → `systemctl restart erp-backend erp-celery erp-celery-beat` → 健康门。
- 回滚：切回旧发布目录/符号链接 + 必要时 `pg_restore` → 重启。

**模式探测**：环境变量 `DEPLOY_MODE=docker|native`（Docker 由 compose 注入；原生由 `deploy-native-ubuntu.sh` 写入）。

## 6. 后端 API（admin，权限 `system:upgrade`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/system/version` | 当前 `APP_VERSION` + `DEPLOY_MODE` |
| GET | `/api/v1/system/check-update?force=` | 拉清单（Redis 缓存 ~20min）、比版本、返回更新说明 + `min_upgradable_from` 校验 |
| POST | `/api/v1/system/upgrade` | 校验 + 单飞锁 + 建 `UpgradeJob` + 投递任务，立即返回 `{job_id}` |
| GET | `/api/v1/system/upgrade/jobs/<id>` | 单个任务状态/步骤日志（持久，供 UI 熬过重启） |
| GET | `/api/v1/system/upgrade/jobs` | 升级历史 |
| POST | `/api/v1/system/rollback` | 投递回滚任务（回到上一个成功版本） |

幂等：`upgrade`/`rollback` 走 Redis 单飞锁，重复触发返回进行中的 `job_id`，不新建。

## 7. 发布清单格式 + 完整性校验

公开 JSON 示例：
```json
{
  "latest_version": "0.3.0",
  "published_at": "2026-07-01T00:00:00Z",
  "release_notes_md": "## 0.3.0\n- ...",
  "min_upgradable_from": "0.2.0",
  "docker": {
    "registry": "ghcr.io", "owner": "hongheshan-svg", "image_tag": "0.3.0",
    "digests": { "backend": "sha256:...", "frontend": "sha256:..." }
  },
  "native": { "tarball_url": "https://github.com/hongheshan-svg/atm-erp/releases/download/v0.3.0/erp-0.3.0.tar.gz", "sha256": "..." }
}
```
- **版本比较**：semver 整型分段比较（同 sub2api `compareVersions`），去前导 `v`。
- **完整性**：Docker 用 `digests` 钉死镜像；原生校验 tar 的 `sha256`。
- **SSRF 防护**：清单与产物 URL 只允许 HTTPS + 可信主机白名单：`raw.githubusercontent.com`、
  `github.com`、`objects.githubusercontent.com`、`ghcr.io`。

## 8. 数据模型 `UpgradeJob`（继承 `BaseModel`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | choice | `upgrade` / `rollback` |
| `from_version` | char | 升级前版本 |
| `target_version` | char | 目标版本 |
| `mode` | choice | `docker` / `native` |
| `status` | choice | `pending`/`running`/`healthcheck`/`success`/`failed`/`rolled_back` |
| `steps` | JSON | 步骤日志数组（时间戳 + 阶段 + 消息 + 级别） |
| `db_backup_path` | char | 本次 `pg_dump` 文件路径 |
| `started_at`/`finished_at` | datetime | |
| `triggered_by` | FK(User) | 触发人（审计） |

审计：经 `AuditLogMiddleware` + `triggered_by` 记录谁/何时/从哪到哪/结果。

## 9. 版本与部署模式来源

- `APP_VERSION`：Docker = 镜像 tag（compose 注入 env）；原生 = 部署时写入的 `VERSION` 文件。
  替换 `backend/config/urls.py` 中 `api_health_check` 硬编码的 `'1.0.0'` 为读取 `APP_VERSION`。
- `DEPLOY_MODE`：`docker`（compose 注入）/ `native`（`deploy-native-ubuntu.sh` 写入）。

## 10. 进度熬过后端重启

Docker 升级会重建 backend 容器 → WebSocket 断开。前端处理：
- 正常时 Channels WebSocket 流式推进度。
- 断线后切换为轮询 `GET /system/upgrade/jobs/<id>`，后端恢复后继续；
- 代理始终独立写 Redis/DB，**最终结果以持久 `UpgradeJob` 为准**。

## 11. 前端「系统升级」页

`frontend/src/views/system/Upgrade.vue`（路由 `meta.permission='system:upgrade'`，`v-permission` 一致）：
- 顶部：当前版本 + 部署模式 + 「检查更新」按钮。
- 有更新：Markdown 渲染 `release_notes_md`、目标版本、「立即升级」（二次确认 + 风险提示：会重启服务、已自动备份 DB）。
- 进度视图：步骤实时流（断线自动重连读 job）、最终结果。
- 「回滚到上一个版本」按钮 + 升级历史表。
- API 走 `frontend/src/api/system.ts`，不在组件内直接 `import axios`。

## 12. 测试

- **后端单测**：清单解析 / 版本比较 / `UpgradeJob` 生命周期 / 单飞锁 / SSRF 白名单 / 权限。
- **代理单测**：通用步骤 + 两分支，含 **dry-run** 模式（不真正拉取/重启，只打印计划）。
- **集成**：用一份假清单在一次性 Docker 栈上跑真升级（同 install 验证做法）+ 健康门 + 回滚路径。
- **原生路径**：以脚本 dry-run + 关键命令断言验证（无独立原生测试机时）。

## 13. 安全与风险

| 风险 | 缓解 |
|------|------|
| 升级代理持有 docker.sock = 宿主 root 等价 | 权限收敛到单一代理；代理只执行白名单操作；不暴露端口；任务来源限 Redis 队列 |
| 清单被篡改/中间人 | 仅 HTTPS + 可信主机白名单；Docker 按 digest、原生按 sha256 校验产物 |
| 迁移失败/不兼容 | 升级前 `pg_dump` 快照 + 健康门不过自动回滚 |
| 并发升级 | Redis 单飞锁 |
| 后端容器重建致进度丢失 | 进度持久化 Redis+DB，UI 断线轮询恢复 |
| 越权触发 | `system:upgrade` 权限 + 审计 |

## 14. 待办前置（实现期产出，非本设计）
- 新建公开仓库 `hongheshan-svg/atm-erp` 并放首个 `manifest.json`。
- 在发布流程（CI）里生成镜像 digest 与原生 tar 的 sha256 并更新清单。
