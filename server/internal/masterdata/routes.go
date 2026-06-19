// Package masterdata 是「主数据」限界上下文的统一入口,聚合各实体子包
// (item / customer / supplier / warehouse)的路由装配。
package masterdata

import (
	"github.com/atm-erp/server/internal/masterdata/customer"
	"github.com/atm-erp/server/internal/masterdata/supplier"
	"github.com/atm-erp/server/internal/masterdata/warehouse"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// Routes 装配并注册主数据各实体路由。
// 由上层(app.go)调用,形如 masterdata.Routes(api, gdb, middleware.RequirePermission)。
//
// 注意:item 子包已在 app.go 中单独装配(参考垂直切片),此处不重复注册以免路由冲突。
// 待整合阶段可将 item 也并入本聚合入口。
func Routes(rg *gin.RouterGroup, gdb *gorm.DB, perm func(string) gin.HandlerFunc) {
	customer.NewHandler(customer.NewService(customer.NewRepo(gdb))).Register(rg, perm)
	supplier.NewHandler(supplier.NewService(supplier.NewRepo(gdb))).Register(rg, perm)
	warehouse.NewHandler(warehouse.NewService(warehouse.NewRepo(gdb))).Register(rg, perm)
}
