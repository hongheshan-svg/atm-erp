package finance

import (
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// Routes 是「财务」上下文的统一入口:装配 repo→service→handler 并注册全部路由。
// 由上层(app.go)调用,形如 finance.Routes(api, gdb, middleware.RequirePermission)。
func Routes(rg *gin.RouterGroup, gdb *gorm.DB, perm func(string) gin.HandlerFunc) {
	repo := NewRepo(gdb)
	svc := NewService(repo)
	h := NewHandler(svc)
	h.Register(rg, perm)
}
