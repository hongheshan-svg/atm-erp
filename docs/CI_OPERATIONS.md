# GitHub 验证与发布操作

## 默认按影响验证

PR 自动运行 Lean ERP CI。功能分支 push、合并 main 不重复触发同一套验证；同一 PR 的新提交取消旧任务。手动入口默认 suite=auto，只有明确选择 full 才运行完整业务链；发版本由 Release 工作流强制运行 full。

计划由 scripts/ci/impact.py 生成：业务模块、后端测试目标、前端组件用例、浏览器 spec、OTA/安装器，以及计划指纹均进入 Summary。后端用例仍只登记在 scripts/ci/backend_test_matrix.py，模块映射在同文件引用登记项。纯 Markdown 修改只运行计划自检和工作流语法检查。

- 采购规则变更选择采购、库存/预算等直接关联测试和相关页面，不跑销售到收款全链。
- OTA 变更选择升级接口、升级组件/页面及真实升级演练；不附带 ERP 全业务流程。
- 共享核心文件（业务模型、序列化、公共服务与导出、权限与幂等、迁移、配置与依赖、公共前端组件和工具、e2e 公共夹具等）使用 impact.py 中经过审阅的 `SHARED_PATHS` 映射，自动覆盖直接调用它们的模块；公共界面组件另加导航、页签、分页、页面概览和岗位逐页巡检用例。只影响静态检查或测试运行器的配置（`CHECK_ONLY`）只跑对应一侧的检查与单测。
- 跨模块回归（权限加固、并发、导入导出、历次评审整改）登记在其实际覆盖的每个模块下，改动任一模块都会运行。scripts/tests 校验每个后端测试目标和浏览器用例（完整业务链除外）至少属于一个模块，且全部已跟踪源文件都能被计划归类。
- 新增、尚未登记的共享/未知路径仍明确失败并列出路径；补充经过审阅的路径映射或手动指定 modules 后再运行。不得通过空列表、忽略失败或默认全量来隐藏缺口。
- 前端版本字段单独递增与依赖更新区别处理：纯版本变更只执行前端检查；前端或 Python 依赖变化按共享路径覆盖全部业务模块，运行时 Python 依赖还会运行安装器与 OTA。
- 映射是可维护的影响策略，不保证发现任意新增耦合。接口增加新的调用方时同步更新映射及选择测试。

## 并行、缓存与失败门禁

计划通过后，fast、browser、OTA、installers 独立并行，不再让慢任务等待整套 fast。fast 内后端、前端、运维测试也分开，未涉及的类别不启动依赖和数据库。所选检查失败、取消或意外跳过均使 CI gate 失败；并行不是放宽门禁。

依赖按锁文件缓存，浏览器按锁文件缓存 Chromium，Docker 使用构建层缓存。桌面/手机使用独立缓存 scope，避免两个 runner 争写同一缓存；容器内 OTA 新增 BuildKit 缓存。缓存只用于加速，不能代替测试通过凭据。发布的原生依赖增加 pip 缓存；多架构镜像和多平台 wheelhouse 保持并行。

backend 不再默认执行整个 backend 阶段：先静态检查，再运行 JSON 目标列表。前端保留 lint/typecheck/build，仅执行选定单测。浏览器双视口并行、独立数据库；每端先完成首次安装向导以建立隔离账号，再执行指定 spec。空目标不会回退到全量，目标必须属于测试矩阵或实际 spec 路径，不经过 shell 拼接。

## 手动入口

统一使用 Actions → Lean ERP CI → Run workflow：

| 参数 | 含义 |
| --- | --- |
| suite=auto | 从比较基线计算影响范围；默认选项 |
| modules | 共享变更的实际受影响模块，逗号分隔 |
| suite=fast/browser/ota/installers | 仅运行该类诊断，不自动取得完整范围凭据 |
| suite=custom | 选择多个类别；未覆盖计划全部要求时仅算局部诊断 |
| browser_projects | both/desktop/mobile；单视口不给完整范围凭据 |
| suite=full | 显式全量，包含完整业务链与双视口 |

