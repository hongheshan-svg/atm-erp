# 远程升级 / Remote Upgrade

> **适用版本**: 0.3.0+
> **部署模式**: Docker Compose（`DEPLOY_MODE=docker`）/ 原生 Ubuntu（`DEPLOY_MODE=native`）

---

> **⚠️ 重要：一键（自动）升级当前仅支持 Docker 部署**
>
> 原生（systemd）部署模式下，调用 `POST /api/v1/system/upgrade` 或 `POST /api/v1/system/rollback`
> 将返回 `403 UpgradeNotAllowed` 错误，提示使用手动流程。
> **原生部署请直接参阅下方[手动端到端测试流程](#手动端到端测试流程manual)中的步骤，或联系运维人员执行手动升级。**
>
> 原生一键自动升级为规划中的后续功能（tracked follow-up），架构/安全章节中的原生设计描述
> 代表最终目标，当前版本尚未实现。

---

## 目录

1. [架构概览](#架构概览)
2. [版本与部署模式来源](#版本与部署模式来源)
3. [清单格式（Manifest）](#清单格式manifest)
4. [权限要求](#权限要求)
5. [API 接口](#api-接口)
6. [升级流程详解](#升级流程详解)
7. [回滚机制](#回滚机制)
8. [安全设计](#安全设计)
9. [发布新版本的操作流程（维护者）](#发布新版本的操作流程维护者)
10. [手动端到端测试流程（MANUAL）](#手动端到端测试流程manual)

---

## 架构概览

```
  管理员浏览器
      │
      │  POST /api/v1/system/upgrade
      ▼
  ┌─────────────────────────────────────────┐
  │  Django Backend (erp-backend)           │
  │  UpgradeService.perform()               │
  │    ├─ 获取清单 → 版本比对               │
  │    ├─ 写 UpgradeJob(status=pending)     │
  │    └─ LPUSH erp:upgrade:queue           │──► Redis
  └─────────────────────────────────────────┘         │
                                                       │ BRPOP
  ┌────────────────────────────────────────────────────▼──┐
  │  erp-updater 容器 (UpgradeAgent)                      │
  │    1. 校验 job_id + DEPLOY_MODE                       │
  │    2. backup_db()  — pg_dump 快照                     │
  │    3. _apply_docker() / _apply_native()               │
  │       Docker: docker compose pull → up -d             │
  │       Native: 下载 tar.gz → sha256 → 解包 → reload    │
  │    4. health_gate() — 轮询 /api/v1/health/ (600 s)    │
  │    5. status=success 或 _rollback()                   │
  │    6. report(event, payload)                          │
  └───────────────────────────────────────────────────────┘
          │  report()
          ▼
  Redis PUBLISH erp:upgrade:events
          │
  ┌───────▼────────────────────────────────────────────────┐
  │  erp-upgrade-relay 容器 (upgrade_progress_relay 命令)  │
  │    SUBSCRIBE erp:upgrade:events                        │
  │    → 写 UpgradeJob.steps (JSON)                        │
  │    → Django Channels PUBLISH → WS 推送管理员浏览器      │
  └────────────────────────────────────────────────────────┘
          │  WebSocket ws/system/upgrade/<job_id>/
          ▼
  管理员浏览器（前端升级页面实时展示进度）
```

**要点说明**

- **进度持久化，UI 可重连**：`relay` 把每条进度事件写入数据库；前端断线重连或 backend 重启后，可通过 `GET /api/v1/system/upgrade/jobs/<id>` 取回完整日志，无需重新升级。
- **Docker 升级时 backend 本身会重启**，WebSocket 中断属预期行为，前端会自动轮询 job 状态直到 `success` 或 `failed`。
- **进度锁**：Redis 键 `erp:upgrade:lock` 确保同一时刻只有一个升级任务运行，防止并发升级相互干扰。

---

## 版本与部署模式来源

| 变量 | 注入位置 | 说明 |
|------|---------|------|
| `APP_VERSION` | `docker-compose.yml` env `${IMAGE_TAG:-latest}` | 当前运行的 Docker 镜像标签；由 CI 发布时通过 `IMAGE_TAG` 传入 |
| `DEPLOY_MODE` | `docker-compose.yml` env（硬编码 `docker`） | 告知系统当前部署类型；原生部署由 `scripts/deploy-native-ubuntu.sh` 写入 |

两个变量由 `backend/apps/core/version.py` 读取：

```python
get_app_version()   # → "1.2.3" 或 "latest"
get_deploy_mode()   # → "docker" | "native" | "unknown"
```

健康检查端点 `GET /api/v1/health/` 响应体包含：

```json
{
  "status": "healthy",
  "version": "1.2.3"
}
```

版本信息端点 `GET /api/v1/system/version` 响应体：

```json
{
  "version": "1.2.3",
  "deploy_mode": "docker"
}
```

---

## 清单格式（Manifest）

升级源为公开仓库 GitHub Release 中的 `manifest.json`，URL 默认为：

```
https://raw.githubusercontent.com/hongheshan-svg/atm-erp/main/manifest.json
```

可通过环境变量 `ERP_UPDATE_MANIFEST_URL` 覆盖（仅限 SSRF 白名单内的主机）。

### manifest.json 完整格式

```json
{
  "latest_version": "1.3.0",
  "release_date": "2026-06-01",
  "release_notes_md": "## v1.3.0\n\n- 新增远程升级功能\n- 修复 BOM 导入边界情况\n",
  "min_upgradable_from": "1.0.0",
  "docker": {
    "image_tag": "1.3.0",
    "registry": "ghcr.io",
    "image_owner": "hongheshan-svg",
    "images": [
      {
        "name": "atm-erp-backend",
        "digest": "sha256:abc123...（64 位十六进制）"
      },
      {
        "name": "atm-erp-frontend",
        "digest": "sha256:def456..."
      },
      {
        "name": "atm-erp-updater",
        "digest": "sha256:789abc..."
      }
    ]
  },
  "native": {
    "download_url": "https://github.com/hongheshan-svg/atm-erp/releases/download/v1.3.0/atm-erp-v1.3.0.tar.gz",
    "sha256": "0a1b2c...（64 位十六进制，tar.gz 文件的 SHA-256）",
    "target_version": "1.3.0"
  }
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `latest_version` | string | 是 | semver 格式，用于版本比对 |
| `release_date` | string | 否 | ISO 8601 日期 |
| `release_notes_md` | string | 是 | Markdown 格式发布说明，前端渲染展示 |
| `min_upgradable_from` | string | 是 | 最低可直接升级的起始版本；低于此版本须手动迁移 |
| `docker.image_tag` | string | Docker 必填 | `docker compose pull` 使用的标签 |
| `docker.registry` | string | Docker 必填 | 镜像注册中心，默认 `ghcr.io` |
| `docker.image_owner` | string | Docker 必填 | 镜像所有者 namespace |
| `docker.images[].digest` | string | Docker 必填 | `sha256:` 前缀的镜像摘要，拉取后校验完整性 |
| `native.download_url` | string | Native 必填 | tar.gz 下载地址，需在 SSRF 白名单内 |
| `native.sha256` | string | Native 必填 | 下载包的 SHA-256 校验值 |
| `native.target_version` | string | Native 必填 | 用于路径合法性校验（semver，防路径穿越） |

---

## 权限要求

| 权限标识 | 说明 |
|---------|------|
| `system:upgrade` | 访问「系统升级」页面、查询升级状态、执行升级操作 |

此权限默认仅分配给**超级管理员**角色。普通管理员（无此权限）访问升级页面时返回 `403 Forbidden`。

初始化权限树时 `init_permissions` 会自动创建此权限节点；如需手动查看可在 Django Admin 的 `Permission` 表中搜索 `upgrade`。

---

## API 接口

所有接口均需认证（Bearer JWT），并校验 `system:upgrade` 权限（`GET /api/v1/system/version` 仅需登录）。

### 1. 查询当前版本

```
GET /api/v1/system/version
```

返回当前运行版本与部署模式，**任意已登录用户**可访问。

**响应示例：**

```json
{
  "version": "1.2.0",
  "deploy_mode": "docker"
}
```

### 2. 检查更新

```
GET /api/v1/system/check-update
GET /api/v1/system/check-update?force=1
```

拉取清单并与当前版本比对，**不执行任何升级操作**。默认结果缓存 20 分钟；加 `?force=1` 强制绕过缓存。

**响应示例（有更新）：**

```json
{
  "current_version": "1.2.0",
  "latest_version": "1.3.0",
  "has_update": true,
  "deploy_mode": "docker",
  "release_notes_md": "## v1.3.0\n...",
  "min_upgradable_from": "1.0.0",
  "cached": false,
  "warning": ""
}
```

**响应字段说明：**

| 字段 | 说明 |
|------|------|
| `current_version` | 当前运行版本 |
| `latest_version` | 清单中最新版本 |
| `has_update` | 是否有可用更新（`true` / `false`） |
| `deploy_mode` | 当前部署模式（`docker` / `native`） |
| `release_notes_md` | Markdown 格式发布说明 |
| `min_upgradable_from` | 最低可直接升级的起始版本 |
| `cached` | 结果是否来自缓存 |
| `warning` | 拉取清单失败时的错误信息（成功时为空串） |

### 3. 执行升级

```
POST /api/v1/system/upgrade
```

创建 `UpgradeJob` 并将任务入队，立即返回 job 信息。

**请求体（可选）：**

```json
{}
```

**响应（202 Accepted）：**

```json
{
  "job_id": "42",
  "status": "pending"
}
```

**并发防护**：若已有升级任务运行，返回 `409 Conflict`：

```json
{
  "detail": "升级任务已在运行中，请等待完成",
  "code": "UPGRADE_BUSY"
}
```

### 4. 手动回滚

```
POST /api/v1/system/rollback
```

人工触发回滚至上一次成功升级前的版本，创建 `UpgradeJob`（`action=rollback`）并入队。

**响应（202 Accepted）：**

```json
{
  "job_id": "43",
  "status": "pending"
}
```

若无可回滚的历史记录，返回 `409 Conflict`（`code: "NO_ROLLBACK"`）。

### 5. 查询 Job 详情

```
GET /api/v1/system/upgrade/jobs/<job_id>
```

**响应示例：**

```json
{
  "id": "42",
  "action": "upgrade",
  "mode": "docker",
  "from_version": "1.2.0",
  "target_version": "1.3.0",
  "status": "running",
  "steps": [
    {"stage": "backup", "message": "pg_dump -> /var/backups/erp/pre-upgrade-20260601-100010.sql", "level": "info", "ts": 1748779210.0},
    {"stage": "apply",  "message": "set IMAGE_TAG=1.3.0; docker compose pull && up -d",          "level": "info", "ts": 1748779215.0}
  ],
  "started_at": "2026-06-01T10:00:05Z",
  "finished_at": null
}
```

`status` 枚举：`pending` | `running` | `healthcheck` | `success` | `failed` | `rolled_back`

### 6. Job 列表

```
GET /api/v1/system/upgrade/jobs
```

返回最近 20 条 Job 记录（按创建时间降序），每条记录结构与 Job 详情相同。

### 7. 进度 WebSocket

```
ws://<host>/ws/system/upgrade/<job_id>/
```

需在握手时带 JWT（`Authorization: Bearer <token>` 头或 query param `token=<token>`）。

**推送格式：**

```json
{
  "stage":   "apply",
  "message": "docker compose up -d 执行完成",
  "level":   "info",
  "ts":      1748779260.0
}
```

`level` 枚举：`info` | `error`

---

## 升级流程详解

### Docker 模式

1. **数据库快照** (`backup_db`)：调用 `pg_dump` 将当前数据库备份至 `/var/backups/erp/pre-upgrade-<timestamp>.sql`（卷 `backend_logs:/var/backups/erp`）。
2. **更新 `.env`** (`_apply_docker`)：将 `IMAGE_TAG=<target_version>` 写入项目根目录的 `.env` 文件。
3. **拉取镜像**：在项目目录执行 `docker compose pull`，拉取新版本镜像。
4. **校验摘要**：对清单中每个 `digest` 调用 `docker inspect` 验证拉到的镜像 sha256 与清单一致，防止中间人攻击。
5. **滚动重启**：执行 `docker compose up -d`，Compose 依次重启各服务（backend/celery/celery-beat 先重启，nginx 最后）。
6. **健康门控** (`health_gate`)：循环轮询 `http://nginx/api/v1/health/`，最多等待 600 秒。健康门控要求 HTTP 响应码为 200 **且** 响应体中 `version` 字段等于 `target_version`。
7. **成功**：写 `UpgradeJob.status=success`，推送进度事件。

### 原生模式

1. **数据库快照**：同上。
2. **下载 tar.gz** (`_apply_native`)：请求 `native.download_url`（需在 SSRF 白名单内），流式下载至临时目录。
3. **sha256 校验**：对下载文件计算 SHA-256，与清单 `native.sha256` 比对；不匹配则中止升级。
4. **路径穿越防护**：解包前校验所有 tar 条目路径，拒绝含 `../` 或绝对路径的压缩包。
5. **解包**：将 tar.gz 解压至安全目录，替换源码与静态资源。
6. **服务重载**：`systemctl restart erp-backend erp-celery erp-celery-beat`。
7. **健康门控 + 成功**：同 Docker 模式。

---

## 回滚机制

### 自动回滚（agent 触发）

当任意步骤（拉取/重启/健康门控）失败时，agent 自动调用 `_rollback()` / `_rollback_native()`：

#### Docker 回滚

1. 将 `.env` 中 `IMAGE_TAG` 恢复为升级前版本。
2. 执行 `docker compose up -d` 拉起旧版本容器（旧镜像仍在本地缓存中，无需重新拉取）。
3. 等待健康门控通过。
4. 写 `UpgradeJob.status=rolled_back`，推送进度事件。

#### 原生回滚

1. 将源码目录符号链接还原至旧版本（升级前已保存旧链接路径）。
2. `systemctl restart` 恢复旧版本。
3. 等待健康门控通过。
4. 写 `UpgradeJob.status=rolled_back`，推送进度事件。

### 手动回滚（人工触发）

管理员可在升级完成后通过 API 主动触发回滚至上一次成功升级前的版本：

```
POST /api/v1/system/rollback
```

详见 [API 接口 → 手动回滚](#4-手动回滚)。

### 数据库回滚

**注意**：agent **不会**自动恢复数据库快照，因为多数迁移是向前兼容的，自动恢复反而可能丢失数据。如果代码回滚成功但数据库 schema 已变更，运维人员应手动评估是否需要回滚数据库：

```bash
# 手动恢复数据库快照（谨慎操作，会覆盖现有数据）
docker compose exec erp-updater pg_restore -h postgres -U erp_user -d erp_db \
  /var/backups/erp/pre-upgrade-<timestamp>.sql
```

---

## 安全设计

### SSRF 防护（清单拉取 & 原生下载）

代码中维护一份**主机白名单**（`ManifestClient.ALLOWED_HOSTS`），仅允许向白名单内的域名发起 HTTP 请求：

- `raw.githubusercontent.com`
- `github.com`
- `objects.githubusercontent.com`（GitHub Releases 重定向目标）

默认拒绝：
- 所有私有 IP（`127.x.x.x`、`10.x.x.x`、`172.16-31.x.x`、`192.168.x.x`、`169.254.x.x`）
- IPv6 回环/链路本地地址
- 不在白名单内的任意公网域名

通过 `ERP_UPDATE_MANIFEST_URL` 覆盖清单 URL 时，同样会经过此 SSRF 校验。**不要**将内网 IP 或 `localhost` 加入白名单（即使在测试环境中也应使用 mock 而非绕过）。

### 镜像完整性（Docker 模式）

拉取镜像后，通过 `docker inspect --format '{{index .RepoDigests 0}}'` 提取镜像摘要，与清单中 `docker.images[].digest` 逐一比对。摘要不匹配时，中止升级并触发回滚。

### tar 解包加固（原生模式）

解包前遍历所有 tar 条目：
- 拒绝路径包含 `../` 的条目（路径穿越攻击）
- 拒绝以 `/` 开头的绝对路径条目
- `target_version` 字段经 semver 正则校验，确保不含 shell 特殊字符（防止命令注入）

### docker.sock 权限边界

`erp-updater` 容器挂载了宿主机的 `/var/run/docker.sock`，这是实现「容器自身驱动 Compose 滚动更新」的必要设计，但也意味着 **updater 拥有宿主机 Docker 的完全控制权**。

风险收敛措施：
1. **最小镜像**：updater 镜像仅包含 Python + docker CLI + pg_dump，无其他服务。
2. **只读项目目录例外**：`.:/project` 挂载是 `rw` 的，因为需要修改 `.env`；其余业务数据卷均不挂载。
3. **网络隔离**：updater 只接入 `erp-network`，无宿主机 host 网络。
4. **无 root**：镜像以非 root 用户运行（`USER erp`），但 docker socket 通信本身不受此限制——这是 Docker 架构固有的约束。
5. **审计日志**：每次升级操作均写入 `UpgradeJob` 记录，可追溯。

**生产建议**：考虑使用 Docker socket proxy（如 [Tecnativa/docker-socket-proxy](https://github.com/Tecnativa/docker-socket-proxy)）进一步限制 updater 可操作的 Docker API 范围（仅允许 `containers/exec`、`images/pull`、`services/update`）。

---

## 发布新版本的操作流程（维护者）

在本项目仓库 `hongheshan-svg/atm-erp` 中执行以下步骤：

### 1. 构建并推送镜像（CI 流程）

```bash
# 在主仓库 CI 中（.github/workflows/release.yml）
IMAGE_TAG="1.3.0"

# 构建多架构镜像
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/hongheshan-svg/atm-erp-backend:${IMAGE_TAG} \
  --push ./backend

# 获取镜像摘要
BACKEND_DIGEST=$(docker manifest inspect \
  ghcr.io/hongheshan-svg/atm-erp-backend:${IMAGE_TAG} \
  | jq -r '.config.digest')

# 同样处理 frontend、updater 镜像...
```

### 2. 为原生包计算 sha256

```bash
sha256sum atm-erp-v1.3.0.tar.gz
# 输出: 0a1b2c...  atm-erp-v1.3.0.tar.gz
```

### 3. 更新 manifest.json

将上述摘要与 sha256 填入 `manifest.json` 并提交到仓库 main 分支：

```bash
# 在 atm-erp 仓库
cat > manifest.json <<'EOF'
{
  "latest_version": "1.3.0",
  "release_date": "2026-06-01",
  "release_notes_md": "## v1.3.0\n\n- 新增远程升级功能\n",
  "min_upgradable_from": "1.0.0",
  "docker": {
    "image_tag": "1.3.0",
    "registry": "ghcr.io",
    "image_owner": "hongheshan-svg",
    "images": [
      {"name": "atm-erp-backend",  "digest": "sha256:<backend-digest>"},
      {"name": "atm-erp-frontend", "digest": "sha256:<frontend-digest>"},
      {"name": "atm-erp-updater",  "digest": "sha256:<updater-digest>"}
    ]
  },
  "native": {
    "download_url": "https://github.com/hongheshan-svg/atm-erp/releases/download/v1.3.0/atm-erp-v1.3.0.tar.gz",
    "sha256": "<tar-gz-sha256>",
    "target_version": "1.3.0"
  }
}
EOF
git add manifest.json && git commit -m "release: v1.3.0" && git push
```

---

## 手动端到端测试流程（MANUAL）

> **前提条件**：
> - 本地已运行 ATM-ERP Docker 堆栈（`docker compose up -d` 且 backend 健康）
> - `erp-updater` 容器正常（`docker compose ps erp-updater`）
> - `erp-upgrade-relay` 容器正常
> - 已有超级管理员账号（拥有 `system:upgrade` 权限）
> - 仓库已发布目标版本的 manifest.json 且镜像已推送到 GHCR

### 步骤一：准备"旧版本"状态

```bash
# 在 .env.docker 或 .env 中设置当前版本低于清单中的 latest_version
# 例如清单写 latest_version=1.3.0，则本地设为
echo 'IMAGE_TAG=1.2.0' >> .env

# 重启 backend 使 APP_VERSION 生效
docker compose up -d backend

# 验证版本
curl -s http://localhost:8080/api/v1/health/ | python3 -m json.tool
# 期望: "version": "1.2.0"
```

### 步骤二：以管理员登录前端

1. 浏览器打开 `http://localhost:8080/erp/`
2. 以超级管理员账号登录
3. 导航至「系统设置 → 系统升级」（URL: `/erp/system/upgrade`）

### 步骤三：检查更新

1. 点击「检查更新」按钮
2. 等待响应（约 2–5 秒，受 GitHub raw 访问速度影响）
3. 确认显示：
   - 当前版本：`1.2.0`
   - 最新版本：`1.3.0`（与清单一致）
   - 发布说明：Markdown 渲染展示

   也可直接调用 API：

   ```bash
   TOKEN="<your-jwt-token>"
   curl -s -H "Authorization: Bearer $TOKEN" \
     http://localhost:8080/api/v1/system/check-update | python3 -m json.tool
   ```

### 步骤四：执行升级

1. 点击「一键升级」按钮，确认对话框
2. 前端进入进度展示页，通过 WebSocket 实时展示各步骤状态
3. 监控 updater 容器日志：

   ```bash
   docker compose logs -f erp-updater
   ```

   期望出现类似输出：
   ```
   [upgrade] job_id=42 target=1.3.0 mode=docker
   [step] backup_db: pg_dump 完成
   [step] pull: docker compose pull 完成
   [step] digest: all digests verified
   [step] apply: docker compose up -d 完成
   [step] health_gate: backend healthy at 1.3.0
   [done] status=success
   ```

4. backend 重启后前端会短暂断线（正常），自动轮询 job 状态
5. 约 60–120 秒后（含镜像拉取时间），前端显示「升级成功」

### 步骤五：验证升级结果

```bash
# 检查运行版本
curl -s http://localhost:8080/api/v1/health/ | python3 -m json.tool
# 期望: "version": "1.3.0"

# 检查 job 详情（status 应为 success）
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/system/upgrade/jobs | python3 -m json.tool

# 检查容器镜像
docker compose ps
docker inspect erp-backend | jq '.[0].Config.Image'
# 期望: ghcr.io/hongheshan-svg/atm-erp-backend:1.3.0

# 检查 .env 文件
grep IMAGE_TAG .env
# 期望: IMAGE_TAG=1.3.0
```

### 步骤六：测试回滚（可选）

在实际升级前，可通过以下方式模拟失败来测试自动回滚：

```bash
# 方法：将 docker-compose.yml 中 backend healthcheck 临时改为总是失败
# 或直接修改清单中 digest 为错误值，触发完整性校验失败

# 观察 updater 日志，期望看到：
# [step] health_gate: FAILED, attempting rollback
# [step] rollback: docker compose up -d (old version)
# [done] status=rolled_back

# 验证版本已回滚
curl -s http://localhost:8080/api/v1/health/ | jq '.version'
# 期望: "1.2.0"
```

也可在升级成功后手动触发回滚：

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/system/rollback | python3 -m json.tool
# 期望: {"job_id": "...", "status": "pending"}
```

### 步骤七：清理测试状态（测试完毕后）

```bash
# 恢复 .env
sed -i 's/IMAGE_TAG=1.2.0/IMAGE_TAG=1.3.0/' .env
docker compose up -d

# 清理升级日志（可选）
docker compose exec backend python manage.py shell -c \
  "from apps.core.models import UpgradeJob; UpgradeJob.objects.all().delete(); print('cleared')"
```

---

> 如在测试中遇到 SSRF 白名单阻断（`ERP_UPDATE_MANIFEST_URL` 指向非白名单地址），
> 请改用仓库的真实 raw URL，或在测试中 mock `ManifestClient.fetch()`，
> **不要**修改白名单配置提交到版本控制。
