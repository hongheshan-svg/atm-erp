// Package app 装配并启动应用:配置 → 日志 → DB → 路由 → HTTP 服务。
package app

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"

	"github.com/atm-erp/server/internal/accounts"
	"github.com/atm-erp/server/internal/finance"
	"github.com/atm-erp/server/internal/iam"
	"github.com/atm-erp/server/internal/inventory"
	"github.com/atm-erp/server/internal/masterdata"
	"github.com/atm-erp/server/internal/masterdata/item"
	"github.com/atm-erp/server/internal/middleware"
	"github.com/atm-erp/server/internal/notify"
	"github.com/atm-erp/server/internal/oa"
	"github.com/atm-erp/server/internal/platform/cache"
	"github.com/atm-erp/server/internal/platform/config"
	"github.com/atm-erp/server/internal/platform/db"
	migratepkg "github.com/atm-erp/server/internal/platform/migrate"
	"github.com/atm-erp/server/internal/platform/obs"
	"github.com/atm-erp/server/internal/platform/task"
	"github.com/atm-erp/server/internal/production"
	"github.com/atm-erp/server/internal/projects"
	"github.com/atm-erp/server/internal/purchase"
	"github.com/atm-erp/server/internal/sales"
	"github.com/atm-erp/server/internal/workflow"
	"github.com/atm-erp/server/internal/ws"
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

	gdb, err := db.Open(cfg)
	if err != nil {
		return fmt.Errorf("数据库连接失败: %w", err)
	}

	// 单个 Redis 客户端,权限缓存与 WS 扇出共用(避免双连接池)。Redis 不可用时为 nil,二者各自降级。
	var rc *cache.Redis
	if c, e := cache.NewRedis(cfg.RedisURL); e == nil {
		rc = c
	} else {
		slog.Warn("Redis 不可用,权限不缓存、WS 降级单实例", "err", e)
	}
	ps := permissionService(cfg, gdb, rc)
	r := buildRouter(cfg, gdb, ps, rc)
	slog.Info("erpd serve 启动", "addr", cfg.HTTPAddr, "env", cfg.AppEnv)
	srv := &http.Server{Addr: cfg.HTTPAddr, Handler: r}
	return srv.ListenAndServe()
}

func buildRouter(cfg *config.Config, gdb *gorm.DB, ps iam.PermissionService, rc *cache.Redis) *gin.Engine {
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
	authH := accounts.NewAuthHandler(gdb, tm)

	// 公开端点(无需鉴权):登录、刷新
	authH.MountPublic(r.Group("/api"))

	api := r.Group("/api")
	api.Use(middleware.Auth(tm, ps))
	authH.MountAuthed(api)

	// WebSocket(Sec-WebSocket-Protocol 子协议鉴权)。有 Redis 则启用多实例 Pub/Sub 扇出,
	// 否则降级单实例内存(多副本部署下跨实例推送会失效,日志告警)。
	hub := ws.NewHub()
	if rc != nil {
		if rh, e := ws.NewHubWithRedis(context.Background(), rc.Client(), ws.FanoutChannel); e == nil {
			hub = rh
			slog.Info("WS 启用 Redis Pub/Sub 多实例扇出", "channel", ws.FanoutChannel)
		} else {
			slog.Warn("WS Redis 扇出初始化失败,降级单实例", "err", e)
		}
	} else {
		slog.Warn("Redis 不可用,WS 降级单实例(多副本下跨实例推送失效)")
	}
	r.GET("/ws/notifications", hub.Handler(tm))

	// 参考切片:masterdata/item
	itemHandler := item.NewHandler(item.NewService(item.NewRepo(gdb)))
	itemHandler.Register(api, middleware.RequirePermission)

	// 业务模块路由(本波从 Django 移植生成,逐步验证中)
	perm := middleware.RequirePermission
	accounts.Routes(api, gdb, perm)
	masterdata.Routes(api, gdb, perm)
	sales.Routes(api, gdb, perm)
	purchase.Routes(api, gdb, perm)
	inventory.Routes(api, gdb, perm)
	projects.Routes(api, gdb, perm)
	production.Routes(api, gdb, perm)
	finance.Routes(api, gdb, perm)
	oa.Routes(api, gdb, perm)
	// 站内信(系统通知):落库 + 经 WebSocket Hub 实时推送给本人(hub 直接满足 notify.Pusher)。
	notifySvc := notify.NewService(gdb).SetPusher(hub)
	notify.RoutesWithService(api, notifySvc, perm)
	// 工作流:注入 IAM 真实审批人 resolver + 站内信通知器(任务待办/抄送/结果,带实时推送)。
	wfSvc := workflow.NewService(gdb, workflow.NewCallbackRegistry(), accounts.NewWorkflowResolver(gdb))
	wfSvc.SetNotifier(notify.AsWorkflowNotifier(notifySvc))
	workflow.RoutesWithService(api, wfSvc, perm)

	return r
}

