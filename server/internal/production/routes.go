// Package production 是「生产/MES」限界上下文的统一入口,
// 移植自 Django apps.production。主要实体:工单(WorkOrder)、工艺路线(Routing)、
// 工序(Process)、看板 WIP 规则(Kanban),并附带工作中心(WorkCenter)作为关联主数据。
//
// 权限码格式 production:<entity>:<action>(view/create/update/delete + 业务动作)。
// 跨模块外键(projects/sales/masterdata/accounts)在本轮以 *uint64 列保留并标 // TODO(port),
// 避免本轮互相依赖导致编译耦合。
package production

import (
	"github.com/atm-erp/server/internal/production/kanban"
	"github.com/atm-erp/server/internal/production/process"
	"github.com/atm-erp/server/internal/production/routing"
	"github.com/atm-erp/server/internal/production/workcenter"
	"github.com/atm-erp/server/internal/production/workorder"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// Routes 装配并注册生产模块全部 REST 路由。
// 形如 production.Routes(api, gdb, middleware.RequirePermission)。
func Routes(rg *gin.RouterGroup, gdb *gorm.DB, perm func(string) gin.HandlerFunc) {
	woH := workorder.NewHandler(workorder.NewService(workorder.NewRepo(gdb)))
	woH.Register(rg, perm)

	rtH := routing.NewHandler(routing.NewService(routing.NewRepo(gdb)))
	rtH.Register(rg, perm)

	prH := process.NewHandler(process.NewService(process.NewRepo(gdb)))
	prH.Register(rg, perm)

	kbH := kanban.NewHandler(kanban.NewService(kanban.NewRepo(gdb)))
	kbH.Register(rg, perm)

	wcH := workcenter.NewHandler(workcenter.NewService(workcenter.NewRepo(gdb)))
	wcH.Register(rg, perm)
}
