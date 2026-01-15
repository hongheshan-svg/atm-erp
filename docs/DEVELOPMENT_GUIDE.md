# ERP系统开发指南

**版本：1.0**  
**更新日期：2026年1月15日**

---

## 目录

1. [开发环境要求](#1-开发环境要求)
2. [技术栈](#2-技术栈)
3. [开发工具](#3-开发工具)
4. [环境搭建](#4-环境搭建)
5. [项目结构](#5-项目结构)
6. [开发规范](#6-开发规范)
7. [调试与测试](#7-调试与测试)
8. [部署说明](#8-部署说明)

---

## 1. 开发环境要求

### 1.1 硬件要求

| 项目 | 最低配置 | 推荐配置 |
|------|----------|----------|
| CPU | 4核 | 8核 |
| 内存 | 8GB | 16GB |
| 硬盘 | 50GB SSD | 100GB SSD |
| 网络 | 内网 | 千兆网络 |

### 1.2 操作系统

| 操作系统 | 版本 | 支持情况 |
|----------|------|----------|
| Ubuntu | 20.04/22.04/24.04 LTS | ✅ 推荐 |
| CentOS | 8+ | ✅ 支持 |
| macOS | 12+ | ✅ 支持 |
| Windows | 10/11 + WSL2 | ✅ 支持 |

### 1.3 必需软件版本

| 软件 | 版本要求 | 说明 |
|------|----------|------|
| Python | 3.10+ | 后端运行环境 |
| Node.js | 18+ | 前端构建工具 |
| PostgreSQL | 15+ | 主数据库 |
| Redis | 7+ | 缓存/消息队列 |
| Docker | 24+ | 容器化部署（可选） |
| Git | 2.30+ | 版本控制 |

---

## 2. 技术栈

### 2.1 后端技术栈

```
Python 3.11
├── Django 4.2              # Web框架
│   ├── Django REST Framework 3.14  # RESTful API
│   ├── Django Channels 4.0         # WebSocket支持
│   ├── Django Filter 23.5          # 数据过滤
│   └── DRF Spectacular 0.27        # API文档生成
│
├── 数据库
│   ├── psycopg2-binary 2.9  # PostgreSQL驱动
│   └── django-redis 5.4     # Redis缓存后端
│
├── 异步任务
│   ├── Celery 5.3           # 分布式任务队列
│   ├── celery-beat          # 定时任务调度
│   └── redis 5.0            # 消息代理
│
├── 搜索引擎
│   ├── elasticsearch 7.17   # 全文搜索
│   ├── elasticsearch-dsl 7.4
│   └── django-elasticsearch-dsl 7.3
│
├── 文档生成
│   ├── reportlab 4.0        # PDF生成
│   ├── openpyxl 3.1         # Excel读写
│   ├── xlsxwriter 3.1       # Excel写入
│   ├── python-barcode 0.15  # 条形码生成
│   └── qrcode 7.4           # 二维码生成
│
├── 图像处理
│   └── Pillow 10.1          # 图像处理
│
└── 工具库
    ├── python-decouple 3.8  # 环境变量管理
    ├── python-dateutil 2.8  # 日期处理
    ├── pytz 2023.3          # 时区处理
    └── requests 2.31        # HTTP客户端
```

### 2.2 前端技术栈

```
Node.js 18+
├── Vue 3                    # 前端框架
│   ├── Composition API      # 组合式API
│   ├── Script Setup         # 语法糖
│   └── Vue Router 4         # 路由管理
│
├── 构建工具
│   └── Vite 5               # 构建打包
│
├── 状态管理
│   └── Pinia                # 状态管理（替代Vuex）
│
├── UI框架
│   ├── Element Plus         # 组件库
│   └── @element-plus/icons-vue  # 图标库
│
├── 图表可视化
│   ├── ECharts 5            # 图表库
│   ├── vue-echarts          # Vue封装
│   └── @toast-ui/vue-gantt  # 甘特图
│
├── HTTP请求
│   └── Axios                # HTTP客户端
│
└── 工具库
    ├── dayjs                # 日期处理
    ├── xlsx                 # Excel导出
    └── lodash-es            # 工具函数
```

### 2.3 基础设施

```
Docker & Docker Compose
├── PostgreSQL 15-alpine     # 数据库
├── Redis 7-alpine           # 缓存/消息队列
├── Elasticsearch 7.17       # 搜索引擎
├── Nginx                    # 反向代理/静态文件
├── Gunicorn/Daphne          # WSGI/ASGI服务器
└── Certbot                  # SSL证书（可选）
```

---

## 3. 开发工具

### 3.1 推荐IDE/编辑器

| 工具 | 用途 | 推荐指数 |
|------|------|----------|
| **VS Code** | 全栈开发 | ⭐⭐⭐⭐⭐ |
| **Cursor** | AI辅助开发 | ⭐⭐⭐⭐⭐ |
| PyCharm | Python后端 | ⭐⭐⭐⭐ |
| WebStorm | Vue前端 | ⭐⭐⭐⭐ |

### 3.2 VS Code 推荐插件

**Python开发**：
```
- Python (Microsoft)
- Pylance
- Python Debugger
- Django
```

**Vue开发**：
```
- Vue - Official (Volar)
- Vue VSCode Snippets
- ESLint
- Prettier
```

**通用工具**：
```
- GitLens
- Docker
- REST Client
- Thunder Client
- Database Client
- Markdown Preview Enhanced
```

### 3.3 浏览器开发工具

| 工具 | 用途 |
|------|------|
| Chrome DevTools | 前端调试 |
| Vue.js Devtools | Vue组件调试 |
| Redux DevTools | 状态调试 |

### 3.4 数据库管理工具

| 工具 | 说明 | 平台 |
|------|------|------|
| **DBeaver** | 通用数据库工具 | 跨平台 |
| pgAdmin 4 | PostgreSQL专用 | 跨平台 |
| Navicat | 商业数据库工具 | 跨平台 |
| TablePlus | 轻量级数据库工具 | macOS/Win |

### 3.5 API测试工具

| 工具 | 说明 |
|------|------|
| **Postman** | API测试平台 |
| Insomnia | 轻量API客户端 |
| Thunder Client | VS Code插件 |
| curl | 命令行工具 |

### 3.6 版本控制

| 工具 | 说明 |
|------|------|
| Git | 版本控制 |
| GitHub/GitLab | 代码托管 |
| SourceTree | Git GUI客户端 |
| GitKraken | Git GUI客户端 |

### 3.7 文档工具

| 工具 | 用途 |
|------|------|
| Swagger UI | API文档 |
| Markdown | 技术文档 |
| Draw.io | 流程图/架构图 |
| PlantUML | UML图 |

---

## 4. 环境搭建

### 4.1 克隆项目

```bash
git clone <repository-url> erp
cd erp
```

### 4.2 后端环境搭建

```bash
# 1. 创建Python虚拟环境
cd backend
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置数据库等参数

# 4. 数据库迁移
python manage.py migrate

# 5. 创建超级用户
python manage.py createsuperuser

# 6. 启动开发服务器
python manage.py runserver 0.0.0.0:8000
```

### 4.3 前端环境搭建

```bash
# 1. 进入前端目录
cd frontend

# 2. 安装依赖
npm install
# 或使用 pnpm
pnpm install

# 3. 配置环境变量
cp .env.example .env.local
# 编辑 .env.local，配置API地址等

# 4. 启动开发服务器
npm run dev
```

### 4.4 Docker环境搭建（推荐）

```bash
# 1. 复制环境变量文件
cp .env.example .env

# 2. 构建并启动所有服务
docker-compose up -d --build

# 3. 查看服务状态
docker-compose ps

# 4. 查看日志
docker-compose logs -f backend

# 5. 进入后端容器执行命令
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser
```

### 4.5 服务端口说明

| 服务 | 端口 | 说明 |
|------|------|------|
| Nginx | 8080/8443 | HTTP/HTTPS入口 |
| Backend | 8000 | Django API |
| PostgreSQL | 5433 | 数据库 |
| Redis | 6380 | 缓存 |
| Elasticsearch | 9201 | 搜索引擎 |

---

## 5. 项目结构

### 5.1 整体结构

```
erp/
├── backend/                 # Django后端
│   ├── apps/               # 应用模块
│   │   ├── core/          # 核心模块（用户、权限、审批）
│   │   ├── accounts/      # 账户模块
│   │   ├── masterdata/    # 主数据（物料、客户、供应商）
│   │   ├── projects/      # 项目管理
│   │   ├── purchase/      # 采购管理
│   │   ├── sales/         # 销售管理
│   │   ├── inventory/     # 库存管理
│   │   ├── finance/       # 财务管理
│   │   └── analytics/     # 数据分析
│   ├── config/            # Django配置
│   │   ├── settings.py    # 主配置
│   │   ├── urls.py        # URL路由
│   │   └── celery.py      # Celery配置
│   ├── requirements.txt   # Python依赖
│   └── manage.py          # Django管理脚本
│
├── frontend/               # Vue前端
│   ├── src/
│   │   ├── api/          # API接口封装
│   │   ├── assets/       # 静态资源
│   │   ├── components/   # 公共组件
│   │   ├── layout/       # 布局组件
│   │   ├── router/       # 路由配置
│   │   ├── stores/       # Pinia状态管理
│   │   ├── utils/        # 工具函数
│   │   ├── views/        # 页面组件
│   │   ├── App.vue       # 根组件
│   │   └── main.js       # 入口文件
│   ├── public/           # 公共静态资源
│   ├── package.json      # npm依赖
│   └── vite.config.js    # Vite配置
│
├── docker/                 # Docker配置
│   ├── backend/
│   │   └── Dockerfile
│   ├── frontend/
│   │   └── Dockerfile
│   └── ssl/               # SSL证书
│
├── docs/                   # 文档
│   ├── USER_MANUAL.md     # 用户手册
│   ├── DEVELOPMENT_GUIDE.md  # 开发指南
│   ├── SYSTEM-ARCHITECTURE.md # 架构说明
│   ├── output/            # 生成的文档
│   └── screenshots/       # 系统截图
│
├── docker-compose.yml      # Docker编排
├── .env.example           # 环境变量示例
└── README.md              # 项目说明
```

### 5.2 后端应用结构（以projects为例）

```
apps/projects/
├── __init__.py
├── admin.py               # Django Admin配置
├── apps.py                # 应用配置
├── models.py              # 数据模型
├── serializers.py         # DRF序列化器
├── views.py               # 视图/API接口
├── urls.py                # URL路由
├── filters.py             # 过滤器（可选）
├── permissions.py         # 权限类（可选）
├── signals.py             # 信号处理（可选）
├── tasks.py               # Celery任务（可选）
└── migrations/            # 数据库迁移
    └── 0001_initial.py
```

### 5.3 前端视图结构（以projects为例）

```
views/projects/
├── ProjectList.vue        # 项目列表页
├── ProjectDetail.vue      # 项目详情页
├── TaskList.vue           # 任务列表
├── BOMList.vue            # BOM列表
├── GanttChart.vue         # 甘特图
└── components/            # 模块私有组件
    ├── ProjectForm.vue
    └── TaskForm.vue
```

---

## 6. 开发规范

### 6.1 Git提交规范

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type类型**：
| 类型 | 说明 |
|------|------|
| feat | 新功能 |
| fix | Bug修复 |
| docs | 文档更新 |
| style | 代码格式（不影响功能） |
| refactor | 重构 |
| perf | 性能优化 |
| test | 测试 |
| chore | 构建/工具变更 |

**示例**：
```
feat(purchase): 添加采购申请批量导入功能

- 支持Excel模板下载
- 支持项目筛选导入
- 自动更新BOM采购状态

Closes #123
```

### 6.2 Python代码规范

```python
# 1. 遵循PEP8规范
# 2. 使用类型注解
def create_purchase_request(
    project_id: int,
    items: list[dict],
    user: User
) -> PurchaseRequest:
    """
    创建采购申请
    
    Args:
        project_id: 项目ID
        items: 物料列表
        user: 当前用户
        
    Returns:
        创建的采购申请对象
    """
    pass

# 3. 模型定义规范
class PurchaseRequest(models.Model):
    """采购申请模型"""
    
    class Meta:
        verbose_name = '采购申请'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    # 字段定义
    request_no = models.CharField('申请单号', max_length=50, unique=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES)
    
    def __str__(self):
        return self.request_no
```

### 6.3 Vue代码规范

```vue
<template>
  <!-- 模板使用kebab-case -->
  <div class="purchase-request-list">
    <el-button @click="handleCreate">新建</el-button>
    <el-table :data="tableData">
      <!-- ... -->
    </el-table>
  </div>
</template>

<script setup>
// 1. 导入顺序：Vue → 第三方 → 本地
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { usePurchaseStore } from '@/stores/purchase'
import api from '@/api/purchase'

// 2. Props定义
const props = defineProps({
  projectId: {
    type: Number,
    required: true
  }
})

// 3. Emits定义
const emit = defineEmits(['success', 'cancel'])

// 4. 响应式数据
const loading = ref(false)
const tableData = ref([])

// 5. 计算属性
const filteredData = computed(() => {
  return tableData.value.filter(item => item.status === 'pending')
})

// 6. 方法定义（handle开头表示事件处理）
const handleCreate = () => {
  // ...
}

// 7. 生命周期
onMounted(() => {
  loadData()
})
</script>

<style scoped>
/* 使用scoped限定作用域 */
.purchase-request-list {
  padding: 20px;
}
</style>
```

### 6.4 API接口规范

```
# RESTful风格
GET    /api/v1/projects/           # 列表
POST   /api/v1/projects/           # 创建
GET    /api/v1/projects/{id}/      # 详情
PUT    /api/v1/projects/{id}/      # 更新
DELETE /api/v1/projects/{id}/      # 删除

# 自定义动作
POST   /api/v1/projects/{id}/approve/    # 审批
POST   /api/v1/projects/{id}/export/     # 导出
POST   /api/v1/projects/import/          # 批量导入
```

---

## 7. 调试与测试

### 7.1 后端调试

```bash
# Django Shell
python manage.py shell

# 使用IPython增强Shell
pip install ipython
python manage.py shell_plus

# 调试API
python manage.py runserver --noreload

# 查看SQL查询
# 在settings.py中设置 LOGGING
```

### 7.2 前端调试

```bash
# 启动开发服务器（支持热更新）
npm run dev

# 使用Vue DevTools调试
# Chrome安装Vue.js devtools插件

# 查看网络请求
# 浏览器F12 → Network标签
```

### 7.3 单元测试

```bash
# 后端测试
python manage.py test apps.projects.tests

# 前端测试
npm run test
```

### 7.4 API测试

```bash
# 使用curl测试
curl -X GET http://localhost:8000/api/v1/projects/ \
  -H "Authorization: Bearer <token>"

# 使用HTTPie
http GET localhost:8000/api/v1/projects/ \
  Authorization:"Bearer <token>"
```

---

## 8. 部署说明

### 8.1 Docker部署（推荐）

```bash
# 生产环境部署
docker-compose -f docker-compose.prod.yml up -d

# 查看日志
docker-compose logs -f

# 更新部署
git pull
docker-compose up -d --build
```

### 8.2 原生部署

参考 `docs/UBUNTU-NATIVE-DEPLOYMENT.md`

### 8.3 常用运维命令

```bash
# 查看服务状态
docker-compose ps

# 重启服务
docker-compose restart backend

# 查看日志
docker-compose logs -f backend --tail=100

# 进入容器
docker-compose exec backend bash

# 数据库备份
docker-compose exec postgres pg_dump -U erp_user erp_db > backup.sql

# 数据库恢复
cat backup.sql | docker-compose exec -T postgres psql -U erp_user erp_db
```

---

## 附录

### A. 常用命令速查

| 命令 | 说明 |
|------|------|
| `python manage.py makemigrations` | 生成迁移文件 |
| `python manage.py migrate` | 执行迁移 |
| `python manage.py createsuperuser` | 创建管理员 |
| `python manage.py collectstatic` | 收集静态文件 |
| `npm run build` | 前端生产构建 |
| `npm run lint` | 代码检查 |

### B. 环境变量说明

| 变量 | 说明 | 示例 |
|------|------|------|
| DEBUG | 调试模式 | True/False |
| SECRET_KEY | Django密钥 | 随机字符串 |
| DB_HOST | 数据库主机 | localhost |
| DB_NAME | 数据库名 | erp_db |
| DB_USER | 数据库用户 | erp_user |
| DB_PASSWORD | 数据库密码 | *** |
| REDIS_URL | Redis地址 | redis://localhost:6379/1 |

### C. 参考资源

- [Django官方文档](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Vue 3官方文档](https://vuejs.org/)
- [Element Plus](https://element-plus.org/)
- [Vite官方文档](https://vitejs.dev/)

---

*本文档最后更新于2026年1月15日*
