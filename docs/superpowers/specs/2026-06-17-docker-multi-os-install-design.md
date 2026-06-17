# 设计文档：Docker 多平台一键安装发布版

- **日期**：2026-06-17
- **目标版本**：v0.2.0
- **状态**：已确认，待编写实现计划

## 1. 目标与背景

当前 v0.1.0 发布只包含**源码**。`docker-compose.yml` 从源码本地构建镜像，`install.sh`
仅支持 Ubuntu/Debian **原生**部署并显式拒绝其他系统，没有任何 CI 发布镜像。

本设计让发布版做到：在 **Linux、macOS、Windows 三个平台同等地位**，通过一条命令用
Docker 拉起完整 ERP，镜像来自 **GHCR 预构建多架构镜像**（amd64 + arm64）。

### 非目标（YAGNI）

- 不做 Kubernetes / Helm。
- 不为 macOS/Windows 实现 Linux host 网络的局域网设备广播发现（Docker Desktop 限制，
  属边缘场景，见 §5）。
- 不引入无 Elasticsearch 的精简 profile（如有需要作为后续迭代）。

## 2. 平台同等地位说明

ERP 应用本体（Web UI、全部业务模块、API、异步任务、搜索）通过 Docker 在三平台**完全一致**
运行，无次级分层。唯一有 Docker Desktop 限制的是 Linux 风格 `host` 网络：

- 考勤等局域网设备集成（`pyzk`）是**出站** TCP 连接到设备 IP（如 `192.168.2.x:4370`）。
  出站 容器→局域网 流量在 macOS/Windows 的 Docker Desktop 上经 NAT 正常路由，因此**标准
  考勤轮询在三平台均可用**。
- Linux 上的 `host` 网络仅是便利项（顺带让 Celery 用宿主机已发布端口访问 DB/Redis）。
  仅设备**主动推送**或 **UDP 广播发现**这类少数模式才真正依赖 Linux host 网络。

因此：基础 compose 完全可移植（Celery 走桥接网络，用服务名访问 `postgres`/`redis`）；
Linux host 网络降级为**可选 override**，绝非前置条件。每个平台获得相同的一键安装与相同
的运行应用。

## 3. 安装方式（Approach A）

`install.sh`（Linux + macOS，POSIX/bash）+ `install.ps1`（Windows，PowerShell）两个瘦脚本，
各自符合平台习惯。

## 4. 交付物清单

| 文件 | 操作 |
|------|------|
| `.github/workflows/release-images.yml` | 新增 — 打 tag 时构建并推送多架构镜像 |
| `docker-compose.yml` | 重写 — 可移植、基于 GHCR 镜像、仅暴露 nginx 端口 |
| `docker-compose.build.yml` | 新增 — 从源码构建的 override（贡献者/离线） |
| `docker-compose.linux-host.yml` | 新增 — 可选 Linux host 网络 override（局域网设备边缘场景） |
| `docker-compose.expose.yml` | 新增 — 可选向宿主机暴露 PG/Redis/ES 端口（调试用） |
| `install.sh` | 重写 — Linux+macOS Docker 一键安装；`--native` 保留原生路径 |
| `install.ps1` | 新增 — Windows Docker 一键安装 |
| `docker/backend/entrypoint.sh` | 修改 — 完整、幂等的首次启动初始化 |
| `.env.example` | 对齐 — 安装脚本消费的唯一模板 |
| `README.md` / `README.zh-CN.md` | 修改 — 新增一键安装章节 |

## 5. 详细设计

### 5.1 CI 镜像流水线（`.github/workflows/release-images.yml`）

- **触发**：推送 tag `v*.*.*`；外加 `workflow_dispatch` 用于手动/测试。
- **构建**：`docker/setup-buildx-action` + `docker/build-push-action`，
  `platforms: linux/amd64,linux/arm64`，构建 backend 与 frontend 两个镜像。
- **镜像源**：Dockerfile 的 `ARG APT_MIRROR/PIP_INDEX_URL/NPM_REGISTRY` 默认值为
  Aliyun/npmmirror（国内快）。CI **覆盖为上游**（PyPI/Debian/npm），让 GitHub 美国 runner
  构建稳定可靠。终端用户拉取成品镜像不受影响。
- **标签**：`:<version>`（如 `0.2.0`）与 `:latest`。
- **鉴权**：`GITHUB_TOKEN` 带 `packages: write`，登录 `ghcr.io`。
- **公开访问**：仓库私有时 GHCR 包仍可设为 Public。一次性步骤：首次推送后用 `gh api`
  将两个包设为 Public 并在文档记录。这样 `docker pull` 无需登录即可使用。

镜像命名：
- `ghcr.io/hongheshan-svg/atm-erp-backend`
- `ghcr.io/hongheshan-svg/atm-erp-frontend`

多架构可用性核对：`postgres:15-alpine`、`redis:7-alpine`、
`docker.elastic.co/elasticsearch/elasticsearch:7.17.16` 均提供 arm64；自建 backend/frontend
由 buildx 输出多架构。

### 5.2 Compose 重构

基础 `docker-compose.yml`（三平台一致）：

- **用镜像而非构建**：`backend`/`celery`/`celery-beat` →
  `image: ${REGISTRY:-ghcr.io}/${IMAGE_OWNER:-hongheshan-svg}/atm-erp-backend:${IMAGE_TAG:-latest}`；
  `nginx` → `atm-erp-frontend`。`build:` 块移到 `docker-compose.build.yml`。
- **Celery 可移植化**：去掉 `network_mode: host`；Celery 加入 `erp-network`，用服务名访问
  `postgres:5432` / `redis:6379`（与 backend 一致）。既更干净，也消除 macOS/Windows 阻塞。
