package routing

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
	q := ListQuery{Keyword: c.Query("keyword"), Status: c.Query("status")}
	if v := c.Query("product_category"); v != "" {
		if n, err := strconv.ParseUint(v, 10, 64); err == nil {
			q.ProductCategoryID = &n
		}
	}
	if v := c.Query("is_active"); v != "" {
		b := v == "true" || v == "1"
		q.IsActive = &b
	}
	if v := c.Query("is_current"); v != "" {
		b := v == "true" || v == "1"
		q.IsCurrent = &b
	}
	rows, total, err := h.svc.List(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Routing]{Count: total, Results: rows})
}

func (h *Handler) Retrieve(c *gin.Context) {
	rt, err := h.svc.Get(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, rt)
}

func (h *Handler) Create(c *gin.Context) {
	var in CreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	rt, err := h.svc.Create(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, rt)
}

func (h *Handler) Update(c *gin.Context) {
	var in UpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	rt, err := h.svc.Update(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, rt)
}

func (h *Handler) Delete(c *gin.Context) {
	if err := h.svc.Delete(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// Approve POST /:id/approve —— 审批工艺路线。
func (h *Handler) Approve(c *gin.Context) {
	rt, err := h.svc.Approve(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, rt)
}

// Register 挂载路由。权限码格式 production:routing:<action>。
func (h *Handler) Register(rg *gin.RouterGroup, perm func(string) gin.HandlerFunc) {
	g := rg.Group("/production/routings")
	g.GET("", perm("production:routing:view"), h.List)
	g.GET("/:id", perm("production:routing:view"), h.Retrieve)
	g.POST("", perm("production:routing:create"), h.Create)
	g.PUT("/:id", perm("production:routing:update"), h.Update)
	g.DELETE("/:id", perm("production:routing:delete"), h.Delete)
	g.POST("/:id/approve", perm("production:routing:approve"), h.Approve)
}

func parseID(c *gin.Context) uint64 {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 64)
	return id
}

func statusFor(err error) int {
	switch {
	case errors.Is(err, ErrNotFound):
		return http.StatusNotFound
	case errors.Is(err, ErrCodeExists), errors.Is(err, ErrBadTransition):
		return http.StatusBadRequest
	default:
		return http.StatusInternalServerError
	}
}
