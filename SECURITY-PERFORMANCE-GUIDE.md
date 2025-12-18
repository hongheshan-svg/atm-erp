# ERP系统安全与性能指南

## 一、安全配置

### 1. HTTPS配置

#### 开发环境（自签名证书）
```bash
# 生成自签名证书
./scripts/generate-ssl.sh localhost
```

#### 生产环境（Let's Encrypt）
```bash
# 使用certbot获取证书
sudo certbot certonly --standalone -d your-domain.com

# 复制证书到nginx目录
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ./nginx/ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ./nginx/ssl/
```

### 2. 安全设置清单

在 `.env.prod` 中配置：

```env
# 必须修改
SECRET_KEY=your-random-secret-key
DEBUG=False
ALLOWED_HOSTS=your-domain.com

# HTTPS设置
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000

# 密码策略
PASSWORD_MIN_LENGTH=8
PASSWORD_REQUIRE_UPPERCASE=True
PASSWORD_REQUIRE_DIGIT=True
PASSWORD_REQUIRE_SPECIAL=True
PASSWORD_EXPIRY_DAYS=90

# 登录安全
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION_MINUTES=30
```

### 3. 运行安全检查

```bash
cd backend
python manage.py security_check
```

检查项目：
- ✓ DEBUG模式
- ✓ SECRET_KEY安全性
- ✓ ALLOWED_HOSTS配置
- ✓ HTTPS设置
- ✓ 数据库密码
- ✓ CORS配置
- ✓ 密码验证器
- ✓ 默认管理员账户
- ✓ 文件权限
- ✓ JWT设置
- ✓ 日志配置
- ✓ 安全中间件

### 4. 安全中间件

已实现的安全中间件（`backend/apps/core/security_middleware.py`）：

| 中间件 | 功能 |
|--------|------|
| RateLimitMiddleware | API请求频率限制 |
| SecurityHeadersMiddleware | 安全响应头 |
| SQLInjectionProtectionMiddleware | SQL注入检测 |
| XSSProtectionMiddleware | XSS攻击检测 |
| RequestLoggingMiddleware | 请求日志记录 |

启用方式（在settings.py的MIDDLEWARE中添加）：
```python
MIDDLEWARE = [
    # ... 其他中间件
    'apps.core.security_middleware.RateLimitMiddleware',
    'apps.core.security_middleware.SecurityHeadersMiddleware',
    'apps.core.security_middleware.SQLInjectionProtectionMiddleware',
    'apps.core.security_middleware.XSSProtectionMiddleware',
    'apps.core.security_middleware.RequestLoggingMiddleware',
]
```

### 5. 安全响应头

自动添加的安全头：
- `Content-Security-Policy` - 内容安全策略
- `X-Content-Type-Options: nosniff` - 防止MIME类型嗅探
- `X-XSS-Protection: 1; mode=block` - XSS保护
- `X-Frame-Options: DENY` - 防止点击劫持
- `Referrer-Policy: strict-origin-when-cross-origin` - 引用策略
- `Permissions-Policy` - 权限策略

## 二、性能优化

### 1. 运行性能检查

```bash
cd backend
python manage.py performance_check
```

检查项目：
- 数据库延迟和表大小
- Redis缓存命中率
- 慢查询分析
- 索引使用情况
- Celery工作状态
- 系统资源使用

### 2. 数据库优化

#### 添加索引
```python
# 在模型Meta中添加索引
class Meta:
    indexes = [
        models.Index(fields=['status', 'created_at']),
        models.Index(fields=['customer', 'order_date']),
    ]
```

#### 使用select_related和prefetch_related
```python
# 优化外键查询
orders = SalesOrder.objects.select_related('customer', 'project')

# 优化多对多查询
orders = SalesOrder.objects.prefetch_related('items')
```

### 3. 缓存策略

```python
from apps.core.performance import cache_result

@cache_result(timeout=300, key_prefix='dashboard')
def get_dashboard_data():
    # 耗时计算
    return data
```

### 4. 查询调试

```python
from apps.core.performance import query_debugger

@query_debugger
def my_view(request):
    # 自动记录SQL查询数量和时间
    return response
```

## 三、健康检查API

| 端点 | 权限 | 说明 |
|------|------|------|
| `/api/core/health/` | 公开 | 基本健康检查 |
| `/api/core/health/ready/` | 公开 | 就绪检查（含依赖） |
| `/api/core/health/status/` | 管理员 | 详细系统状态 |
| `/api/core/health/security/` | 管理员 | 安全配置状态 |

## 四、生产部署

### 1. 使用生产配置启动

```bash
# 复制生产环境配置
cp backend/.env.prod.example backend/.env

# 编辑配置文件
nano backend/.env

# 重启服务
sudo systemctl restart erp-backend erp-celery
```

### 2. SSL证书配置

使用Let's Encrypt获取免费SSL证书：
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

证书会自动续期（certbot自动配置cron任务）。

### 3. 日志监控

日志位置：
- Nginx: `/var/log/nginx/`
- Django: `/var/log/erp/`
- 系统服务: `journalctl -u erp-backend`

### 4. 备份策略

```bash
# 数据库备份
sudo -u postgres pg_dump erp_db > backup_$(date +%Y%m%d).sql

# Redis备份
redis-cli BGSAVE

# 使用管理脚本备份
sudo /opt/erp/scripts/manage-native.sh backup
```

## 五、安全最佳实践

1. **定期更新依赖** - 使用 `pip-audit` 检查漏洞
2. **定期轮换密钥** - SECRET_KEY、数据库密码等
3. **监控异常登录** - 查看登录日志
4. **定期安全审计** - 运行 `security_check` 命令
5. **最小权限原则** - 用户只授予必要权限
6. **数据加密** - 敏感数据加密存储
7. **备份验证** - 定期测试备份恢复

## 六、性能监控建议

1. 使用 APM 工具（如 Sentry、New Relic）
2. 设置慢查询告警
3. 监控 Redis 内存使用
4. 监控 Celery 队列长度
5. 设置资源使用告警阈值
