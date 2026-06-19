// Package middleware 实现 Gin 中间件链(顺序敏感),对齐蓝图安全模型:
// Recovery → RequestID → SecurityHeaders → CORS → (RateLimit) → Auth → RequirePermission → (DataScope/Audit)。
// RateLimit / Audit / Casbin 在 Phase 1 补全。
package middleware

import (
	"net/http"
	"strings"

	"github.com/atm-erp/server/internal/iam"
	"github.com/atm-erp/server/internal/platform/httpx"
	"github.com/atm-erp/server/internal/platform/model"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

func RequestID() gin.HandlerFunc {
	return func(c *gin.Context) {
		rid := c.GetHeader("X-Request-ID")
		if rid == "" {
			rid = uuid.NewString()
		}
		c.Set("request_id", rid)
		c.Header("X-Request-ID", rid)
		c.Next()
	}
}

func SecurityHeaders() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Header("X-Content-Type-Options", "nosniff")
		c.Header("X-Frame-Options", "DENY")
		c.Header("Referrer-Policy", "strict-origin-when-cross-origin")
		c.Next()
	}
}

func CORS(allowed []string) gin.HandlerFunc {
	set := make(map[string]bool, len(allowed))
	for _, o := range allowed {
		set[o] = true
	}
	return func(c *gin.Context) {
		origin := c.GetHeader("Origin")
		if origin != "" && set[origin] {
			c.Header("Access-Control-Allow-Origin", origin)
			c.Header("Access-Control-Allow-Credentials", "true")
			c.Header("Access-Control-Allow-Headers", "Authorization,Content-Type,X-Request-ID")
			c.Header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
		}
		if c.Request.Method == http.MethodOptions {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}
		c.Next()
	}
}

// Auth 校验 Bearer JWT、加载权限,把 AuthUser 注入 gin 与 request context。
func Auth(tm *iam.TokenManager, ps iam.PermissionService) gin.HandlerFunc {
	return func(c *gin.Context) {
		h := c.GetHeader("Authorization")
		if !strings.HasPrefix(h, "Bearer ") {
			httpx.Error(c, http.StatusUnauthorized, "未提供认证令牌")
			return
		}
		claims, err := tm.Parse(strings.TrimPrefix(h, "Bearer "))
		if err != nil || claims.TokenType != "access" {
			httpx.Error(c, http.StatusUnauthorized, "令牌无效或已过期")
			return
		}
		u, err := ps.Load(c.Request.Context(), claims.UserID)
		if err != nil {
			httpx.Error(c, http.StatusUnauthorized, "用户不存在")
			return
		}
		iam.SetAuthUser(c, u)
		ctx := iam.WithAuthUser(c.Request.Context(), u)
		ctx = model.WithUserID(ctx, u.ID)
		c.Request = c.Request.WithContext(ctx)
		c.Next()
	}
}

// RequirePermission 要求当前用户拥有指定权限码(父码通配)。
func RequirePermission(code string) gin.HandlerFunc {
	return func(c *gin.Context) {
		u, ok := iam.CurrentUser(c)
		if !ok || !u.Can(code) {
			httpx.Error(c, http.StatusForbidden, "无权限:"+code)
			return
		}
		c.Next()
	}
}

// RequireSystemAdmin 前置封死 system:* 越权(对齐 C1 边界,ADR-005)。
func RequireSystemAdmin() gin.HandlerFunc {
	return func(c *gin.Context) {
		u, ok := iam.CurrentUser(c)
		if !ok || !u.IsSuperuser {
			httpx.Error(c, http.StatusForbidden, "需要系统管理员权限")
			return
		}
		c.Next()
	}
}
