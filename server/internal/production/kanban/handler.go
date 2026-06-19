package kanban

import (
	"errors"
	"net/http"
	"strconv"

	"github.com/atm-erp/server/internal/platform/httpx"
	"github.com/gin-gonic/gin"
)

type Handler struct{ svc *Service }

func NewHandler(svc *Service) *Handler { return &Handler{svc: svc} }

func (h *Handler) List(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := ListQuery{Keyword: c.Query("keyword")}
	if v := c.Query("is_active"); v != "" {
		b := v == "true" || v == "1"
		q.IsActive = &b
	}
	rows, total, err := h.svc.List(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[KanbanWIPRule]{Count: total, Results: rows})
}

func (h *Handler) Retrieve(c *gin.Context) {
	k, err := h.svc.Get(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, k)
}

func (h *Handler) Create(c *gin.Context) {
	var in CreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	k, err := h.svc.Create(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, k)
}

func (h *Handler) Update(c *gin.Context) {
	var in UpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	k, err := h.svc.Update(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, k)
}

func (h *Handler) Delete(c *gin.Context) {
	if err := h.svc.Delete(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// Register 挂载路由。权限码格式 production:kanban:<action>。
// TODO(port): 看板大屏只读聚合端点(overview/work-centers/active-orders/quality)
// 需聚合工单+工作中心+质检实时数据,跨模块,留待集成阶段补全。
func (h *Handler) Register(rg *gin.RouterGroup, perm func(string) gin.HandlerFunc) {
	g := rg.Group("/production/kanban/wip-rules")
	g.GET("", perm("production:kanban:view"), h.List)
	g.GET("/:id", perm("production:kanban:view"), h.Retrieve)
	g.POST("", perm("production:kanban:create"), h.Create)
	g.PUT("/:id", perm("production:kanban:update"), h.Update)
	g.DELETE("/:id", perm("production:kanban:delete"), h.Delete)
}

func parseID(c *gin.Context) uint64 {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 64)
	return id
}

func statusFor(err error) int {
	switch {
	case errors.Is(err, ErrNotFound):
		return http.StatusNotFound
	case errors.Is(err, ErrDuplicate):
		return http.StatusBadRequest
	default:
		return http.StatusInternalServerError
	}
}
