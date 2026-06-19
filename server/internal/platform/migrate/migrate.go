// Package migrate 用 golang-migrate 跑增量 SQL 迁移(//go:embed)。
// 共库策略(ADR-004):Django 的 161 条迁移为权威 schema,Go 增量从 migrations/ 起,
// baseline 仅落标记表;161 条不重放。
package migrate

import (
	"database/sql"
	"embed"
	"errors"
	"fmt"

	"github.com/atm-erp/server/internal/platform/config"
	"github.com/golang-migrate/migrate/v4"
	migpg "github.com/golang-migrate/migrate/v4/database/postgres"
	"github.com/golang-migrate/migrate/v4/source/iofs"
	_ "github.com/jackc/pgx/v5/stdlib"
)

//go:embed migrations/*.sql
var migrationsFS embed.FS

// Up 应用所有未执行的增量迁移(幂等;无变更时不报错)。
func Up(cfg *config.Config) error {
	src, err := iofs.New(migrationsFS, "migrations")
	if err != nil {
		return fmt.Errorf("加载迁移源: %w", err)
	}
	db, err := sql.Open("pgx", cfg.DSN())
	if err != nil {
		return fmt.Errorf("打开数据库: %w", err)
	}
	defer func() { _ = db.Close() }()

	drv, err := migpg.WithInstance(db, &migpg.Config{})
	if err != nil {
		return fmt.Errorf("初始化迁移驱动: %w", err)
	}
	m, err := migrate.NewWithInstance("iofs", src, "postgres", drv)
	if err != nil {
		return fmt.Errorf("初始化迁移器: %w", err)
	}
	if err := m.Up(); err != nil && !errors.Is(err, migrate.ErrNoChange) {
		return fmt.Errorf("执行迁移: %w", err)
	}
	return nil
}
