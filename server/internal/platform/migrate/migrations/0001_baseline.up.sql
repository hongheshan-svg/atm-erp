-- baseline:共库迁移。Django 的 161 条迁移为权威 schema,Go 增量从本目录起。
-- 本文件仅落一个标记表,验证 golang-migrate 链路可用,且对共库无破坏(IF NOT EXISTS)。
CREATE TABLE IF NOT EXISTS erp_go_migrations_marker (
    id         bigserial PRIMARY KEY,
    note       text NOT NULL DEFAULT 'go-rewrite increments start here',
    applied_at timestamptz NOT NULL DEFAULT now()
);
