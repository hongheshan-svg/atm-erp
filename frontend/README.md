# 精简前端

Vue 3 + TypeScript + Element Plus；十个入口按权限显示，以项目串联交付和售后。经营报表仅管理员和单独授权的经理账号可见。所有网络调用经 src/api 和 src/utils/request.ts，JWT 刷新及退出会话统一处理。

列表统一使用 ListPagination 和 pagination.ts，默认每页10条，可选10/20/50/100并保存浏览器偏好；ResourcePanel、经营报表和 BOM 共用。BOM 本地分页只影响展示，导入确认仍提交全部预览行。长表格最大高度560px，桌面侧栏保持随滚动可见，深色背景延伸到整页底部。

TransferTools 提供业务列表的 Excel/CSV 导出及有权资源的模板/预览/确认导入。导出传递已应用的筛选条件，忽略当前页；设置资源不显示这些入口。导入预览采用共享分页，确认提交服务端签名凭据；后端重验并整批保存。导入弹窗在短视口内部滚动，确认与关闭按钮保留可见。下载错误通过统一请求层还原 JSON 错误消息，附件下载继续复用同一鉴权入口。

BOMPurchasePicker 在采购列表和项目BOM复用，支持品牌/单元/标准件类别的多选组合过滤和跨页勾选。筛选变更保留选择，项目变更清空；选择后再次读取缺口，只带选中行进入采购表单，表单不能增加未勾选项。全局原生input样式排除ElSelect内部输入，避免影响组件布局和键盘操作。

`npm ci` 后运行 `npm run dev`，默认 18310 端口；通过 VITE_API_BASE_URL 设置 API 代理目标。

检查：`npm run lint`、`npm run typecheck`、`npm run test`、`npm run build`。

浏览器验证：`E2E_BASE_URL=http://127.0.0.1:18320 E2E_ADMIN_PASSWORD=测试管理员密码 npm run test:e2e`。必须使用隔离测试环境，测试从界面创建用户、项目、采购、库存及收付款。没有密码会失败，不会以跳过冒充通过。
