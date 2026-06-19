package inventory

import (
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// Routes 是库存与MRP模块的统一装配入口。
// 权限码格式 inventory:<entity>:<action>,对齐前端权限三件套与 Django permission_module/resource。
//
// 用法:inventory.Routes(api, gdb, middleware.RequirePermission)
func Routes(rg *gin.RouterGroup, gdb *gorm.DB, perm func(string) gin.HandlerFunc) {
	repo := NewRepo(gdb)
	svc := NewService(repo)
	h := NewHandler(svc)

	// 库存(只读聚合视图)
	stock := rg.Group("/inventory/stocks")
	stock.GET("", perm("inventory:stock:view"), h.ListStock)
	stock.GET("/:id", perm("inventory:stock:view"), h.RetrieveStock)

	// 库存移动
	move := rg.Group("/inventory/stock-moves")
	move.GET("", perm("inventory:stock_move:view"), h.ListMove)
	move.GET("/:id", perm("inventory:stock_move:view"), h.RetrieveMove)
	move.POST("", perm("inventory:stock_move:create"), h.CreateMove)
	move.PUT("/:id", perm("inventory:stock_move:update"), h.UpdateMove)
	move.DELETE("/:id", perm("inventory:stock_move:delete"), h.DeleteMove)
	move.POST("/:id/complete", perm("inventory:stock_move:complete"), h.CompleteMove)

	// 批次
	batch := rg.Group("/inventory/batches")
	batch.GET("", perm("inventory:batch:view"), h.ListBatch)
	batch.GET("/:id", perm("inventory:batch:view"), h.RetrieveBatch)
	batch.POST("", perm("inventory:batch:create"), h.CreateBatch)
	batch.PUT("/:id", perm("inventory:batch:update"), h.UpdateBatch)
	batch.DELETE("/:id", perm("inventory:batch:delete"), h.DeleteBatch)

	// 库存预警
	alert := rg.Group("/inventory/stock-alerts")
	alert.GET("", perm("inventory:stock_alert:view"), h.ListAlert)
	alert.GET("/:id", perm("inventory:stock_alert:view"), h.RetrieveAlert)
	alert.POST("", perm("inventory:stock_alert:create"), h.CreateAlert)
	alert.DELETE("/:id", perm("inventory:stock_alert:delete"), h.DeleteAlert)
	alert.POST("/:id/acknowledge", perm("inventory:stock_alert:update"), h.AcknowledgeAlert)
	alert.POST("/:id/resolve", perm("inventory:stock_alert:update"), h.ResolveAlert)
	alert.POST("/:id/ignore", perm("inventory:stock_alert:update"), h.IgnoreAlert)
}
