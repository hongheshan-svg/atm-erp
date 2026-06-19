// Package iam 提供认证、授权(menu RBAC + 父码通配)、数据范围。
// 蓝图 ADR-005:Casbin 仅承载 menu RBAC;数据范围/字段脱敏/越权边界手写并逐条回归。
// 本脚手架先实现手写的 Authorizer/DataScope(忠实于现有语义),Casbin 接入留待 Phase 1。
package iam

import (
	"context"

	"github.com/gin-gonic/gin"
)

// AuthUser 是请求上下文中的当前用户快照。
type AuthUser struct {
	ID          uint64
	Username    string
	IsSuperuser bool
	Permissions []string          // menu 级权限码(含父码)
	DataScopes  map[string]string // module -> scope(all/dept_tree/dept/self/custom)
	DeptIDs     []uint64
}

const ginAuthUserKey = "erp_auth_user"

func SetAuthUser(c *gin.Context, u *AuthUser) { c.Set(ginAuthUserKey, u) }

func CurrentUser(c *gin.Context) (*AuthUser, bool) {
	v, ok := c.Get(ginAuthUserKey)
	if !ok {
		return nil, false
	}
	u, ok := v.(*AuthUser)
	return u, ok
}

type ctxKey string

const authUserCtxKey ctxKey = "erp_auth_user"

func WithAuthUser(ctx context.Context, u *AuthUser) context.Context {
	return context.WithValue(ctx, authUserCtxKey, u)
}

func AuthUserFrom(ctx context.Context) (*AuthUser, bool) {
	u, ok := ctx.Value(authUserCtxKey).(*AuthUser)
	return u, ok
}
