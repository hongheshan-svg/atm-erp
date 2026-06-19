package purchase

import (
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// Routes 是采购模块对外统一入口:内部 new 各层并注册路由。
// 用法(在 app 装配处):purchase.Routes(api, gdb, middleware.RequirePermission)
func Routes(rg *gin.RouterGroup, gdb *gorm.DB, perm func(string) gin.HandlerFunc) {
	repo := NewRepo(gdb)
	svc := NewService(repo)
	h := NewHandler(svc)
	h.Register(rg, perm)
}
