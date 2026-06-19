package workflow

import (
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// Routes 是 workflow 模块统一入口:装配引擎 + handler 并注册路由。
//
// 权限码格式 workflow:<entity>:<action>。注意:Django 端工作流 ViewSet 实际用
// permission_module='system' 且多数读接口 allow_authenticated_read;此处按本轮
// 任务约定统一用 workflow:* 前缀,接线时若需对齐旧权限码再行调整(见 TODO)。
//
// 注:本入口用默认 CallbackRegistry/AssigneeResolver(空实现)。真实接线时应在
// app wire 阶段构造 Service、向 Registry 注册各业务 callback、注入真实 resolver,
// 再调用 RoutesWithService 挂载;Routes 提供「开箱即用、零业务依赖」的默认装配。
func Routes(rg *gin.RouterGroup, gdb *gorm.DB, perm func(string) gin.HandlerFunc) {
	svc := NewService(gdb, NewCallbackRegistry(), defaultResolver{})
	RoutesWithService(rg, svc, perm)
}

// RoutesWithService 用调用方装配好的 Service(已注册 callback/resolver)挂载路由。
func RoutesWithService(rg *gin.RouterGroup, svc *Service, perm func(string) gin.HandlerFunc) {
	h := NewHandler(svc)

	// ── 流程定义 ──
	defs := rg.Group("/workflow/definitions")
	defs.GET("", perm("workflow:definition:view"), h.listDefinitions)
	defs.GET("/:id", perm("workflow:definition:view"), h.retrieveDefinition)
	defs.POST("", perm("workflow:definition:create"), h.createDefinition)
	defs.PUT("/:id", perm("workflow:definition:update"), h.updateDefinition)
	defs.DELETE("/:id", perm("workflow:definition:delete"), h.deleteDefinition)

	// ── 审批步骤 ──
	steps := rg.Group("/workflow/steps")
	steps.GET("", perm("workflow:step:view"), h.listSteps)
	steps.GET("/:id", perm("workflow:step:view"), h.retrieveStep)
	steps.POST("", perm("workflow:step:create"), h.createStep)
	steps.PUT("/:id", perm("workflow:step:update"), h.updateStep)
	steps.DELETE("/:id", perm("workflow:step:delete"), h.deleteStep)
	steps.POST("/reorder", perm("workflow:step:update"), h.reorderSteps)

	// ── 审批实例 ──
	inst := rg.Group("/workflow/instances")
	inst.GET("", perm("workflow:instance:view"), h.listInstances)
	inst.GET("/my_submitted", perm("workflow:instance:view"), h.mySubmitted)
	inst.GET("/history", perm("workflow:instance:view"), h.instanceHistory)
	inst.GET("/:id", perm("workflow:instance:view"), h.retrieveInstance)
	inst.POST("", perm("workflow:instance:create"), h.startInstance)
	inst.POST("/:id/withdraw", perm("workflow:instance:withdraw"), h.withdrawInstance)
	inst.DELETE("/:id", perm("workflow:instance:delete"), h.deleteInstance)

	// ── 审批任务 ──
	tasks := rg.Group("/workflow/tasks")
	tasks.GET("", perm("workflow:task:view"), h.listTasks)
	tasks.GET("/my_pending", perm("workflow:task:view"), h.myPending)
	tasks.GET("/pending_count", perm("workflow:task:view"), h.pendingCount)
	tasks.GET("/:id", perm("workflow:task:view"), h.retrieveTask)
	tasks.POST("/:id/approve", perm("workflow:task:approve"), h.approveTask)
	tasks.POST("/:id/reject", perm("workflow:task:reject"), h.rejectTask)
}
