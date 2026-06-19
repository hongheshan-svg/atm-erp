package process

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
	q := ListQuery{OperationType: c.Query("operation_type")}
	if v := c.Query("routing"); v != "" {
		if n, err := strconv.ParseUint(v, 10, 64); err == nil {
			q.RoutingID = &n
		}
	}
	if v := c.Query("work_station"); v != "" {
		if n, err := strconv.ParseUint(v, 10, 64); err == nil {
			q.WorkStationID = &n
		}
	}
	if v := c.Query("is_outsourced"); v != "" {
		b := v == "true" || v == "1"
		q.IsOutsourced = &b
	}
	rows, total, err := h.svc.List(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Process]{Count: total, Results: rows})
}

func (h *Handler) Retrieve(c *gin.Context) {
	p, err := h.svc.Get(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, p)
}

func (h *Handler) Create(c *gin.Context) {
	var in CreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	p, err := h.svc.Create(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, p)
}

func (h *Handler) Update(c *gin.Context) {
	var in UpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	p, err := h.svc.Update(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, p)
}

func (h *Handler) Delete(c *gin.Context) {
	if err := h.svc.Delete(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// Register 挂载路由。权限码格式 production:process:<action>。
func (h *Handler) Register(rg *gin.RouterGroup, perm func(string) gin.HandlerFunc) {
	g := rg.Group("/production/processes")
	g.GET("", perm("production:process:view"), h.List)
	g.GET("/:id", perm("production:process:view"), h.Retrieve)
	g.POST("", perm("production:process:create"), h.Create)
	g.PUT("/:id", perm("production:process:update"), h.Update)
	g.DELETE("/:id", perm("production:process:delete"), h.Delete)
}

func parseID(c *gin.Context) uint64 {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 64)
	return id
}

func statusFor(err error) int {
	switch {
	case errors.Is(err, ErrNotFound):
		return http.StatusNotFound
	case errors.Is(err, ErrSeqConflict):
		return http.StatusBadRequest
	default:
		return http.StatusInternalServerError
	}
}
