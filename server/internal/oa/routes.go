package oa

import (
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// Routes 是「OA与协同」模块的统一装配入口:new 各实体的 repo→service→handler
// 并注册路由。perm 由调用方注入(如 middleware.RequirePermission),
// 形如 oa.Routes(api, gdb, middleware.RequirePermission)。
func Routes(rg *gin.RouterGroup, gdb *gorm.DB, perm func(string) gin.HandlerFunc) {
	vehicle := NewVehicleHandler(NewVehicleService(NewVehicleRepo(gdb)))
	asset := NewAssetHandler(NewAssetService(NewAssetRepo(gdb)))
	archive := NewArchiveHandler(NewArchiveService(NewArchiveRepo(gdb)))
	announcement := NewAnnouncementHandler(NewAnnouncementService(NewAnnouncementRepo(gdb)))

	vehicle.Register(rg, perm)
	asset.Register(rg, perm)
	archive.Register(rg, perm)
	announcement.Register(rg, perm)
}