// permissionService 选择权限服务:默认走 GORM RBAC(查 user/role/core_permission 等表);
// 仅在 development 且显式 ERPD_DEV_SUPERUSER=1 时用 dev 超管旁路(安全 fail-closed)。
func permissionService(cfg *config.Config, gdb *gorm.DB, rc *cache.Redis) iam.PermissionService {
	if cfg.AppEnv == "development" && os.Getenv("ERPD_DEV_SUPERUSER") == "1" {
		slog.Warn("⚠ 启用 dev 超管权限服务(StaticPermissionService),仅限本地开发,切勿用于生产")
		return &iam.StaticPermissionService{Superuser: true}
	}
	base := accounts.NewGormPermissionService(gdb)
	if rc == nil {
		return base // Redis 不可用(已在 Serve 告警),权限不缓存
	}
	slog.Info("权限服务启用 Redis 缓存(TTL 5m)")
	return accounts.NewCachedPermissionService(base, rc)
}

// Worker 启动 asynq 异步任务 worker(替代 Celery worker)。
func Worker(_ context.Context) error {
	cfg := config.Load()
	opt, err := task.RedisOpt(cfg.RedisURL)
	if err != nil {
		return err
	}
	gdb, err := db.Open(cfg)
	if err != nil {
		return fmt.Errorf("数据库连接失败: %w", err)
	}
	notifySvc := notify.NewService(gdb)
	// worker 无 WS 端点:有 Redis 时把站内信发布到扇出频道,由 serve 实例投递给在线用户。
	if rc, err := cache.NewRedis(cfg.RedisURL); err == nil {
		notifySvc.SetPusher(ws.NewHubPublisher(rc.Client(), ws.FanoutChannel))
		slog.Info("worker 站内信经 Redis 扇出实时推送")
	}
	wfSvc := workflow.NewService(gdb, workflow.NewCallbackRegistry(), accounts.NewWorkflowResolver(gdb))
	wfSvc.SetNotifier(notify.AsWorkflowNotifier(notifySvc))
	jobs := map[string]func(context.Context) error{
		// 审批超时提醒(对齐 Django check_workflow_deadline_reminders:扫超时待办 → 给审批人发站内信)。
		"workflow:remind_overdue": func(ctx context.Context) error { _, e := wfSvc.RemindOverdue(ctx); return e },
	}
	schedule := map[string]string{"workflow:remind_overdue": "@every 1h"}
	// 不记原始 URL(可能含密码);只记已解析的 addr/db。
	slog.Info("erpd worker 启动(asynq + 定时)", "addr", opt.Addr, "db", opt.DB)
	return task.RunWithJobs(opt, jobs, schedule)
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
	cfg := config.Load()
	if err := migratepkg.Up(cfg); err != nil {
		return err
	}
	fmt.Println("migrate: 增量迁移完成")
	return nil
}
