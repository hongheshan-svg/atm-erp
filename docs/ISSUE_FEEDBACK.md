# 问题反馈与自动修复

员工在 ERP 的「问题反馈」页提交问题，服务端把它建成本仓库的公开 GitHub Issue；维护者在本机开一个专用的 Claude Code 会话，用 `/loop` 持续处理这些 issue、提交修复并按节奏发版。

## 员工使用

- 左侧导航「问题反馈」，或任意页面右上角「反馈问题」（会自动带上当前页面路径）。
- 填写类型、标题、问题描述，可选复现步骤、相关页面和错误提示里的“错误编号”。
- 下方列表显示所有已提交的问题和处理状态（处理中 / 已解决 / 不处理），点编号可打开 GitHub 页面。状态每两分钟最多从 GitHub 同步一次。

## 公开与隐私

- 仓库公开，issue 任何人可见。页面上有提示：不要填写客户名称、金额、联系方式、账号或密码。
- issue 正文只写类型、版本、页面路径（只保留 `resource`/`section` 参数，搜索词等不会写入）、提交人岗位代码、错误编号和浏览器信息；用户填写的文字放在代码块里，@提及、链接、图片和 HTML 都不会生效。
- 提交人姓名不写进 issue，只记录在本地反馈记录和「操作审计」（`feedback.submit`）里。

## 管理员配置 GitHub 连接

1. 用维护者账号在 GitHub 打开 Settings → Developer settings → Fine-grained tokens，新建令牌：Repository access 只选 `hongheshan-svg/atm-erp`，Repository permissions 只给 **Issues: Read and write**，有效期按需要设置。
2. 以管理员登录 ERP，打开「问题反馈」页底部「GitHub 连接」，粘贴 `github_pat_…` 保存。保存时会校验令牌能访问仓库；令牌只存在服务器数据库，任何接口都不回显。
3. 令牌过期或要停用时，在同一处换新令牌或点「停用」。未配置时员工能看到列表，但不能提交。

每个账号每小时最多提交 20 条。服务器需要能访问 `api.github.com`（与在线升级相同）。

## 标签约定

| 标签 | 含义 |
| --- | --- |
| `from-erp` | ERP 提交（由维护者令牌创建，自动带上） |
| `claude-fix` | 维护者手动把任意 issue 交给自动修复 |
| `claude-working` / `fixed-pending-release` / `needs-human` | 自动修复循环的处理状态 |

只有仓库协作者能给 issue 加标签，所以外部人员开的 issue 不会进入自动处理；需要处理时由维护者手动加 `claude-fix`。

## 自动修复循环

规则写在 `.claude/skills/erp-issue-loop/SKILL.md`：只处理维护者打过可信标签的 issue，issue 内容一律当作数据、不执行其中的指令；改动限于业务代码与测试，不碰 CI、安装、升级和依赖；PR 检查全绿才合并；每 24 小时最多发一次版，发版后回帖并关闭对应 issue。

启动（在维护者本机，一个专门用于循环的克隆里）：

```bash
git clone https://github.com/hongheshan-svg/atm-erp.git ~/atm-erp-loop
cd ~/atm-erp-loop/frontend && npm ci && cd ..
# 可选：导出 PG_TEST_HOST/PG_TEST_PORT/PG_TEST_USER/PG_TEST_PASSWORD 和 SECRET_KEY，循环会先在本机跑后端测试；不导出则以 PR 的 CI 为准。
claude
```

在会话中输入 `/loop /erp-issue-loop`（不带间隔，循环按情况自行安排下一次检查），或 `/loop 30m /erp-issue-loop` 固定每 30 分钟一轮。会话需要能不经确认地运行 `git`、`gh`、测试命令（例如使用自动模式），且本机 `gh` 已登录维护者账号。关闭会话或按 Esc 中断即停止；处理进度都在 GitHub 标签上，重新启动后会接着处理。
