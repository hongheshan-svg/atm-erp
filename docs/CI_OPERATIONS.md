# GitHub 验证与发布操作

## 默认按影响验证

PR 自动运行 Lean ERP CI。功能分支 push、合并 main 不重复触发同一套验证；同一 PR 的新提交取消旧任务。PR 已自动按影响范围验证，不要再对同一分支手动触发 suite=auto——两次运行互不取消，只是把同样的检查跑两遍。手动入口默认 suite=auto，只有明确选择 full 才运行完整业务链；发版本由 Release 工作流强制运行 suite=release（见下文），不含完整业务链。

计划由 scripts/ci/impact.py 生成：业务模块、后端测试目标、前端组件用例、浏览器 spec、OTA/安装器，以及计划指纹均进入 Summary。后端用例仍只登记在 scripts/ci/backend_test_matrix.py，模块映射在同文件引用登记项。纯 Markdown 修改只运行计划自检和工作流语法检查。

- 采购规则变更选择采购、库存/预算等直接关联测试和相关页面，不跑销售到收款全链。
- OTA 变更选择升级接口、升级组件/页面及真实升级演练；不附带 ERP 全业务流程。升级接口模块（`ota`：升级单测与页面用例）和真实升级演练（ci-ota 套件）分开选择：后端升级代码、迁移命令与架构保护、数据库迁移、运行时依赖、Docker/Compose（含 `.dockerignore`、`.env.example`），以及演练执行或导入的脚本才启动演练（`deploy/` 下只有原生配置样例和说明，只启动安装器）；只改升级页面或前端升级接口文件（如 `SystemUpgrade.vue`、`src/api/upgrade.ts`）只跑升级相关单测与页面用例，演练不经过界面。前端单测按文件名整词匹配模块名（驼峰与连字符均为分词边界），`ota` 不再因子串命中 `FinanceTotals.spec.ts`。
- 运维单测（`scripts/tests/test_*.py`）只在 fast/ops 运行，修改单测不启动升级演练；安装器流程另在三平台运行 impact.py `INSTALLER_TESTS` 所列单测，改这几项仍启动安装器；离线 wheelhouse 在三平台默认运行器（Linux x86_64、macOS arm64、Windows x64）之外，另在 `ubuntu-24.04-arm` 与 `macos-15-intel` 上离线安装并导入，覆盖发布包中的全部五种原生架构。scripts/ 下其他文件（含新增文件）默认启动安装器，只有 `NOT_INSTALLER_PATHS` 所列文件例外：独立备份巡检工具（backup_cycle、ops_check）和只由 ci-ota 运行的升级演练脚本。`scripts/tests/test_ci_impact.py` 从 release-installers.yml、ci-ota.yml（含 Dockerfile 复制进镜像的脚本）出发，按导入、执行与文件名引用递归核对：这两个流程运行或导入的每个文件都会选中对应套件，被跳过的文件不在其中；只做 `bash -n` 的 scripts 下 shell 脚本仍选中安装器。
- 共享核心文件（业务模型、序列化、公共服务与导出、权限与幂等、迁移、配置与依赖、公共前端组件和工具、e2e 公共夹具等）使用 impact.py 中经过审阅的 `SHARED_PATHS` 映射，自动覆盖直接调用它们的模块；公共界面组件另加导航、页签、分页、页面概览和岗位逐页巡检用例。只影响静态检查或测试运行器的配置（`CHECK_ONLY`）只跑对应一侧的检查与单测。
- 跨模块回归（权限加固、并发、导入导出、历次评审整改）登记在其实际覆盖的每个模块下，改动任一模块都会运行。scripts/tests 校验每个后端测试目标和浏览器用例（完整业务链除外）至少属于一个模块，且整个仓库的已跟踪文件（`git ls-files` 全量，不限 backend/frontend）都能被计划归类：Markdown 及 docs 下的图片、Office/PDF 文档按文档处理；`.githooks/`、`.gitattributes` 等本地钩子与仓库元数据只运行运维脚本测试；`run_all_tests.py` 按 ci-fast.yml 处理；生成测试命令与分片矩阵的 `scripts/ci/run_selected.py`、`scripts/ci/select_suites.py` 按 ci-fast.yml 加 ci-browser.yml 处理（静态检查、平台用例与 accounts 模块的单测和页面用例），改动当次就实际运行各类命令；`.dockerignore` 与 docker/ 一样运行 OTA 与安装器。
- 新增、尚未登记的共享/未知路径仍明确失败并列出路径；补充经过审阅的路径映射或手动指定 modules 后再运行。不得通过空列表、忽略失败或默认全量来隐藏缺口。
- 前端版本字段单独递增与依赖更新区别处理：纯版本变更只执行前端检查；前端或 Python 依赖变化按共享路径覆盖全部业务模块，运行时 Python 依赖还会运行安装器与 OTA。数据库迁移除全部业务模块外还会运行 OTA 升级演练（升级先备份再前向迁移）。
- 映射是可维护的影响策略，不保证发现任意新增耦合。接口增加新的调用方时同步更新映射及选择测试。

