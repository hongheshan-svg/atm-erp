package customer

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
	rows, total, err := h.svc.List(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Customer]{Count: total, Results: rows})
}

func (h *Handler) Retrieve(c *gin.Context) {
	row, err := h.svc.Get(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, row)
}

func (h *Handler) Create(c *gin.Context) {
	var in CreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	row, err := h.svc.Create(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, row)
}

func (h *Handler) Update(c *gin.Context) {
	var in UpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	row, err := h.svc.Update(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, row)
}

func (h *Handler) ChangeStatus(c *gin.Context) {
	var in ChangeStatusInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	row, err := h.svc.ChangeStatus(c.Request.Context(), parseID(c), in.Status)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, row)
}

func (h *Handler) Delete(c *gin.Context) {
	if err := h.svc.Delete(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// Register 挂载路由,权限码对齐前端三件套(masterdata:customer:*)。
func (h *Handler) Register(rg *gin.RouterGroup, perm func(string) gin.HandlerFunc) {
	g := rg.Group("/masterdata/customers")
	g.GET("", perm("masterdata:customer:view"), h.List)
	g.GET("/:id", perm("masterdata:customer:view"), h.Retrieve)
	g.POST("", perm("masterdata:customer:create"), h.Create)
	g.PUT("/:id", perm("masterdata:customer:update"), h.Update)
	g.POST("/:id/change_status", perm("masterdata:customer:update"), h.ChangeStatus)
	g.DELETE("/:id", perm("masterdata:customer:delete"), h.Delete)
}

func parseID(c *gin.Context) uint64 {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 64)
	return id
}

func statusFor(err error) int {
	switch {
	case errors.Is(err, ErrNotFound):
		return http.StatusNotFound
	case errors.Is(err, ErrCodeExists), errors.Is(err, ErrInvalidStatus):
		return http.StatusBadRequest
	default:
		return http.StatusInternalServerError
	}
}
