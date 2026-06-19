package app

import (
	"testing"

	"github.com/atm-erp/server/internal/iam"
	"github.com/atm-erp/server/internal/platform/config"
)

// TestBuildRouterNoDuplicateRoutes 验证所有模块路由接线不冲突:
// gin 在注册重复 method+path 时会 panic,本测试以此捕获模块间路由碰撞。
// buildRouter 在注册阶段不访问 DB,故传 nil gdb 即可。
func TestBuildRouterNoDuplicateRoutes(t *testing.T) {
	cfg := &config.Config{AppEnv: "development", JWTSecret: "test-secret"}
	ps := &iam.StaticPermissionService{Superuser: true}
	defer func() {
		if r := recover(); r != nil {
			t.Fatalf("buildRouter panic(可能存在重复路由): %v", r)
		}
	}()
	if buildRouter(cfg, nil, ps) == nil {
		t.Fatal("buildRouter 返回 nil")
	}
}
