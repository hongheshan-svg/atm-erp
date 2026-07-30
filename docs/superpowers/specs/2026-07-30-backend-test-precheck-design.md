# 后端测试本地预检 · 设计

- 日期:2026-07-30
- 状态:设计已确认,待实现
- 范围:开发工具链(shell 脚本 + git hook + 一层薄 Docker 镜像),不改动任何业务代码
- 关联:
  - [Quality Guardrails for ERP](2026-05-20-quality-guardrails-design.md)(CI 与 pre-commit 的最初设计)
  - `scripts/precheck.sh` + `.githooks/pre-commit`(本设计的姊妹件,已于 PR #38 合并,负责 lint 侧)

## 1. 背景与问题

2026-07-30 排查「GitHub 上 CI 基本都跑失败」时,统计最近 40 次 run:11 次失败,其中 **7 次挂在 `Backend / preflight → Lint and formatting`**,另 **4 次是真实的测试失败**。

lint 侧的 7 次已经由 `scripts/precheck.sh` + `.githooks/pre-commit` 解决(提交前用官方 ruff 镜像跑一遍与 CI 逐字一致的检查)。本设计处理剩下的 4 次。

查这 4 次失败具体挂在哪个 job:

| run | 失败的 job |
|---|---|
| 30414919311 | `Backend / integration`、`Backend / platform, permissions and accounts` |
| 30436436661 | `Backend / finance, reporting and office`、`Backend / projects, master data and sales` |

结论有两点值得注意:一是失败分散在多个模块分组,不是某一个分组特别脆;二是 **`Backend / integration`(pytest)也真实挂过**,所以预检若只覆盖 4 个 Django 分组会留下缺口。

问题的本质与 lint 侧相同:**本地没有任何等价于 CI 的测试执行路径**。本机没有 Python 虚拟环境,`erp-app` 生产容器不装 dev 依赖,开发者要跑一次后端测试没有现成办法,于是所有测试失败都只能等推上 GitHub 之后才发现,每次要补一轮提交才转绿,浪费 15 分钟一轮的流水线。

## 2. 目标与非目标

### 目标

1. 在 `git push` 之前,用与 CI 保真的方式跑受本次改动影响的后端测试。
2. 常见改动(单个业务 app)的预检代价控制在 **1 分钟内**,不破坏日常节奏。
3. 测试数据库与**生产库完全隔离**——本机的 `erp` compose 栈跑的就是真实生产数据,预检绝不能碰。
4. 与 CI 的配置(分组划分、警告开关、依赖版本)保持**自动跟随**,不靠人工同步。

### 非目标

- 不替代 CI。CI 仍然全量跑 14 个 job,预检只是把高概率失败提前拦下。
- 不覆盖前端测试(Vitest)、浏览器 E2E、依赖审计、容器构建这些 job。
- 不追求「本地绿 = CI 必绿」的强保证。见第 7 节的已知差异。
- 不引入新的 Python 依赖到本机(维持 `precheck.sh` 确立的「一切经 Docker」原则)。

## 3. 实测基线

以下数字全部在本机实测得出(生产镜像 `atm-erp-app:0.3.0`,Python 3.11.15 / Django 5.2.16,与 CI 的 `PYTHON_VERSION: '3.11'` 及 `requirements.txt` 钉版一致),**不是估算**:

| CI 分组 | 用例数 | 本地耗时(复用测试库) | 该分组在 CI 上的耗时 |
|---|---:|---:|---:|
| ① platform, permissions and accounts | 292 | **336s** | 12m32s |
| ② projects, master data and sales | 32 | 11s | — |
| ③ supply chain, inventory and production | 94 | 18s | — |
| ④ finance, reporting and office | 186 | 10s | — |
| integration (pytest) | 36 | 23s | — |
| **合计** | **640** | **≈6 分 40 秒** | — |

一次性成本:**首次创建测试库约 7 分钟**(执行全量迁移),之后靠 `--keepdb` 复用。

分组① 独占了总耗时的 90%,这是「按改动选分组」价值的来源:只要改动没碰到分组①,预检就在半分钟量级。

### 3.1 必须复刻的四个条件

排查过程中确认了四条,少任何一条预检都不可信:

1. **必须挂仓库根**,即 `-v "$REPO_ROOT:/repo:ro" -w /repo/backend`。若只挂 `backend/` 到 `/app`,会**盖掉镜像里已有的 `/app/frontend`**,导致分组①中读取前端路由文件的 4 个用例直接 error(`找不到前端路由文件`)。挂仓库根同时也让目录布局与 CI 的 checkout 结果一致。
2. **`PYTHONDONTWRITEBYTECODE=1`**。只读挂载下 Python 会对数百个模块反复尝试写 `.pyc` 并失败,实测导致 **17 倍**的性能损失(7m33s → 27s)。
3. **`-W error::DeprecationWarning`**。CI 的执行命令是 `python -W error::DeprecationWarning manage.py test --noinput`,不加这个开关则「本地绿」不等于「CI 绿」。
4. **postgres + redis 双容器**。redis 是硬依赖,实测连不上时用例直接 error(`ConnectionInterrupted`),不是可选降级项。

## 4. 架构

### 4.1 组件

| 文件 | 职责 |
|---|---|
| `scripts/precheck-tests.sh` | 测试预检主脚本:管理测试栈生命周期、解析改动、执行测试 |
| `.githooks/pre-push` | 触发器:计算本次 push 的改动范围,调用主脚本 |
| `docker/test-runner.Dockerfile` | 在生产镜像上补 `pytest` / `pytest-django` 的薄镜像 |
| `CLAUDE.md` | 使用说明 |

`scripts/precheck-tests.sh` 与既有的 `scripts/precheck.sh`(lint)是并列关系,互不调用、互不依赖。两者共用 `install.sh` 确立的输出风格(`c_info` / `c_ok` / `c_err`)与「一切经 Docker」的原则。

### 4.2 分组定义:动态读取,不复制

分组划分**不在预检里复制一份**,而是从 `scripts/ci/backend_test_matrix.py` 的 `GROUPS` 常量动态读取(在容器内 import 该模块并导出 JSON)。

这与 `precheck.sh` 从 `requirements-dev.txt` 动态解析 ruff 版本是同一条原则:CI 改了分组划分,预检自动跟随,不存在「改了 CI 忘了改预检」的漂移。该模块自身的 `validate_coverage()` 已经保证所有 `apps.*` 都被某个分组覆盖且不重复。

### 4.3 改动 → 分组映射

| 改动路径 | 触发 |
|---|---|
| `backend/apps/core/**`、`backend/config/**`、`backend/manage.py`、`backend/requirements*.txt`、`backend/pyproject.toml` | **全部 4 组 + integration** |
| `backend/apps/<其它 app>/**` | 含该 app 的那一组 + integration |
| `backend/tests/**` | 仅 integration |
| `frontend/src/router/index.ts` | 分组① |
| 其它(`docs/`、`nginx/`、`miniprogram/`、`scripts/ci/`、`frontend/` 其余部分,以及 `backend/` 下的 `logs/`、`uploads/`、`backend/`(staticfiles)等非代码目录) | 不触发,不启 Docker |

匹配采用**白名单**语义:只有明确列出的路径才触发测试,未列出的一律放行。这样新增的目录默认不会拖慢 push,代价是新增了需要覆盖的代码路径时要记得补规则——由第 8 节的验证项与 CI 全量兜底。

两条不显然的规则:

- **`apps/core` 触发全量**。`core` 提供全站的 `BaseModel`、权限 Mixin、审计与工作流,改它影响所有模块。而全量只比单跑分组①多约 40 秒(分组①本身就是耗时大头),保真度几乎是白拿的。`config/`(settings、根 urls)同理。
- **`frontend/src/router/index.ts` 触发分组①**。分组①的 `test_menu_sync_toplevel` / `test_permission_bootstrap` 会直接读取这个文件来核对菜单权限。改前端路由却忘了同步菜单权限,是本项目真实踩过的坑。

### 4.4 测试栈生命周期

| 资源 | 名称 | 镜像 |
|---|---|---|
| 网络 | `erp-testenv-net` | — |
| 数据库 | `erp-testenv-pg` | `postgres:15` |
| 缓存 | `erp-testenv-redis` | `redis:7` |
| 数据卷 | `erp-testenv-pgdata` | — |

命名前缀 `erp-testenv-` 与生产的 `erp-postgres` / `erp-redis` 明确区分,且这些资源**不属于任何 compose project**,不会被 `docker compose down` 误伤,也不会与生产栈争用端口(全部只在自有网络内暴露,不映射到宿主机)。

镜像刻意选用 `postgres:15` / `redis:7` 而非本机已有的 alpine 变体,与 CI 逐字一致。alpine 基于 musl,其字符串排序(collation)规则与 CI 所用 glibc 不同,理论上存在「本地绿、CI 红」的排序类差异。代价是一次性多下载约 150MB。

PG 数据放在**命名卷**里,因此那 7 分钟建好的测试库能在容器被删除后存活。脚本每次运行时自愈:缺什么建什么,容器停了就 `start`,已在跑就直接用。

生命周期开关:

- 默认:自动拉起,用完**不停**(下次省去启动时间)
- `--fresh-db`:保留容器与卷,只 `DROP` 并重建 `test_erp_db`(约 7 分钟)。迁移文件被改写/删除后用它
- `--down`:删除容器,保留数据卷(测试库仍在,下次拉起后可直接复用)
- `--clean`:连数据卷一起删除,回到全新状态(下次会重新经历 7 分钟建库)

### 4.5 执行参数

```
docker run --rm --network erp-testenv-net \
  -v "$REPO_ROOT:/repo:ro" -w /repo/backend \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -e DJANGO_SETTINGS_MODULE=config.settings -e SECRET_KEY=<预检专用常量> -e DEBUG=False \
  -e DB_HOST=erp-testenv-pg -e DB_NAME=erp_db -e DB_USER=erp_user \
  -e DB_PASSWORD=erp_password -e DB_PORT=5432 \
  -e REDIS_URL=redis://erp-testenv-redis:6379/0 -e REDIS_HOST=erp-testenv-redis \
  <test-runner 镜像> \
  -W error::DeprecationWarning manage.py test --noinput --keepdb <targets>
```

数据库口令沿用 CI 的 `erp_password`(CI workflow 里就是明文写死的同一串),因为这套测试栈只在自有 Docker 网络内可达、不映射宿主机端口、且只装测试数据。`SECRET_KEY` 同理用一个仅供预检使用的常量,与生产 `.env` 无关。

integration 部分对应 CI 的 `pytest tests/integration -v --tb=short -W error::DeprecationWarning`,额外加 `--reuse-db`(等价于 `--keepdb`)与 `-p no:cacheprovider`(只读挂载下无法写 `.pytest_cache`,不加会有一条无害但干扰视线的 warning)。

### 4.6 薄测试镜像

生产镜像不装 dev 依赖,没有 pytest。`docker/test-runner.Dockerfile` 在其上补三行:

```dockerfile
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG PYTEST_SPEC
RUN pip install --no-cache-dir ${PYTEST_SPEC}
```

pytest / pytest-django 的版本从 `requirements-dev.txt` 解析(与 ruff 版本同一手法)。镜像 tag 为 `erp-test-runner:<pytest版本>-<基础镜像版本>`——依赖或基础镜像一变,tag 自然 miss 并触发重建,不需要人记得刷新。镜像不存在时脚本自动构建。

相比每次容器内 `pip install`(约 6 秒),薄镜像的好处是**离线也能跑**,不依赖 PyPI 可达。

## 5. 触发与流程

`.githooks/pre-push` 从 stdin 读取 `<local_ref> <local_sha> <remote_ref> <remote_sha>`,据此计算改动基线:

- `remote_sha` 为全 0(新分支首次推送)→ 基线取 `origin/main`
- 否则 → 基线取 `remote_sha`
- `local_sha` 为全 0(删除远程分支)→ 直接放行

然后 `git diff --name-only <基线>..<local_sha>` 得到改动文件,套用 4.3 的映射:

- 无任何命中 → 直接放行,**不启动 Docker**(与 pre-commit 对非 Python 改动的处理一致)
- 有命中 → 拉起测试栈并执行,失败则拦截

`core.hooksPath` 已在 lint 侧指向 `.githooks`,因此 pre-push 无需额外配置即可生效。

## 6. 失败与边界处理

- **Docker 不可用** → 拦截并提示 `git push --no-verify` 可跳过。与既有 pre-commit 的行为保持一致:门禁行为可预期,是否放行由人决定,而不是脚本替人决定。
- **首次建库** → 在开始前明确打印「首次需约 7 分钟创建测试库,后续复用」,避免看起来像卡死。
- **测试失败** → 打印失败用例摘要与完整日志文件路径,便于直接定位。
- **迁移陈旧** → 见第 7 节。

## 7. 与 CI 的已知差异

只有一处刻意的差异:**预检使用 `--keepdb`,CI 每次新建库**。

代价是,当既有迁移文件被**改写或删除**时,本地测试库会与迁移状态不一致(新增迁移无妨,`--keepdb` 仍会正常 apply)。为此提供 `--fresh-db` 强制重建,并在文档中写明触发条件。

其余两点不构成执行差异,但需要知晓:

- 薄镜像的基础是 `atm-erp-app:<版本>`,构建于某个时点。若 `requirements.txt` 之后发生变更,镜像中的依赖会滞后于 CI。脚本会打印所用的基础镜像 tag,`requirements*.txt` 出现在改动中时给出提示。
- 分组① 的 336 秒是本机实测值,与机器负载相关,不同环境会有出入。

## 8. 验证策略

不以「跑一次绿了」作为验收标准。实现完成后逐条验证:

1. **能拦住真实失败** — 临时引入一个必然失败的用例,确认 `git push` 被拦截且报错指向该用例。
2. **映射精确** — 只改 `backend/apps/finance/models.py`,确认仅触发分组④ + integration,不触发其它分组。
3. **core 放大生效** — 只改 `backend/apps/core/models.py`,确认触发全部 4 组 + integration。
4. **无关改动零开销** — 只改 `docs/` 下文件,确认秒级放行且完全不启动 Docker。
5. **逃生门可用** — 确认 `git push --no-verify` 能跳过预检。
6. **生产库未被触碰** — 全流程结束后核对生产 `erp-postgres` 中不存在新增的 `test_*` 数据库。

## 9. 遗留事项

- 本机生产 PG 实例中残留有 6 个历史测试库(约 320MB),来自本设计之前的手工试跑。它们与生产数据同库共存,建议清理,但**属于本设计范围之外的独立决定**,需用户拍板后单独处理。
