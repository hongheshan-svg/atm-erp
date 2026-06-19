package workorder

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
	q := ListQuery{
		Keyword: c.Query("keyword"),
		Status:  c.Query("status"),
	}
	if v := c.Query("priority"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			q.Priority = &n
		}
	}
	if v := c.Query("work_center"); v != "" {
		if n, err := strconv.ParseUint(v, 10, 64); err == nil {
			q.WorkCenterID = &n
		}
	}
	if v := c.Query("project"); v != "" {
		if n, err := strconv.ParseUint(v, 10, 64); err == nil {
			q.ProjectID = &n
		}
	}
	rows, total, err := h.svc.List(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[WorkOrder]{Count: total, Results: rows})
}

func (h *Handler) Retrieve(c *gin.Context) {
	wo, err := h.svc.Get(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, wo)
}

func (h *Handler) Create(c *gin.Context) {
	var in CreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	wo, err := h.svc.Create(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.Created(c, wo)
}

func (h *Handler) Update(c *gin.Context) {
	var in UpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	wo, err := h.svc.Update(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, wo)
}

func (h *Handler) Delete(c *gin.Context) {
	if err := h.svc.Delete(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// Start POST /:id/start —— 开始生产。
func (h *Handler) Start(c *gin.Context) {
	wo, err := h.svc.Start(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, wo)
}

// Complete POST /:id/complete —— 完成生产。
func (h *Handler) Complete(c *gin.Context) {
	var in CompleteInput
	if err := c.ShouldBindJSON(&in); err != nil && err.Error() != "EOF" {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	wo, err := h.svc.Complete(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, wo)
}

// Register 挂载路由。权限码格式 production:work_order:<action>。
func (h *Handler) Register(rg *gin.RouterGroup, perm func(string) gin.HandlerFunc) {
	g := rg.Group("/production/work-orders")
	g.GET("", perm("production:work_order:view"), h.List)
	g.GET("/:id", perm("production:work_order:view"), h.Retrieve)
	g.POST("", perm("production:work_order:create"), h.Create)
	g.PUT("/:id", perm("production:work_order:update"), h.Update)
	g.DELETE("/:id", perm("production:work_order:delete"), h.Delete)
	g.POST("/:id/start", perm("production:work_order:start"), h.Start)
	g.POST("/:id/complete", perm("production:work_order:complete"), h.Complete)
}

func parseID(c *gin.Context) uint64 {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 64)
	return id
}

func statusFor(err error) int {
	switch {
	case errors.Is(err, ErrNotFound):
		return http.StatusNotFound
	case errors.Is(err, ErrBadTransition), errors.Is(err, ErrQtyNegative), errors.Is(err, ErrQtyExceed):
		return http.StatusBadRequest
	default:
		return http.StatusInternalServerError
	}
}