- **仅暴露 nginx**（`80`/`443`）。基础版不再向宿主机发布 Postgres `5433` / Redis `6380` /
  ES `9201`——它们是内部服务，不发布可避免新机器端口冲突。需要的开发者用
  `docker-compose.expose.yml` override，或 `docker compose exec`。
- 保留 healthcheck、volumes、networks 不变。
- 通过 env 参数化：`REGISTRY`、`IMAGE_OWNER`、`IMAGE_TAG`。

Override 文件：
- `docker-compose.build.yml`：为四个服务重新加入 `build:` context，供本地构建。
- `docker-compose.linux-host.yml`：Celery `network_mode: host` + localhost 端口接线，
  仅在 Linux 上设备需要 UDP 发现/广播时显式叠加。
- `docker-compose.expose.yml`：向宿主机发布 PG/Redis/ES 端口，仅调试用。

**权衡**：基础版不暴露 DB 端口，依赖 `localhost:5433` 连库的开发者改用 expose override，
可接受。

### 5.3 安装脚本

两脚本共同流程：

1. **检测** OS + 架构。
2. **确保 Docker**：
   - Linux：缺失则 `curl -fsSL https://get.docker.com | sh`，启用 service，提示将用户加入
     `docker` 组（需重新登录，或脚本内用 `sudo` 执行 compose）。
   - macOS/Windows：检测 Docker Desktop；缺失则打印下载链接并干净退出（无法静默安装
     Desktop）。macOS 若存在 Homebrew，可提示 `brew install --cask docker`（可选）。
3. **获取部署文件**：按锁定版本从 Release 资产 / raw tag 下载 compose + `.env.example`。
4. **生成 `.env`**（已存在则不覆盖）：随机 `SECRET_KEY` + `DB_PASSWORD`、随机
   `ADMIN_PASSWORD`、`ALLOWED_HOSTS`/CORS/CSRF 设为 `localhost` + 检测到的宿主机 IP、
   `IMAGE_TAG=<version>`。随机串用 `openssl rand` 或 `python -c`，Windows 用 PowerShell
   `[System.Web.Security.Membership]::GeneratePassword` 或 GUID 等价物。
5. **`docker compose pull` → `up -d`**，随后**轮询健康检查**直到 backend + nginx 就绪。
6. **打印**成功横幅：`http://localhost`、admin 用户名、生成的 admin 密码。

- **参数**：`--tag <x>`（锁定版本）、`--https`（用现有 `scripts/generate-ssl.sh` 生成自签
  证书并用 443）、`--native`（仅 Linux → 委托现有 `scripts/deploy-native-ubuntu.sh`，保留
  当前原生路径）。
- **一键命令**（写入 README）：
  - Linux/macOS：`curl -fsSL https://github.com/hongheshan-svg/atm-erp/releases/latest/download/install.sh | bash`
  - Windows：`irm https://github.com/hongheshan-svg/atm-erp/releases/latest/download/install.ps1 | iex`

### 5.4 Entrypoint 首次启动初始化修复

现状 `entrypoint.sh` 运行 `migrate`/`collectstatic`/`init_workflows` 并创建 `admin/admin123`，
但**跳过 `init_permissions`、`init_roles`、`init_dashboard_widgets`**——新机器启动后没有权限树
和角色。修复方案：

- **仅 `backend` 服务执行初始化**（用 `RUN_BOOTSTRAP=1` 控制；Celery/beat 只等待 DB，避免
  三个容器竞争同一迁移/种子）。
- 初始化序列，**幂等**，用 volume 中标记文件（`/app/logs/.bootstrapped`）守护：首启执行完整
  序列，之后跳过；`migrate` 每次启动都跑：
  `migrate` → `collectstatic` → `init_permissions` → `init_roles --force` →
  `init_dashboard_widgets` → `init_workflows`。
- **Admin** 用 `ADMIN_USERNAME`/`ADMIN_PASSWORD` env（安装脚本生成）创建，不再硬编码密码。
- **示例数据**默认关闭（`SEED_DEMO_DATA=0`）；仅在显式开启时运行 `seed_data`。

### 5.5 发布打包与文档

- `release-images.yml`（或配套 `release.yml`）向 GitHub Release **附加资产**：`install.sh`、
  `install.ps1`、`docker-compose.yml`、`docker-compose.build.yml`、
  `docker-compose.linux-host.yml`、`docker-compose.expose.yml`、`.env.example`。
- README（中英双语）顶部新增 **"一键安装 / One-click install"** 章节，含三平台一键命令，
  并附"从源码构建"说明指向 build override。

## 6. 默认值决策

- **Admin 密码**：随机生成并打印一次，不用固定 `admin123`（更安全）。
- **基础 compose**：不向宿主机暴露 Postgres/Redis/ES（更干净、更安全）。

## 7. 验证计划

1. 打预发布 tag `v0.2.0-rc.1`，验证 CI 构建 + GHCR 推送（不出正式 Release）。
2. 本机（macOS / Docker Desktop）`docker compose pull && up -d`，确认可移植性与初始化产出可
   登录系统。
3. 端到端冒烟 `install.sh`（Linux 环境）：从零到打印登录信息。
4. README 一键命令链接有效性核对。

## 8. 风险与缓解

| 风险 | 缓解 |
|------|------|
| GitHub runner 构建多架构（arm64 经 QEMU）慢 | 仅在 tag 时构建；可加 buildx 缓存 |
| GHCR 包默认私有导致 `docker pull` 失败 | 首发后用 `gh api` 设为 Public，文档记录 |
| Docker Desktop 未装（mac/win） | 脚本检测并给出明确下载指引后退出 |
| 初始化命令并发竞争 | 仅 backend 执行 + 标记文件守护 |
| 局域网设备广播发现在 mac/win 不可用 | 文档说明；提供 Linux host override |
