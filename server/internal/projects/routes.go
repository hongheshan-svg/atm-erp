package projects

import (
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// Routes 装配「项目与工程」上下文的全部路由到 rg 下。
// 权限码格式 projects:<entity>:<action>(view/create/update/delete + 业务动作),
// 与前端三件套(路由 meta.permission / hasPermission / v-permission)保持一致。
func Routes(rg *gin.RouterGroup, gdb *gorm.DB, perm func(string) gin.HandlerFunc) {
	repo := NewRepo(gdb)
	svc := NewService(repo)
	h := NewHandler(svc)

	// ---- Project ----
	p := rg.Group("/projects/projects")
	p.GET("", perm("projects:project:view"), h.listProjects)
	p.GET("/:id", perm("projects:project:view"), h.retrieveProject)
	p.POST("", perm("projects:project:create"), h.createProject)
	p.PUT("/:id", perm("projects:project:update"), h.updateProject)
	p.DELETE("/:id", perm("projects:project:delete"), h.deleteProject)
	p.POST("/:id/submit", perm("projects:project:update"), h.submitProject)
	p.POST("/:id/change_status", perm("projects:project:update"), h.changeProjectStatus)

	// ---- ProjectTask ----
	t := rg.Group("/projects/tasks")
	t.GET("", perm("projects:project_task:view"), h.listTasks)
	t.GET("/:id", perm("projects:project_task:view"), h.retrieveTask)
	t.POST("", perm("projects:project_task:create"), h.createTask)
	t.PUT("/:id", perm("projects:project_task:update"), h.updateTask)
	t.DELETE("/:id", perm("projects:project_task:delete"), h.deleteTask)
	t.POST("/:id/update_progress", perm("projects:project_task:update"), h.updateTaskProgress)

	// ---- ProjectBOM ----
	b := rg.Group("/projects/bom")
	b.GET("", perm("projects:project_bom:view"), h.listBOM)
	b.GET("/:id", perm("projects:project_bom:view"), h.retrieveBOM)
	b.POST("", perm("projects:project_bom:create"), h.createBOM)
	b.PUT("/:id", perm("projects:project_bom:update"), h.updateBOM)
	b.DELETE("/:id", perm("projects:project_bom:delete"), h.deleteBOM)
	b.POST("/:id/confirm", perm("projects:project_bom:update"), h.confirmBOM)
	b.POST("/:id/release", perm("projects:project_bom:update"), h.releaseBOM)

	// ---- Drawing ----
	d := rg.Group("/projects/drawings")
	d.GET("", perm("projects:drawing:view"), h.listDrawings)
	d.GET("/:id", perm("projects:drawing:view"), h.retrieveDrawing)
	d.POST("", perm("projects:drawing:create"), h.createDrawing)
	d.PUT("/:id", perm("projects:drawing:update"), h.updateDrawing)
	d.DELETE("/:id", perm("projects:drawing:delete"), h.deleteDrawing)
	d.POST("/:id/submit_review", perm("projects:drawing:update"), h.submitDrawingReview)
	d.POST("/:id/approve", perm("projects:drawing:approve"), h.approveDrawing)
	d.POST("/:id/reject", perm("projects:drawing:approve"), h.rejectDrawing)
	d.POST("/:id/release", perm("projects:drawing:release"), h.releaseDrawing)
}
