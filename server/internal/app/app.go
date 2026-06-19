// Package app 装配并启动应用:配置 → 日志 → DB → 路由 → HTTP 服务。
package app

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"

	"github.com/atm-erp/server/internal/iam"
	"github.com/atm-erp/server/internal/masterdata/item"
	"github.com/atm-erp/server/internal/middleware"
	"github.com/atm-erp/server/internal/platform/config"
	"github.com/atm-erp/server/internal/platform/db"
	"github.com/atm-erp/server/internal/platform/obs"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// Serve 启动 HTTP 服务。
func Serve(_ context.Context) error {
	cfg := config.Load()
	if err := cfg.Validate(); err != nil {
		return err
	}
	obs.Setup(cfg.AppEnv)

	ps, err := permissionService(cfg)
	if err != nil {
		return err
	}

	gdb, err := db.Open(cfg)
	if err != nil {
		return fmt.Errorf("数据库连接失败: %w", err)
	}

	r := buildRouter(cfg, gdb, ps)
	slog.Info("erpd serve 启动", "addr", cfg.HTTPAddr, "env", cfg.AppEnv)
	srv := &http.Server{Addr: cfg.HTTPAddr, Handler: r}
	return srv.ListenAndServe()
}

func buildRouter(cfg *config.Config, gdb *gorm.DB, ps iam.PermissionService) *gin.Engine {
	if cfg.AppEnv != "development" {
		gin.SetMode(gin.ReleaseMode)
	}
	r := gin.New()
	r.Use(
		gin.Recovery(),
		middleware.RequestID(),
		middleware.SecurityHeaders(),
		middleware.CORS(cfg.CORSAllowedOrigins),
	)

	// 探针(无需鉴权)。/api/v1/health/ 兼容 erp-updater 的 ERP_HEALTH_URL。
	r.GET("/healthz", func(c *gin.Context) { c.JSON(http.StatusOK, gin.H{"status": "ok"}) })
	r.GET("/api/v1/health/", func(c *gin.Context) { c.JSON(http.StatusOK, gin.H{"status": "ok"}) })
	r.GET("/readyz", func(c *gin.Context) {
		if err := db.Ping(c.Request.Context(), gdb); err != nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{"status": "db_down"})
			return
		}
		c.JSON(http.StatusOK, gin.H{"status": "ready"})
	})

	tm := iam.NewTokenManager(cfg.JWTSecret, cfg.JWTAccessMinutes, cfg.JWTRefreshDays)

	api := r.Group("/api")
	api.Use(middleware.Auth(tm, ps))

	// 参考切片:masterdata/item
	itemHandler := item.NewHandler(item.NewService(item.NewRepo(gdb)))
	itemHandler.Register(api, middleware.RequirePermission)

	return r
}

// permissionService 选择权限服务:非 dev 或未显式 opt-in 时拒绝 fail-open 超管(安全 fail-closed)。
func permissionService(cfg *config.Config) (iam.PermissionService, error) {
	if cfg.AppEnv == "development" && os.Getenv("ERPD_DEV_SUPERUSER") == "1" {
		slog.Warn("⚠ 启用 dev 超管权限服务(StaticPermissionService),仅限本地开发,切勿用于生产")
		return &iam.StaticPermissionService{Superuser: true}, nil
	}
	return nil, errors.New("未接入真实 RBAC PermissionService:仅 development 且 ERPD_DEV_SUPERUSER=1 时允许 dev 超管,否则拒绝启动(见 docs/go-rewrite Phase 1)")
}

// Healthcheck 供容器 distroless 健康检查子命令使用。
func Healthcheck(_ context.Context) error {
	cfg := config.Load()
	resp, err := http.Get("http://127.0.0.1" + cfg.HTTPAddr + "/healthz")
	if err != nil {
		return err
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		return errors.New("unhealthy")
	}
	return nil
}

// Migrate 占位:后续接入 golang-migrate(//go:embed 增量 SQL,161 Django 迁移为 baseline 不重放)。
func Migrate(_ context.Context) error {
	fmt.Println("migrate: 占位(待接入 golang-migrate 增量;见 docs/go-rewrite/30-migration-plan.md)")
	return nil
}