## Python 依赖固定

`backend/requirements.txt` 是人工维护的顶层清单；`backend/constraints.txt` 由 uv 对 Python 3.11 做跨平台解析生成，固定全部传递依赖。Docker 镜像、测试镜像、五种原生 wheelhouse、源码目录原生安装和 CI（`requirements-dev.txt` 内含 `-c constraints.txt`）都按它安装，PR 验证过的版本与 Release 打包的版本一致。macOS 原生包只能用兼容 Intel macOS 12+ / Apple Silicon 14+ 的 wheel，autobahn、cryptography 因此在 requirements.txt 中按 `sys_platform` 分别固定；约束只能按操作系统区分，不能按 CPU 架构（pip 在构建机上求值环境标记，一台机器构建两种架构的 wheelhouse）。升级依赖：修改 requirements.txt 后在仓库根目录运行下面的命令，两个文件一并提交；只升级某个传递依赖时追加 `--upgrade-package <名称>`。命令沿用已有固定版本，不会顺带升级其他依赖。`scripts/tests/test_dependency_pins.py` 离线核对两份清单一致、约束文件不含镜像源或本机路径，且每条安装路径都应用约束；改动任一依赖清单都会运行运维单测，运行时依赖另运行安装器与 OTA。

```bash
uv pip compile --no-config --universal --python-version 3.11 backend/requirements.txt -o backend/constraints.txt
```

## 并行、缓存与失败门禁

计划通过后，fast、browser、OTA、installers 独立并行，不再让慢任务等待整套 fast。fast 内后端、前端、运维测试也分开，未涉及的类别不启动依赖和数据库。所选检查失败、取消或意外跳过均使 CI gate 失败；并行不是放宽门禁。

依赖按锁文件缓存，Docker 使用构建层缓存。Chromium 不缓存：缓存键含锁文件哈希，每次版本号递增都会变，PR 与 tag 写入的缓存别的运行又读不到，实测首轮从未命中，却占用约三分之一的仓库缓存额度；直接下载约 8 秒。浏览器分片把前端依赖、Chromium 及其字体包的安装放到后台，与镜像构建、安装同时进行，装完（失败最多重试两次）才开始向导与用例，每片少等约半分钟；重试只针对这一步网络安装和安装器任务的 apt 下载，任何用例都不重试。计划任务的 actionlint 直接下载固定版本的官方预编译包并核对 SHA256，不再依赖缓存或现场编译；升级版本时同步更新 `ci.yml` 中的校验值。应用镜像的依赖层（apt、pip、npm ci）只由 main 上的 `ci-cache.yml` 写入共享 scope `app-image`（Dockerfile、运行时依赖、`frontend/package.json` 或前端锁文件变化时触发，另每周重建一次防止过期清理）；浏览器分片、容器内 OTA 任务和 Release 的镜像构建只读复用，不再各自导出缓存——PR 的缓存其他 PR 读不到，tag 触发的 Release 写入的缓存也只对同一 tag 可见，导出一次还要多花半分钟到一分钟。版本号合并到 main 时锁文件随之变化，预热流程会构建同一 tree，Release 的 amd64 镜像因此通常全部命中；`app-image` 只有 amd64 层，arm64 镜像仍完整构建。预热流程不运行测试、不产生验证凭据。缓存只用于加速，不能代替测试通过凭据。发布的原生依赖增加 pip 缓存；多架构镜像和多平台 wheelhouse 保持并行。

