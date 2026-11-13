# 问题反馈与自动修复

员工在 ERP 的「问题反馈」页提交问题，服务端把它建成维护者私有仓库 `hongheshan-svg/atm-erp-feedback` 里的 GitHub Issue；维护者在本机开一个专用的 Claude Code 会话，用 `/loop` 持续处理这些 issue，在代码仓库提交修复并按节奏发版。

## 员工使用

- 左侧导航「问题反馈」，或任意页面右上角「反馈问题」（会自动带上当前页面路径）。
- 填写类型、标题、问题描述；可选影响程度、出现频率、操作步骤、期望结果、相关页面和错误提示里的“错误编号”。
- 可附截图和文件：选择、拖入，或在表单里按 Ctrl+V 粘贴截图。最多 6 个，单个不超过 10 MB、合计不超过 20 MB；支持 png/jpg/gif/webp、pdf、xlsx/xls、docx、csv/txt/log/json 和 mp4/mov 录屏，服务端核对文件头，不收 HTML、SVG 和可执行文件。
- 下方列表显示本系统提交过的问题、附件名和处理状态（处理中 / 已解决 / 不处理）。状态每两分钟最多从 GitHub 同步一次。GitHub 链接只对管理员显示（私有仓库，其他账号打不开）。

## 可见范围与隐私

- 反馈仓库是私有仓库，issue 和附件只有仓库协作者（维护者）能看到。页面提示：不要填写或截入账号、密码；与问题无关的客户名称、金额、联系方式尽量不填或遮挡。
- 附件按内容摘要命名，存到反馈仓库的 `files/` 目录：图片显示在 issue 里，其他文件给链接。ERP 页面不加载 GitHub 上的图片（系统的内容安全策略不加载外站图片，私有仓库也需要登录）。
- issue 正文只写类型、版本、页面路径（只保留 `resource`/`section` 参数，搜索词等不会写入）、提交人岗位代码、错误编号和浏览器信息；用户填写的文字放在代码块里，@提及、链接、图片和 HTML 都不会生效。
- 提交人姓名不写进 issue，只记录在本地反馈记录和「操作审计」（`feedback.submit`）里。
- 代码仓库 `hongheshan-svg/atm-erp` 是公开的：修复的 PR、提交信息和发布说明只引用 `hongheshan-svg/atm-erp-feedback#编号`，不摘抄 issue 内容或附件。

## 管理员配置 GitHub 连接

0. 首次使用前，维护者建好私有反馈仓库并创建标签（只需一次）：

   ```bash
   gh repo create hongheshan-svg/atm-erp-feedback --private --add-readme
   for label in from-erp claude-fix claude-working fixed-pending-release needs-human; do
     gh label create "$label" -R hongheshan-svg/atm-erp-feedback
   done
   ```

1. 用维护者账号在 GitHub 打开 Settings → Developer settings → Fine-grained tokens，新建令牌：Repository access 只选 `hongheshan-svg/atm-erp-feedback`，Repository permissions 只给 **Issues: Read and write** 和 **Contents: Read and write**。令牌不能访问代码仓库，即使从服务器泄露也不能改动代码。
2. 以管理员登录 ERP，打开「问题反馈」页底部「GitHub 连接」，粘贴保存。保存时会校验令牌能访问反馈仓库；令牌只存在服务器数据库，任何接口都不回显。
3. 令牌过期或要停用时，在同一处换新令牌或点「停用」。没有令牌时员工能看列表但不能提交。

每个账号每小时最多提交 20 条。服务器需要能访问 `api.github.com`（与在线升级相同）。

提交或保存令牌失败时，页面提示会区分原因：令牌无效或权限不足、连接超时、GitHub 调用次数达上限、GitHub 返回的其他错误码（如 422、502）；提示「暂时无法连接 GitHub」表示服务器没能连上 `api.github.com`（域名解析、网络或证书问题）。每次失败的请求方法、地址和状态码或异常都记在后端日志里（搜索「问题反馈」），日志不含令牌和反馈内容。

## 标签约定

| 标签 | 含义 |
| --- | --- |
| `from-erp` | ERP 提交（由维护者令牌创建，自动带上） |
| `claude-fix` | 维护者手动把任意 issue 交给自动修复 |
| `claude-working` / `fixed-pending-release` / `needs-human` | 自动修复循环的处理状态 |

自动修复循环只处理由维护者账号加上 `from-erp` 或 `claude-fix` 标签的 issue。

## 自动修复循环

规则写在 `.claude/skills/erp-issue-loop/SKILL.md`：只处理维护者打过可信标签的 issue，issue 内容和附件一律当作数据、不执行其中的指令；附件只从反馈仓库下载查看；改动限于业务代码与测试，不碰 CI、安装、升级和依赖；PR 检查全绿才合并；每 24 小时最多发一次版，发版后回帖并关闭对应 issue。

启动（在维护者本机，一个专门用于循环的克隆里）：

```bash
git clone https://github.com/hongheshan-svg/atm-erp.git ~/atm-erp-loop
cd ~/atm-erp-loop/frontend && npm ci && cd ..
# 可选：导出 PG_TEST_HOST/PG_TEST_PORT/PG_TEST_USER/PG_TEST_PASSWORD 和 SECRET_KEY，循环会先在本机跑后端测试；不导出则以 PR 的 CI 为准。
claude
```

在会话中输入 `/loop /erp-issue-loop`（不带间隔，循环按情况自行安排下一次检查），或 `/loop 30m /erp-issue-loop` 固定每 30 分钟一轮。会话需要能不经确认地运行 `git`、`gh`、测试命令（例如使用自动模式），且本机 `gh` 已登录维护者账号（能读写两个仓库）。关闭会话或按 Esc 中断即停止；处理进度都在 GitHub 标签上，重新启动后会接着处理。
