# GitHub 验证与发布操作

## 自动运行

- 仅 PR 自动触发 `Lean ERP CI`，功能分支 push 不额外启动同一套任务；同 PR 新提交取消旧验证。合并 main 不重复跑，tag 只触发 Release。
- `plan` 根据差异选任务。纯文档只检查工作流语法及选择逻辑；前端/业务后端执行快速检查和两端浏览器；迁移及核心平台增加 OTA；安装器、依赖、版本号、工作流、未知文件变动执行全量。
- `fast` 前后端并行；通过后启动选中的浏览器、OTA、安装器。桌面和手机使用两台独立 runner、数据库和新安装向导，并行跑各自完整业务链。
- 每次都有 `CI gate`。选中的任务失败、取消或意外跳过，门禁失败。全量且两端通过时，产生 `Full validation (<Git tree>)` 供发布核对。
- 后端使用service PostgreSQL和pip缓存，统一调用 `run_all_tests.py --stage backend`，目标只来自backend_test_matrix.py。浏览器缓存npm、Playwright、Docker构建层。安装器验证当前提交，不固定重打v1.0.0/v1.1.0。

## 单独或组合运行

GitHub **Actions → 对应工作流 → Run workflow** 选择分支：

| 工作流 | 用途 |
| --- | --- |
| Lean ERP CI | `suite=full/fast/browser/ota/installers`；`custom`时勾选多个任务 |
| Fast checks | 仅后端、前端及运维/选择逻辑检查 |
| Browser validation | `projects=desktop/mobile/both`；每端包含首次向导和完整业务链 |
| OTA validation | Docker及原生备份、升级、迁移、数据保留演练 |
| Installer validation | 三平台安装器及当前版本Linux原生安装/重复安装 |
| Release | 指定已存在的正式tag，验证后打包，可只建草稿或正式发布 |

```bash
gh workflow run ci-browser.yml --ref main -f projects=desktop
gh workflow run ci.yml --ref main -f suite=full -f browser_projects=both
gh workflow run ci.yml --ref main -f suite=custom -F fast=true -F installers=true -F browser=false -F ota=false
```

子工作流独立运行用于诊断；发布凭据必须来自同一次Lean ERP CI全量通过，包括两端浏览器。只测桌面、部分组合或不同代码不能当作发布通过。

## 发布

1. 功能分支更新后端/前端版本及 `docs/releases/vX.Y.Z.md`，创建PR；版本变更自动触发全量。
2. CI gate全绿后合并main，创建并推送正式tag，自动触发Release。
3. 检查tag在main历史中、版本一致、说明含Installation/Documentation；查找本仓库ci.yml成功运行中同一Git tree的全量记录。Squash只改提交标识、不改内容时可复用。
4. 有匹配记录直接打包，没有则先跑全量；`force_validation=true`强制重验。查询错误会失败，不静默跳过。
5. 从tag构建三平台 × native/docker六包及SHA256清单。发布job核对本地包来源及远端上传SHA256后公开，只有该job具备contents写权限。

tag push会正式发布；手动运行默认 `publish=false`，仅上传草稿。公开版本拒绝覆盖，草稿重试可更新附件。发布按tag串行且不取消进行中的任务。

```bash
# tag必须已存在且版本匹配，替换示例版本
gh workflow run release.yml --ref main -f tag=vX.Y.Z -F publish=false
```

复用最多检查最近100个成功CI运行；没找到完整凭据就补跑。旧tag若不含新工作流/脚本，沿用 `scripts/package_release.py` 手动补包，不改写已发布tag。历史版本不再参与普通PR的安装验收。

运行Summary显示选中任务、Git tree和复用run id。浏览器截图和trace按desktop/mobile分别保留7天，发布构建附件保留14天。部分任务跳过会明确显示，不能解读为全量通过。
