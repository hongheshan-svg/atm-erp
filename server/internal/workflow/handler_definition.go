package workflow

import (
	"net/http"

	"github.com/atm-erp/server/internal/platform/httpx"
	"github.com/gin-gonic/gin"
)

func (h *Handler) listDefinitions(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := DefinitionListQuery{
		BusinessType: c.Query("business_type"),
		IsActive:     parseBoolQuery(c, "is_active"),
		Keyword:      c.Query("search"),
	}
	items, total, err := h.svc.ListDefinitions(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[WorkflowDefinition]{Count: total, Results: items})
}

func (h *Handler) retrieveDefinition(c *gin.Context) {
	d, err := h.svc.GetDefinition(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, d)
}

func (h *Handler) createDefinition(c *gin.Context) {
	var in DefinitionCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	d, err := h.svc.CreateDefinition(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.Created(c, d)
}

func (h *Handler) updateDefinition(c *gin.Context) {
	var in DefinitionUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	d, err := h.svc.UpdateDefinition(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, d)
}

func (h *Handler) deleteDefinition(c *gin.Context) {
	if err := h.svc.DeleteDefinition(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}