backend 不再默认执行整个 backend 阶段：先静态检查（Ruff 覆盖 backend、全部 scripts 与 run_all_tests.py；只改 scripts/ 时不启动 backend，ops 任务同样运行这次 Ruff 检查），再运行 JSON 目标列表。所选目标分两次执行：并发阶段（`TARGETS['concurrency']`，多线程抢锁、带超时）串行；其余用例以 `--parallel=auto` 按 CPU 数多进程运行，每个进程使用由 `test_atm_erp_lean` 克隆出的 `test_atm_erp_lean_N` 独立库，仍满足迁移与清库保护的前缀要求。本地 4 进程实测全部 829 个后端用例由 184 秒降到 78 秒；CI 4 核预计由约 4 分钟降到约 2 分钟，以实际运行日志为准。多进程依赖 tblib 把失败回溯传回主进程并逐条报告；它作为固定版本写在 `backend/requirements-dev.txt`，缺少 tblib 的环境自动退回串行。只改变执行方式，不增减用例，`run_all_tests.py` 的本地阶段命令不变。前端保留 lint/typecheck/build，仅执行选定单测。浏览器双视口并行、独立数据库；每端先完成首次安装向导以建立隔离账号，再执行指定 spec。用例较多时，计划把所选 spec 按估算耗时分成最多 4 片，每片在各自的 runner 上用一套独立安装运行，全业务范围的单视口耗时由约 15 分钟降到约 7 分钟；用例少时仍是一片。分片只决定怎么分机器，不改变选中哪些用例：每个 spec 恰好属于一片，任何一片失败、取消或被跳过都使 CI gate 失败。耗时权重登记在 `scripts/ci/select_suites.py` 的 `BROWSER_SECONDS`，只需登记明显偏慢的文件；CI 日志逐条列出用例耗时，某一片明显变慢时据此调整。空目标不会回退到全量，目标必须属于测试矩阵或实际 spec 路径，不经过 shell 拼接。

## 手动入口

统一使用 Actions → Lean ERP CI → Run workflow：

| 参数 | 含义 |
| --- | --- |
| suite=auto | 从比较基线计算影响范围；默认选项 |
| modules | 共享变更的实际受影响模块，逗号分隔 |
| suite=fast/browser/ota/installers | 仅运行该类诊断，不自动取得完整范围凭据 |
| suite=custom | 选择多个类别；未覆盖计划全部要求时仅算局部诊断 |
| browser_projects | both/desktop/mobile；单视口不给完整范围凭据 |
| suite=release | 发版验证：比较前一正式 tag，后端、前端单测与运维脚本测试全部运行；浏览器按改动模块及关联页面（不含完整业务链），OTA 与安装器按相关改动 |
| suite=full | 显式全量，包含完整业务链与双视口 |

模块值：sales、projects、bom、purchases、inventory、finance、masterdata、accounts、reports、ota。PR 基线为目标分支提交；手动 auto 等默认比较 HEAD 之前最近匹配的版本 tag；手动 suite=release 与 Release 共用 `release_gate.release_base`：取低于目标版本（手动时为 `backend/apps/core/version.py` 的版本）的最高正式 tag，预发布 tag 不算，计划指纹因此一致。未知基线或未知路径失败，不静默假定没有变更。

示例（只选择实际受影响模块）：

```bash
gh workflow run ci.yml --ref feature/example -f suite=auto -f modules=purchases,inventory
gh workflow run ci.yml --ref feature/example -f suite=browser -f modules=ota -f browser_projects=mobile
# 仅明确要求全量时
gh workflow run ci.yml --ref feature/example -f suite=full -f browser_projects=both
```

Fast checks 和 Browser validation 作为可复用子流程，由统一入口传入非歧义目标；不再提供无目标的独立手动入口。OTA/Installer 子流程仍可独立诊断，但不能单独作为发布凭据。

## 发布门禁与证据复用

