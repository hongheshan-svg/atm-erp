// Package testutil 提供集成测试辅助:注入超管绕过鉴权、打开并迁移测试库。
// 仅测试用;生产 schema 走 golang-migrate(ADR-004 禁 AutoMigrate)。
package testutil

import (
	"testing"

	"github.com/atm-erp/server/internal/iam"
	"github.com/atm-erp/server/internal/platform/model"
	"github.com/gin-gonic/gin"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

// InjectSuperuser 是测试中间件,注入超管 AuthUser 旁路真实 JWT/RBAC,
// 让集成测试聚焦 repo/service/handler 的 CRUD 行为。
func InjectSuperuser(uid uint64) gin.HandlerFunc {
	return func(c *gin.Context) {
		u := &iam.AuthUser{ID: uid, IsSuperuser: true}
		iam.SetAuthUser(c, u)
		ctx := iam.WithAuthUser(c.Request.Context(), u)
		ctx = model.WithUserID(ctx, uid)
		c.Request = c.Request.WithContext(ctx)
		c.Next()
	}
}

// AllowAll 是一个 no-op 权限中间件,签名匹配各模块 Routes 的 perm 参数。
func AllowAll(_ string) gin.HandlerFunc {
	return func(c *gin.Context) { c.Next() }
}

// OpenDB 连接测试库并对给定模型执行 AutoMigrate(仅测试用)。
func OpenDB(t *testing.T, dsn string, models ...any) *gorm.DB {
	t.Helper()
	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		t.Fatalf("打开测试库失败: %v", err)
	}
	if len(models) > 0 {
		if err := db.AutoMigrate(models...); err != nil {
			t.Fatalf("AutoMigrate 失败: %v", err)
		}
	}
	return db
}

// NewAPIEngine 构建仅挂 /api 组 + 超管旁路的测试引擎,供模块 Routes 注册。
func NewAPIEngine() (*gin.Engine, *gin.RouterGroup) {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	api := r.Group("/api")
	api.Use(InjectSuperuser(1))
	return r, api
}
