package accounts

import (
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// Routes 是 accounts 模块的统一装配入口:new Repo→Service→Handler,并注册全部路由。
// 调用方:accounts.Routes(api, gdb, middleware.RequirePermission)。
func Routes(rg *gin.RouterGroup, gdb *gorm.DB, perm func(string) gin.HandlerFunc) {
	h := NewHandler(NewService(NewRepo(gdb)))
	h.Register(rg, perm)
}