1. 功能分支更新一致版本与发布说明，完成相应验证，合并 main 后打正式 tag。**发版本必须通过发版验证（suite=release）**，PR 的按影响范围结果不能代替。
2. Release 检查 tag 在 main 历史、前后端版本一致、Installation/Documentation 区块、目标未公开发布，再计算前一正式 tag 到目标提交的完整变更范围。
3. 优先复用本仓库成功 CI：同一 Git tree 且计划指纹一致的 Release validation，或同 tree 的 Full validation。Scoped validation、CI gate、单视口或局部诊断都不能作为发布凭据。CI 中找不到时，再查此前 Release 运行内经 workflow_call 执行的发版验证（任务名 `validate / Release validation (<tree> <指纹>)`）：镜像推送或上传失败会使整次 Release 失败，但该标记任务只在 CI gate 确认全部选中套件成功后运行，因此只认这个任务本身成功、tree 与指纹一致，不看整次运行结论。重新派发同一 tag（草稿重试、GHCR 失败后重发）因此不再重跑整套发版验证。
4. 没有匹配记录时 Release 以 suite=release、双视口运行发版验证：全部后端阶段（平台、业务、并发）、全部前端单测与运维脚本测试全部运行；浏览器只跑前一正式 tag 以来改动的模块及关联页面用例（共享核心改动和未登记路径覆盖全部业务模块），不含完整业务链；OTA 在升级代码、数据库迁移、Docker/Compose 或运行时依赖变化时运行，安装器在安装与打包脚本、Docker/部署配置或运行时依赖变化时运行。纯业务或文档发布不启动 OTA 与安装器。force_validation 强制重跑。不修改已存在 tag 来绕过失败。完整业务链只在明确要求时手动运行 suite=full。
5. wheelhouse 可与验证并行准备；全部选中检查通过后才进入镜像构建、最终打包和发布。三平台 native/docker 六包、双架构预构建镜像、离线 wheelhouse、来源及上传哈希检查保留。只有发布 job 具备 contents 写权限；公开版本拒绝覆盖，草稿可重试。

```bash
# 可选：发版 PR 合并后、打 tag 前对 main 跑发版验证（基线与 Release 相同：低于 version.py 版本的最高正式 tag），Release 会复用同 tree 同计划的结果
gh workflow run ci.yml --ref main -f suite=release -f browser_projects=both
gh workflow run release.yml --ref main -f tag=vX.Y.Z -F publish=false
```

tag push 默认正式发布，手动默认草稿；发布按 tag 串行且不取消进行中任务。复用最多查询最近100次成功 CI 和最近100次已结束的 Release（各次运行的任务列表并发查询，结果仍按时间顺序取最近的匹配，预检由约 2～3 分钟降到半分钟内），未找到就由 Release 以 suite=release 补跑发版验证，查询错误直接失败。首次发布没有历史正式 tag 时需先明确基线，不能自动认定已验证。

## OTA 与交付物覆盖边界

Docker 旧宿主机升级保留 classic/containerd 两种镜像存储，使用归档 config 摘要验证兼容，不能只在同一引擎导出再导入。原生升级、三平台安装器和 Linux 重复安装仍独立验证。

容器内 OTA 检查直接 Compose 启动及真实心跳、待重启持久化、程序校验、离线依赖、先备份后迁移、强杀进程恢复、新版本健康及重建保留。备份在独立空数据库实际还原。fixture-from-image 是本地发布/依赖夹具，不证明正式远端下载或另一架构；真实包可通过 native-package 参数检查相应依赖。基础运行时变化仍须遵循 docker/app/runtime-protocol.json，不静默强行迁移。

Summary 和失败日志用于说明执行了什么，不把跳过项读成通过。浏览器截图/trace 保留7天，发布包保留14天。不以本地通过推断远端全绿。Windows 脚本测试显式使用 UTF-8；离线容器演练提前拉取 PostgreSQL/Redis 基础镜像，不依赖 runner 的已有镜像缓存。


### 共享控件引起的完整业务链用例适配

共享表单、按钮或选择器改变时，可以同步更新 `full-chain.spec.ts` 的定位器和辅助函数。该文件的变化本身不把按范围验证提升为完整业务链；影响计划会明确记录“仅在显式 suite=full 时执行”，原业务模块的关联页面与发版验证仍正常运行。只有用户明确要求完整业务链时选择 `suite=full`。