模块值：sales、projects、bom、purchases、inventory、finance、masterdata、accounts、reports、ota。PR 基线为目标分支提交；手动 auto 默认比较 HEAD 之前最近匹配的版本 tag，发布则比较前一正式 tag。未知基线或未知路径失败，不静默假定没有变更。

示例（只选择实际受影响模块）：

```bash
gh workflow run ci.yml --ref feature/example -f suite=auto -f modules=purchases,inventory
gh workflow run ci.yml --ref feature/example -f suite=browser -f modules=ota -f browser_projects=mobile
# 仅明确要求全量时
gh workflow run ci.yml --ref feature/example -f suite=full -f browser_projects=both
```

Fast checks 和 Browser validation 作为可复用子流程，由统一入口传入非歧义目标；不再提供无目标的独立手动入口。OTA/Installer 子流程仍可独立诊断，但不能单独作为发布凭据。

## 发布门禁与证据复用

1. 功能分支更新一致版本与发布说明，完成相应验证，合并 main 后打正式 tag。**发版本必须全量验证**，按影响范围的结果不能代替。
2. Release 检查 tag 在 main 历史、前后端版本一致、Installation/Documentation 区块、目标未公开发布，再计算前一正式 tag 到目标提交的完整变更范围。
3. 优先复用本仓库成功 CI：必须存在同一 Git tree 成功的 Full validation 标记。Scoped validation、CI gate、单视口或局部诊断都不能作为发布凭据。
4. 没有匹配记录时 Release 以 suite=full、双视口运行全量验证：全部后端阶段（平台、业务、并发）与前端单测、含完整业务链的全部浏览器用例、OTA 与安装器，约 20 分钟。force_validation 强制重跑全量。前一正式 tag 到本次的差异只写入发布摘要，不再缩小验证范围。不修改已存在 tag 来绕过失败。
5. wheelhouse 可与验证并行准备；全部选中检查通过后才进入镜像构建、最终打包和发布。三平台 native/docker 六包、双架构预构建镜像、离线 wheelhouse、来源及上传哈希检查保留。只有发布 job 具备 contents 写权限；公开版本拒绝覆盖，草稿可重试。

```bash
# 可选：打 tag 前先对 main 跑全量，Release 会复用同 tree 的 Full validation
gh workflow run ci.yml --ref main -f suite=full -f browser_projects=both
gh workflow run release.yml --ref main -f tag=vX.Y.Z -F publish=false
```

tag push 默认正式发布，手动默认草稿；发布按 tag 串行且不取消进行中任务。复用最多查询最近100次成功 CI，未找到就跑影响范围，查询错误直接失败。首次发布没有历史正式 tag 时需先明确基线，不能自动认定已验证。

## OTA 与交付物覆盖边界

Docker 旧宿主机升级保留 classic/containerd 两种镜像存储，使用归档 config 摘要验证兼容，不能只在同一引擎导出再导入。原生升级、三平台安装器和 Linux 重复安装仍独立验证。

容器内 OTA 检查直接 Compose 启动及真实心跳、待重启持久化、程序校验、离线依赖、先备份后迁移、强杀进程恢复、新版本健康及重建保留。备份在独立空数据库实际还原。fixture-from-image 是本地发布/依赖夹具，不证明正式远端下载或另一架构；真实包可通过 native-package 参数检查相应依赖。基础运行时变化仍须遵循 docker/app/runtime-protocol.json，不静默强行迁移。

Summary 和失败日志用于说明执行了什么，不把跳过项读成通过。浏览器截图/trace 保留7天，发布包保留14天。本轮工作流优化已通过 121 项本地 CI/安装运维脚本测试、修改的 CI Python 文件 Ruff 检查及 actionlint；没有执行全业务流程测试。远端验证与发布结果见 PR #80 及对应 Actions，不以本地通过推断远端全绿。Windows 脚本测试显式使用 UTF-8；离线容器演练提前拉取 PostgreSQL/Redis 基础镜像，不依赖 runner 的已有镜像缓存。
