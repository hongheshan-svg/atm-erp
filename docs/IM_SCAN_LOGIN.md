# 企业微信 / 钉钉 / 飞书 扫码登录 + 首登自动建号

员工用公司企业 IM 扫码即可登录 ERP,首次登录自动建号,免去管理员手动创建用户。

- **新员工**:扫码 → 自动建号(默认 `employee` 最小权限,仅本人数据;管理员事后授权)。
- **老员工(已有 ERP 账号)**:登录后在「个人中心 → 企业 IM 绑定」扫码绑定;此后即可扫码登录。
- **管理员/特权账号**:不能被扫码自动绑定(防接管),只能本人在个人中心绑定或继续用密码登录。

> 信任边界:OAuth 授权限定在企业自建应用内,只有该企业 IM 通讯录成员能扫码授权;新号默认无菜单权限、不越权。

---

## 1. 各平台后台配置

在对应开放平台创建「自建应用 / 网页应用」,拿到凭据并配置**可信回调域**:

| 平台 | 需要的凭据 | 回调域(Redirect)|
|------|-----------|------------------|
| 企业微信 | CorpID、AgentID、应用 Secret | `<FRONTEND_URL>/erp/login/callback` |
| 钉钉 | 扫码登录应用 AppKey / AppSecret(client_id/secret) | 同上 |
| 飞书 | App ID、App Secret | 同上 |

> 回调地址固定为 `${FRONTEND_URL}/erp/login/callback`(后端按 `FRONTEND_URL` 自拼,不取自请求,防开放重定向)。
> 绑定流程复用同一回调,仅多一个 `&mode=bind` 查询参数,**注册回调域时按域名/路径匹配即可**。

## 2. 环境变量(`.env` / `.env.docker`)

```bash
# 企业微信
WECHAT_WORK_CORP_ID=
WECHAT_WORK_CORP_SECRET=
WECHAT_WORK_AGENT_ID=
# 钉钉
DINGTALK_APP_KEY=
DINGTALK_APP_SECRET=
# 飞书
FEISHU_APP_ID=
FEISHU_APP_SECRET=

# 前端回调域(各平台后台需配为可信域)
FRONTEND_URL=https://erp.example.com

# 扫码登录策略
OAUTH_AUTO_CREATE=true            # 新人扫码自动建号(默认开)
OAUTH_NEW_USER_ACTIVE=true        # 新号是否直接激活(false=需管理员激活)
OAUTH_ALLOWED_EMAIL_DOMAINS=      # 可选:仅允许这些邮箱域名自动建号(逗号分隔,空=不限)
OAUTH_DEFAULT_ROLE_CODE=employee  # 自动建号默认角色(data_scope=SELF)
OAUTH_BIND_EXISTING_BY_PHONE=false  # 见 §4
```

只配了哪个平台的 Secret,前端登录页就只显示哪个平台的扫码按钮(后端 `GET /api/auth/oauth/providers` 自动探测)。

## 3. 登录/绑定流程

```
登录:登录页 → 扫码按钮 → 平台授权页(桌面显二维码/IM 内静默) → 回调 /erp/login/callback
     → 后端 code 换身份 → 建号/已绑账号 → 发 JWT(同密码登录)→ 进首页

绑定:个人中心「企业 IM 绑定」→ 扫码绑定 → 平台授权 → 回调(mode=bind)
     → 后端把该 IM 身份绑定到「当前已登录账号」→ 回个人中心(已绑定)
```

## 4. 老员工怎么开通扫码(两种方式,二选一)

ERP 里已存在的账号,**默认不会**被扫码静默绑定(安全,防账号接管)。开通方式:

- **方式 A(推荐,默认):本人自助绑定**
  老员工用账号密码登录 → 个人中心「企业 IM 绑定」→ 扫码绑定自己的企业微信/钉钉/飞书 → 之后即可扫码登录。
  无需管理员、无接管风险(本人登录 + 本人完成 OAuth,双向自证)。

- **方式 B:管理员批量按手机号绑定**
  设 `OAUTH_BIND_EXISTING_BY_PHONE=true`,组织信任「IM 平台核验过的手机号」:非特权老员工扫码时按手机号自动绑定。
  特权账号(superuser/staff/持 system 权限)**始终拒绝**自动绑定。
  > 取舍:更省事,但把信任建立在「IM 手机号 == ERP 手机号」上;若手机号录入有误可能误绑,请确保 ERP 手机号准确。

## 5. 安全设计

- **不接管账号**:首扫**不**凭 email 匹配既有账号(email 易冒名);默认也不凭手机号静默绑定既有账号;特权账号永不自动绑定。
- **登录 CSRF**:`state` 经服务端签名(带过期)**且**绑定到发起扫码的浏览器(HttpOnly+SameSite cookie),回调要求 cookie 与 state 一致;`code` 一次性消费(防重放)。
- **新号 fail-closed**:默认 `employee`(仅本人数据);即便角色分配异常也只能看到本人数据,不越权。
- **SSRF/泄漏防护**:清单与三方请求固定官方域名 + 超时;secret/token/code 不进日志。
- **限流**:登录/扫码端点复用密码登录的 `login` 限流。

## 6. REST 端点

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/auth/oauth/providers` | 否 | 可用登录方式(按是否配 Secret)|
| GET | `/api/auth/oauth/<platform>/login-url[?mode=bind]` | 否 | 扫码授权 URL + state(`mode=bind` 走绑定回调)|
| POST | `/api/auth/oauth/<platform>/callback` | 否 | code+state → 登录(发 JWT,体同密码登录 + `is_new_user`)|
| GET | `/api/auth/oauth/bindings` | 是 | 当前用户各平台绑定状态 |
| POST | `/api/auth/oauth/<platform>/bind` | 是 | 自助绑定(冲突→409)|
| DELETE | `/api/auth/oauth/<platform>/bind` | 是 | 解绑 |

`<platform>` ∈ `wecom` / `dingtalk` / `feishu`。

## 7. 联调前需核对(代码已逐处标注 TODO)

- 三平台「授权 / code 换 token / 用户信息」端点的**当下官方版本与参数**(平台偶有版本变更)。
- 钉钉/飞书 `external_id` 取 `unionId`/`union_id`;现有 `dingtalk_id` 字段亦用于通知发消息(通常需企业 `userid`),
  若通知模块依赖 userid,请确认语义不冲突。
- 真实 code 验证需在各平台后台配好自建应用 + 可信回调域(联调环境)。

## 8. 测试

后端:`python manage.py test apps.accounts.tests.test_oauth_login`(打桩 `resolve_identity`,免真实网络;覆盖
首登建号 / 二次绑定不重复 / 默认拒绝既有匹配 / 特权拒绝 / email 不作匹配键 / state 签名+cookie / code 重放 /
自助绑定需登录 / 绑定冲突 409 / 解绑 / 状态列表)。
