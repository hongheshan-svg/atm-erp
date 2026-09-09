# 精简后端

仅 core、accounts、business；配置来自进程环境。安装与完整业务说明见根 README.md。

安装 `pip install -r requirements-dev.txt`，为新库配置 SECRET_KEY、DB_HOST、DB_NAME、DB_USER、DB_PASSWORD、REDIS_URL、ADMIN_PASSWORD，然后运行 `python manage.py migrate`、`python manage.py init_system`、`python manage.py runserver`。

init_system 只创建缺失的管理员，不重置已有密码。旧版数据库、定向迁移、fake 和回滚会被保护机制拒绝。不能清库绕过。

根目录运行 `bash scripts/precheck-tests.sh --all` 在独立 PostgreSQL 容器执行平台、业务和并发验证。测试目标以 scripts/ci/backend_test_matrix.py 为唯一来源。
